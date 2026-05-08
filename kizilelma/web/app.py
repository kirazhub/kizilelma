"""Kızılelma Web Terminal — Bloomberg tarzı arayüz (FastAPI).

API uç noktaları:
    - GET /                : Ana HTML sayfası (terminal arayüzü)
    - GET /api/status      : Sağlık kontrolü + canlı saat
    - GET /api/snapshot    : Güncel piyasa verisi (cache'lenir)
    - GET /api/history     : Son 30 snapshot kaydı (DB'den)

Cache stratejisi:
    Snapshot çağrısı TEFAS yüzünden 30-60 saniye sürebilir.
    Bu yüzden sonuç 5 dakika boyunca bellekte tutulur; aynı istek
    tekrar gelirse cache'den döndürülür. İlk çağrı yavaş,
    sonrakiler anlıktır.
"""
import asyncio
import datetime as dt
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
CACHE_TTL_SECONDS = 5 * 60  # 5 dakika


class SnapshotCache:
    """Basit bellekteki snapshot cache'i.

    Aynı anda birden fazla istek gelirse tek bir toplama işlemi
    beklenir — böylece TEFAS'a aynı anda 10 kere istek atmış olmayız.
    """

    def __init__(self, ttl_seconds: int = CACHE_TTL_SECONDS) -> None:
        self._data: Optional[dict] = None
        self._fetched_at: Optional[dt.datetime] = None
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()

    def is_fresh(self) -> bool:
        if self._data is None or self._fetched_at is None:
            return False
        age = (dt.datetime.now() - self._fetched_at).total_seconds()
        return age < self._ttl

    async def get_or_fetch(self) -> dict:
        """Cache taze ise onu döndür, değilse yenile."""
        if self.is_fresh():
            return self._wrap(self._data, cached=True)

        async with self._lock:
            # Başkası doldurmuş olabilir
            if self.is_fresh():
                return self._wrap(self._data, cached=True)

            # Import burada — circular import'tan kaçınmak için
            from kizilelma.scheduler.daily_job import collect_all_data

            logger.info("Snapshot cache yenileniyor…")
            snapshot = await collect_all_data()
            self._data = snapshot.model_dump(mode="json")
            self._fetched_at = dt.datetime.now()
            return self._wrap(self._data, cached=False)

    def _wrap(self, data: dict, cached: bool) -> dict:
        return {
            "data": data,
            "cached": cached,
            "fetched_at": self._fetched_at.isoformat() if self._fetched_at else None,
        }


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
    """Güncel piyasa verisini JSON döndürür (cache'li)."""
    try:
        result = await _cache.get_or_fetch()
        return result
    except Exception as exc:
        logger.exception("Snapshot toplama başarısız")
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


def main() -> None:
    """CLI giriş noktası — uvicorn sunucusunu başlatır."""
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    print("=" * 60)
    print("  KIZILELMA TERMINAL")
    print("  http://localhost:8000")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
