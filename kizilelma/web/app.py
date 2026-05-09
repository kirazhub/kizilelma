"""Kızılelma Web Terminal — Bloomberg tarzı arayüz (FastAPI).

API uç noktaları:
    - GET /                : Ana HTML sayfası (terminal arayüzü)
    - GET /api/status      : Sağlık kontrolü + canlı saat
    - GET /api/snapshot    : Güncel piyasa verisi (cache'lenir + DB fallback)
    - GET /api/history     : Son 30 snapshot kaydı (DB'den)

Cache & fallback stratejisi:
    Kullanıcı ASLA boş ekran görmemeli. Üç katmanlı akış:

    1. Taze cache (< 5 dk)     → cache'den dön (`source=live` veya `source=db`)
    2. Canlı toplama (collect) → başarılıysa cache'le ve dön (`source=live`)
    3. DB fallback             → canlı patladıysa en son DB kaydını dön
                                 (`source=db`, `is_historical=true`)
    4. DB de boşsa             → 503 error

    Böylece hafta sonu / TEFAS bakım / internet kesintisi durumlarında bile
    en son kalan veri ekranda kalır; üstte "DATA AS OF: …" uyarısı çıkar.
"""
import asyncio
import datetime as dt
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from kizilelma.agent.chat import ChatRequest, chat_endpoint


logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
CACHE_TTL_SECONDS = 5 * 60  # 5 dakika

# AI yorumu cache — saatte bir yenilenir (API maliyetini düşürür)
AI_CACHE_DURATION = dt.timedelta(hours=1)
_ai_cache: dict = {
    "commentary": None,
    "fetched_at": None,
    "snapshot_timestamp": None,
}
_ai_lock = asyncio.Lock()


class SnapshotCache:
    """Bellekteki snapshot cache'i + DB fallback yöneticisi.

    Aynı anda birden fazla istek gelirse tek bir toplama işlemi beklenir —
    böylece TEFAS'a aynı anda 10 kere istek atmış olmayız.

    Canlı toplama başarısız olursa otomatik olarak DB'deki en son snapshot'a
    düşer; o da yoksa hatayı yukarı atar.

    İç durum alanları (testlerin eriştiği):
        _data        : cache'deki dict (ham snapshot verisi)
        _fetched_at  : cache'in alındığı zaman
        _source      : "live" | "db" — verinin nereden geldiği
    """

    def __init__(self, ttl_seconds: int = CACHE_TTL_SECONDS) -> None:
        self._data: Optional[dict] = None
        self._fetched_at: Optional[dt.datetime] = None
        self._source: Optional[str] = None  # "live" | "db"
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()

    def is_fresh(self) -> bool:
        if self._data is None or self._fetched_at is None:
            return False
        age = (dt.datetime.now() - self._fetched_at).total_seconds()
        return age < self._ttl

    async def get_or_fetch(self) -> dict:
        """Cache taze ise onu döndür; değilse canlı çek, o da başarısızsa DB'ye düş.

        Returns:
            `{"data": <snapshot_dict>, "cached": bool, "fetched_at": iso,
              "source": "live"|"db", "live_error": str|None}` yapısı.

        Raises:
            Exception: Hem canlı toplama hem DB fallback başarısızsa.
        """
        if self.is_fresh():
            return self._wrap(self._data, cached=True, live_error=None)

        async with self._lock:
            # Başkası doldurmuş olabilir
            if self.is_fresh():
                return self._wrap(self._data, cached=True, live_error=None)

            # Import burada — circular import'tan kaçınmak için
            from kizilelma.scheduler.daily_job import collect_all_data

            # Katman 1: Canlı veri toplamayı dene
            try:
                logger.info("Snapshot cache yenileniyor (canlı)…")
                snapshot = await collect_all_data()
                data = snapshot.model_dump(mode="json")
                data["is_historical"] = False
                self._data = data
                self._fetched_at = dt.datetime.now()
                self._source = "live"
                return self._wrap(self._data, cached=False, live_error=None)
            except Exception as exc:
                live_error = str(exc)[:200]
                logger.warning(
                    "Canlı veri çekilemedi, DB fallback deneniyor: %s", exc
                )

                # Katman 2: DB fallback — en son başarılı snapshot'ı getir
                try:
                    from kizilelma.storage.db import get_latest_full_snapshot

                    historical = get_latest_full_snapshot()
                except Exception as db_exc:
                    # DB de patladıysa canlı hatasını aynen yukarı at
                    logger.error("DB fallback da başarısız: %s", db_exc)
                    raise exc from db_exc

                if historical is None:
                    # DB boş — kullanıcı için yapacak bir şey yok
                    logger.error("Canlı hata + DB boş → 503")
                    raise exc

                # DB verisini cache'le — tekrar tekrar DB'ye gitmeyelim
                logger.info(
                    "DB'deki en son snapshot kullanılıyor (timestamp=%s)",
                    historical.get("timestamp"),
                )
                self._data = historical
                self._fetched_at = dt.datetime.now()
                self._source = "db"
                return self._wrap(
                    self._data, cached=False, live_error=live_error
                )

    def _wrap(
        self, data: dict, cached: bool, live_error: Optional[str]
    ) -> dict:
        return {
            "data": data,
            "cached": cached,
            "fetched_at": self._fetched_at.isoformat() if self._fetched_at else None,
            "source": self._source or "unknown",
            "live_error": live_error,
        }

    def get_cached_data(self) -> Optional[dict]:
        """Cache'deki ham veri (varsa) — async olmayan erişim için."""
        return self._data


_cache = SnapshotCache()


app = FastAPI(
    title="Kızılelma Terminal",
    description="Bloomberg tarzı yatırım terminali — Türkiye piyasaları",
    version="0.1.0",
)

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)


@app.get("/")
async def home():
    """Ana HTML sayfasını servis et."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/status")
async def status():
    """Sistem sağlık kontrolü ve saat bilgisi."""
    import pytz

    now = dt.datetime.now()
    ist = dt.datetime.now(pytz.timezone("Europe/Istanbul"))
    return {
        "status": "LIVE",
        "server_time": now.isoformat(),
        "istanbul_time": ist.strftime("%H:%M:%S"),
        "istanbul_date": ist.strftime("%Y-%m-%d"),
        "cache_fresh": _cache.is_fresh(),
    }


@app.get("/api/snapshot")
async def current_snapshot():
    """Güncel piyasa verisini JSON döndürür (cache + DB fallback'li).

    Başarı durumu:
        200 + { data, cached, fetched_at, source, live_error }
        - source="live" : canlı toplama başarılı
        - source="db"   : canlı başarısız, DB'den dönüldü (data.is_historical=True)

    Hata durumu (sadece canlı başarısız + DB boşken):
        503 + { error, data: null }
    """
    try:
        return await _cache.get_or_fetch()
    except Exception as exc:
        logger.exception("Snapshot toplama başarısız ve DB fallback yok")
        return JSONResponse(
            status_code=503,
            content={"error": str(exc), "data": None},
        )


@app.get("/api/history")
async def history():
    """Son 30 günlük snapshot geçmişi (DB'den)."""
    try:
        from kizilelma.storage.db import get_recent_snapshots

        snaps = get_recent_snapshots(limit=30)
        return [
            {
                "id": s.id,
                "timestamp": s.timestamp.isoformat(),
                "fund_count": s.fund_count,
                "bond_count": s.bond_count,
                "news_count": s.news_count,
            }
            for s in snaps
        ]
    except Exception as exc:
        logger.warning(f"History çekilemedi: {exc}")
        return []


# ----------------------------------------------------------------------------
# AI Commentary — Claude ile 2-3 cümlelik piyasa özeti
# ----------------------------------------------------------------------------

def _safe_float(value) -> float:
    """String/None/float → float, başarısızsa 0.0 (crash etmez)."""
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


async def _generate_ai_commentary(snapshot: dict) -> str:
    """Snapshot verisinden Claude ile 2-3 cümlelik piyasa yorumu üret.

    ANTHROPIC_API_KEY yoksa veya herhangi bir hata varsa istisna fırlatır —
    çağıran fonksiyon zarif fallback yapar.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("AI key yok")

    import anthropic  # lazy import — env yoksa hiç yüklenmesin

    funds = snapshot.get("funds", []) or []
    repo_rates = snapshot.get("repo_rates", []) or []
    bonds = snapshot.get("bonds", []) or []

    # En yüksek 1Y getirili 5 fon (sadece >0 olanlar)
    top_funds = sorted(
        [f for f in funds if _safe_float(f.get("return_1y")) > 0],
        key=lambda f: _safe_float(f.get("return_1y")),
        reverse=True,
    )[:5]

    fund_summary = ", ".join(
        f"{f.get('code', '?')} ({(f.get('category') or '')[:20]}) "
        f"%{_safe_float(f.get('return_1y')):.1f}"
        for f in top_funds
    ) or "veri yok"

    # TCMB 1 haftalık repo oranı
    policy_rate: Optional[float] = None
    for r in repo_rates:
        if r.get("type") == "repo" and r.get("maturity") == "1w":
            policy_rate = _safe_float(r.get("rate"))
            break

    prompt = f"""Bugün Türkiye piyasa verileri:

En iyi 5 fon (1Y getiri):
{fund_summary}

TCMB politika faizi: {f'{policy_rate:.2f}' if policy_rate else 'bilinmiyor'}%
Toplam fon sayısı: {len(funds)}
İzlenen tahvil: {len(bonds)}

Bu verilerden yola çıkarak 2-3 cümlelik KISA ve ÖZ bir Türkçe piyasa yorumu yaz. Hikaye anlatma, sadece günün öne çıkan durumunu belirt. Örnek: "Para piyasası fonları güçlü. TCMB faizi sabit kalıyor. Kısa vadeli risksiz enstrümanlar önde."

Yanıtında sadece yorum olsun, başka hiçbir şey yazma. 200 karakteri geçme."""

    client = anthropic.AsyncAnthropic(api_key=api_key)
    response = await client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=200,
        system=(
            "Sen Türkiye finansal piyasaları uzmanı bir analiz motorusun. "
            "Çok kısa, net, veri odaklı yorumlar yazarsın. Hikaye anlatmaz, "
            "sadece gözlem belirtirsin."
        ),
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text.strip()


@app.get("/api/ai_commentary")
async def ai_commentary():
    """Günün piyasa verisinden 2-3 cümlelik AI yorumu üret.

    Cache: 1 saat boyunca aynı yorum tekrar kullanılır (API maliyet kontrolü).
    ANTHROPIC_API_KEY yoksa veya hata varsa `commentary: null` döner — frontend
    bunu zarif şekilde fallback gösterir.

    Yanıt:
        {"commentary": "...", "cached": bool, "generated_at": iso, "snapshot_timestamp": iso}
        veya hata durumunda
        {"commentary": null, "error": "..."}
    """
    now = dt.datetime.now()

    # Cache kontrol — lock'suz, sadece okuma
    if (
        _ai_cache["commentary"] is not None
        and _ai_cache["fetched_at"] is not None
        and now - _ai_cache["fetched_at"] < AI_CACHE_DURATION
    ):
        return {
            "commentary": _ai_cache["commentary"],
            "cached": True,
            "generated_at": _ai_cache["fetched_at"].isoformat(),
            "snapshot_timestamp": _ai_cache["snapshot_timestamp"],
        }

    # Yenileme — lock al, aynı anda birden fazla istek API'yi dövmesin
    async with _ai_lock:
        # Başkası doldurmuş olabilir
        if (
            _ai_cache["commentary"] is not None
            and _ai_cache["fetched_at"] is not None
            and now - _ai_cache["fetched_at"] < AI_CACHE_DURATION
        ):
            return {
                "commentary": _ai_cache["commentary"],
                "cached": True,
                "generated_at": _ai_cache["fetched_at"].isoformat(),
                "snapshot_timestamp": _ai_cache["snapshot_timestamp"],
            }

        # Snapshot al (cache'ten gelir büyük ihtimalle)
        try:
            snap_payload = await _cache.get_or_fetch()
            snapshot = snap_payload.get("data") or {}
        except Exception as exc:
            logger.warning("AI yorumu için snapshot alınamadı: %s", exc)
            return {"commentary": None, "error": "Snapshot yok"}

        if not snapshot:
            return {"commentary": None, "error": "Snapshot boş"}

        try:
            commentary = await _generate_ai_commentary(snapshot)
        except RuntimeError as exc:
            # AI key yok — sessiz geç
            return {"commentary": None, "error": str(exc)}
        except Exception as exc:
            logger.warning("AI yorumu üretilemedi: %s", exc)
            return {"commentary": None, "error": str(exc)[:100]}

        # Cache'le
        _ai_cache["commentary"] = commentary
        _ai_cache["fetched_at"] = now
        _ai_cache["snapshot_timestamp"] = snapshot.get("timestamp")

        return {
            "commentary": commentary,
            "cached": False,
            "generated_at": now.isoformat(),
            "snapshot_timestamp": snapshot.get("timestamp"),
        }


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """AI chat endpoint — Claude Haiku ile RAG, SSE streaming döner."""
    return await chat_endpoint(request)


def main() -> None:
    """CLI giriş noktası — uvicorn sunucusunu başlatır.

    Railway ve benzeri PaaS ortamlarında `$PORT` env değişkeni verilir;
    lokal kullanımda 8000 default'u devreye girer.
    """
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    port = int(os.environ.get("PORT", 8000))
    print("=" * 60)
    print("  KIZILELMA TERMINAL")
    print(f"  http://0.0.0.0:{port}")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
