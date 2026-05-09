"""Kızılelma AI Chat — basit, garantili çalışan tek dosyalı modül.

Üç fonksiyon, anlaşılması kolay:
    1. get_context(message)        → veriyi DB'den topla (tek yerden)
    2. build_prompt(ctx, msg, hist) → context'i Claude prompt'una çevir
    3. stream_response(msg, hist)   → Claude'dan canlı (streaming) cevap

FastAPI bağlantısı:
    chat_endpoint(ChatRequest) → SSE StreamingResponse
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import AsyncGenerator

import anthropic
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from kizilelma.storage.db import get_engine
from kizilelma.storage.models import (
    FundRecord,
    MacroRecord,
    RepoRecord,
    SnapshotRecord,
)


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Claude ayarları
# ---------------------------------------------------------------------------
CLAUDE_MODEL = "claude-haiku-4-5"
MAX_TOKENS = 800
MAX_TOKENS_REPORT = 1500  # Rapor modu daha uzun çıktı ister
TEMPERATURE = 0.8

# Türkçe büyük harfli kelimeler bazen 2-4 karakterli oluyor; bunlar fon kodu
# DEĞİLDİR ama regex'e takılır → context'e yanlış fon eklemeyelim diye filtre.
STOP_WORDS = {
    "TCMB", "BIST", "USD", "EUR", "TL", "AI", "YTL",
    "KDV", "NE", "EN", "AB", "ABD", "PARA", "BU", "NE",
    "VE", "DA", "DE", "Kİ", "MI", "MU",
}


# ===========================================================================
# 1. CONTEXT TOPLAMA — Tüm veriyi tek yerden, garantili al
# ===========================================================================

def get_context(message: str) -> dict:
    """Soruya göre gerekli veriyi DB'den topla.

    HER ZAMAN aşağıdaki anahtarlarla bir dict döner:
        - macro_data       : USD, EUR, altın, BIST, petrol, vs.
        - funds            : Soruyla ilgili fonlar (kod geçiyorsa onlar, yoksa top 5)
        - repo_rates       : TCMB faiz oranları
        - latest_snapshot  : En son snapshot zamanı (ISO string) ya da None
    """
    context: dict = {
        "macro_data": [],
        "funds": [],
        "repo_rates": [],
        "latest_snapshot": None,
    }

    engine = get_engine()
    with Session(engine) as session:
        # --- En son DOLU snapshot'ı bul ---------------------------------------
        # Bazen en son snapshot tamamen boş kalabilir (collector hatası vs).
        # Bu yüzden "makro veya fon içeren" en son snapshot'ı arıyoruz.
        last_macro = session.exec(
            select(MacroRecord).order_by(MacroRecord.snapshot_id.desc()).limit(1)
        ).first()
        last_fund = session.exec(
            select(FundRecord).order_by(FundRecord.snapshot_id.desc()).limit(1)
        ).first()

        candidate_snap_ids: list[int] = []
        if last_macro:
            candidate_snap_ids.append(last_macro.snapshot_id)
        if last_fund:
            candidate_snap_ids.append(last_fund.snapshot_id)

        if not candidate_snap_ids:
            # DB tamamen boşsa boş context dön
            return context

        snap_id = max(candidate_snap_ids)
        latest_snap = session.get(SnapshotRecord, snap_id)
        if latest_snap:
            context["latest_snapshot"] = latest_snap.timestamp.isoformat()
        # --- MAKRO VERİLER ----------------------------------------------------
        # Strateji: Her sembolün EN SON kaydını al.
        # Tek snapshot'a bakmıyoruz çünkü bazen bir snapshot eksik kalır
        # (örn: yfinance hata verir, sadece bir kısmı kaydedilir).
        # Distinct sembolleri çekip her biri için en son kaydı topluyoruz.
        all_symbols = list(
            session.exec(select(MacroRecord.symbol).distinct()).all()
        )
        macros: list[MacroRecord] = []
        for sym in all_symbols:
            latest_for_sym = session.exec(
                select(MacroRecord)
                .where(MacroRecord.symbol == sym)
                .order_by(MacroRecord.id.desc())
                .limit(1)
            ).first()
            if latest_for_sym:
                macros.append(latest_for_sym)

        # Önemli sembolleri başa al (USDTRY, EURTRY, GOLD, BIST, BRENT)
        priority_order = {
            "USDTRY": 0, "EURTRY": 1, "GOLD_OZ": 2,
            "BIST100": 3, "BRENT": 4,
        }
        macros.sort(key=lambda m: priority_order.get(m.symbol, 99))

        context["macro_data"] = [
            {
                "symbol": m.symbol,
                "name": m.name,
                "value": float(m.value),
                "currency": m.currency,
                "category": m.category,
                "date": m.date.isoformat() if m.date else "",
            }
            for m in macros
        ]

        # latest_snapshot'ı gerçek veri tarihinden hesapla
        # (snapshot.timestamp ile makro.date farklı olabiliyor)
        all_dates = [m.date for m in macros if m.date]
        if all_dates:
            most_recent = max(all_dates)
            context["latest_snapshot"] = most_recent.isoformat()

        # --- REPO / TCMB FAİZ -------------------------------------------------
        repo_stmt = select(RepoRecord).where(RepoRecord.snapshot_id == snap_id)
        repos = list(session.exec(repo_stmt))
        if not repos:
            # Repo içeren en son snapshot'a düş
            last_repo = session.exec(
                select(RepoRecord).order_by(RepoRecord.snapshot_id.desc()).limit(1)
            ).first()
            if last_repo:
                repos = list(
                    session.exec(
                        select(RepoRecord).where(
                            RepoRecord.snapshot_id == last_repo.snapshot_id
                        )
                    )
                )

        context["repo_rates"] = [
            {
                "type": r.type,
                "maturity": r.maturity,
                "rate": float(r.rate),
                "date": r.date.isoformat() if r.date else "",
            }
            for r in repos
        ]

        # --- FONLAR -----------------------------------------------------------
        # Soruda fon kodu var mı? (2-4 büyük harf ardışık)
        candidate_codes = re.findall(r"\b[A-Z]{2,4}\b", message)
        fund_codes = [c for c in candidate_codes if c not in STOP_WORDS]

        if fund_codes:
            # Belirli fonları getir (en son fiyat)
            funds: list[FundRecord] = []
            for code in fund_codes[:5]:
                stmt = (
                    select(FundRecord)
                    .where(FundRecord.code == code)
                    .order_by(FundRecord.snapshot_id.desc())
                    .limit(1)
                )
                fund = session.exec(stmt).first()
                if fund:
                    funds.append(fund)
            context["funds"] = [_fund_dict(f) for f in funds]
        else:
            # Genel: en yüksek 1Y getirili 5 fon
            # Fon içeren en son snapshot'ı kullan (snap_id boş olabilir)
            fund_snap_id = last_fund.snapshot_id if last_fund else snap_id
            stmt = (
                select(FundRecord)
                .where(FundRecord.snapshot_id == fund_snap_id)
                .where(FundRecord.return_1y > 0)
                .order_by(FundRecord.return_1y.desc())
                .limit(5)
            )
            top_funds = list(session.exec(stmt))
            context["funds"] = [_fund_dict(f) for f in top_funds]

    return context


def _fund_dict(f: FundRecord) -> dict:
    """FundRecord'u JSON'a uygun dict'e çevir."""
    return {
        "code": f.code,
        "name": f.name,
        "category": f.category or "",
        "price": float(f.price) if f.price else 0.0,
        "return_1d": float(f.return_1d) if f.return_1d is not None else None,
        "return_1m": float(f.return_1m) if f.return_1m is not None else None,
        "return_1y": float(f.return_1y) if f.return_1y is not None else None,
        "date": f.date.isoformat() if f.date else "",
    }


# ===========================================================================
# 2. PROMPT OLUŞTURMA
# ===========================================================================


def is_report_request(message: str) -> bool:
    """Kullanıcı rapor istiyor mu kontrol et.

    Bazı tetikleyici kelimeler RAPOR MODU'nu aktif eder. Bu modda AI yapılandırılmış,
    ASCII tablo formatında detaylı bir piyasa raporu üretir.
    """
    message_lower = message.lower()
    report_keywords = [
        "rapor ver", "rapor", "analiz ver", "analiz", "özet ver", "özet",
        "tablo", "günün durumu", "günün özeti", "piyasa raporu",
        "genel görünüm", "detaylı bilgi", "detayli rapor",
        "günlük rapor", "haftalık rapor", "performans raporu",
        "ozet", "ozet ver",  # şapkasız varyantlar
    ]
    return any(kw in message_lower for kw in report_keywords)


SYSTEM_PROMPT = """Sen Kızıl Elma adında, Türkiye finansal piyasalar uzmanı bir AI analiz
asistanısın. YZ Portföy platformu için profesyonel finansal analiz ve raporlama hizmeti
veriyorsun.

═══════════════════════════════════════
KİMLİĞİN VE TONUN
═══════════════════════════════════════

- Profesyonel ama erişilebilir bir finans uzmanısın
- Bankacı tonunda değil, daha sıcak — ama saygılı ve net
- Veriye dayalı konuşursun, fikir değil rakam söylersin
- Yorumlarında objektif kalırsın, kesin tahmin yapmazsın

═══════════════════════════════════════
İKİ MOD: SOHBET vs RAPOR
═══════════════════════════════════════

▌ SOHBET MODU (varsayılan)
Kullanıcı normal soru sorduğunda:
- 3-5 cümlelik akıcı paragraf
- Bir konuda derinleşmek için somut rakamlar
- Profesyonel ama kuru olmayan ton
- "Şu anda...", "Mevcut görünümde...", "Veriye göre..." gibi başlangıçlar
- ASLA liste, tablo veya bullet yapma — akıcı paragraf

▌ RAPOR MODU
Sana "⚡ RAPOR MODU AKTİF" işareti geldiğinde RAPOR formatında cevap ver.

Rapor formatı (ASCII tablo, monospace):

═══════════════════════════════════════
📊 PİYASA RAPORU — [TARİH]
═══════════════════════════════════════

▌ DÖVİZ PİYASALARI
USD/TRY ............ [değer]
EUR/TRY ............ [değer]

▌ KIYMETLİ MADENLER
Gram Altın ......... [değer] ₺
Ons Altın .......... [değer] $

▌ ENDEKS & EMTİA
BIST 100 ........... [değer] puan
Brent Petrol ....... $[değer]

▌ FAİZ ORANLARI (TCMB)
Politika Faizi ..... %[değer]
Gecelik Repo ....... %[değer]

▌ ÖNE ÇIKAN FONLAR (1Y Performans)
1. [KOD] ............ +%[getiri] ([kategori])
2. [KOD] ............ +%[getiri] ([kategori])

▌ ANALİZ ÖZETİ
[2-3 cümlelik trend yorumu ve özet]

⚠️ Bu rapor sadece bilgilendirme amaçlıdır, yatırım tavsiyesi niteliği taşımaz.
═══════════════════════════════════════

═══════════════════════════════════════
VERİ KULLANIMI - ZORUNLU KURALLAR
═══════════════════════════════════════

1. Sana her seferinde "📊 GÜNCEL PİYASA VERİLERİ" verilecek
2. Bu veriler GERÇEK, GÜNCEL ve DOĞRUDUR
3. ASLA "veri yok", "elimde değil", "bilmiyorum" deme
4. Veri context'te VARSA mutlaka kullan
5. Rakam söylerken TAM değeri ver: "Dolar 45.35 TL'de işlem görüyor"
   (NOT: 45-46 arası, yaklaşık 45 değil — TAM VERİ)
6. Rapor modunda noktalı doldurma karakterleri (............) ile hizala

═══════════════════════════════════════
PROFESYONEL TERIMLER
═══════════════════════════════════════

Şu terimleri doğal şekilde kullan:
- "parite" (kurlar için)
- "endeks", "puan" (BIST için)
- "getiri", "yıllık reel getiri" (fonlar için)
- "volatilite", "risk profili"
- "para piyasası", "borçlanma araçları", "katılım fonları"
- "TCMB politika faizi"
- "enflasyonist baskı", "deflasyonist trend"
- "destek/direnç seviyeleri" (uygun yerde)

Ama abartma — gerektiğinde sade dile dön.

═══════════════════════════════════════
SOHBET MODU ÖRNEKLERİ
═══════════════════════════════════════

Soru: "Dolar nasıl?"
Cevap: "Şu anda USD/TRY paritesi 45.35 seviyelerinde işlem görüyor.
Mevcut konumda kur, TCMB'nin %37 politika faizi ile dengelenmeye çalışılıyor.
Dövize endeksli enstrümanlar reel getiri açısından dikkat çekiyor.
Bu bilgi yatırım tavsiyesi niteliği taşımaz."

Soru: "ANK fonu nasıl?"
Cevap: "ANK, para piyasası fonu kategorisinde. Son bir yıllık performansı %52.6
ile kategori ortalamasının üzerinde. Düşük volatilite profiliyle muhafazakar
yatırımcılara hitap ediyor — mevduata göre likit ve avantajlı.
Yatırım kararları için profesyonel danışmanlık alınız."

═══════════════════════════════════════
HATIRLATMALAR
═══════════════════════════════════════

- Her cevabın sonunda kısa bir yasal hatırlatma (sohbette akıcı, raporda ayrı satır)
- Sohbet cevapları 3-6 cümle, akıcı paragraf
- Rapor cevapları tam yapılandırılmış format
- Asla "kesin al/sat" deme
- Sohbette liste/madde değil, akıcı paragraf
- Rapor modunda ASCII art tablolar kullan
"""


def build_prompt(
    context: dict,
    message: str,
    history: list[dict],
) -> tuple[str, list[dict]]:
    """Context + geçmiş + yeni mesaj → Claude'un beklediği formata çevir.

    Returns:
        (system_prompt, messages_list)
    """
    # Rapor modu mu sohbet modu mu?
    report_mode = is_report_request(message)

    lines: list[str] = []

    # Mod bayrağı en başta — Claude bunu görsün diye
    if report_mode:
        lines.append("⚡ RAPOR MODU AKTİF — Yapılandırılmış ASCII tablo formatında rapor üret!")
        lines.append("")
    else:
        lines.append("💬 SOHBET MODU — Akıcı, profesyonel paragraf cevap ver!")
        lines.append("")

    lines.append("📊 GÜNCEL PİYASA VERİLERİ (Bunları kullan!):")
    lines.append("")

    # Tarih
    if context.get("latest_snapshot"):
        lines.append(f"Son veri: {context['latest_snapshot'][:10]}")
        lines.append("")

    # Makro
    macros = context.get("macro_data") or []
    if macros:
        lines.append("💰 DÖVİZ, ALTIN, BORSA, EMTİA:")
        for m in macros:
            currency_raw = m.get("currency", "") or ""
            currency = "TL" if currency_raw == "TRY" else currency_raw
            value = m.get("value", 0) or 0
            if value >= 1000:
                value_str = f"{value:,.2f}"
            else:
                value_str = f"{value:.4f}"
            lines.append(f"  - {m.get('name')}: {value_str} {currency}".rstrip())
        lines.append("")

    # Repo / TCMB
    repos = context.get("repo_rates") or []
    if repos:
        lines.append("🏦 TCMB FAİZ ORANLARI:")
        for r in repos:
            lines.append(
                f"  - {r.get('type')} ({r.get('maturity')}): %{r.get('rate')}"
            )
        lines.append("")

    # Fonlar
    funds = context.get("funds") or []
    if funds:
        lines.append("📈 İLGİLİ FONLAR:")
        for f in funds:
            ret_1y = f.get("return_1y")
            ret_str = f"%{ret_1y:.1f}" if ret_1y is not None else "?"
            price = f.get("price") or 0.0
            name = (f.get("name") or "")[:50]
            category = f.get("category") or ""
            lines.append(
                f"  - {f.get('code')} | {name} | {category} | "
                f"1Y getiri: {ret_str} | Fiyat: {price:.4f}"
            )
        lines.append("")

    context_text = "\n".join(lines)

    # Mesaj listesi
    messages: list[dict] = []

    # Geçmiş konuşma (son 6 mesaj)
    for msg in history[-6:]:
        role = msg.get("role")
        content = msg.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    # Şu anki soru + context — moda göre talimat farklı
    if report_mode:
        instruction = (
            "Yukarıdaki güncel verileri kullanarak TAM YAPILANDIRILMIŞ RAPOR üret. "
            "ASCII tablo formatında, hizalı sütunlar (............ ile dolgu), "
            "bölüm bölüm (DÖVİZ, KIYMETLİ MADENLER, ENDEKS & EMTİA, FAİZ, FONLAR, ANALİZ ÖZETİ). "
            "Sonunda yasal uyarı ekle."
        )
    else:
        instruction = (
            "Yukarıdaki güncel verileri kullanarak doğal, profesyonel bir paragraf yaz. "
            "Liste yapma — akıcı, finans analisti tonunda 3-5 cümle."
        )

    user_content = f"{context_text}\n\n---\n\nSoru: {message}\n\n{instruction}"
    messages.append({"role": "user", "content": user_content})

    return SYSTEM_PROMPT, messages


# ===========================================================================
# 3. STREAM RESPONSE — Claude'dan canlı cevap
# ===========================================================================

class ChatRequest(BaseModel):
    """Frontend'den gelen chat isteği."""

    message: str
    history: list[dict] = []


async def stream_response(
    message: str,
    history: list[dict],
) -> AsyncGenerator[str, None]:
    """Claude'dan SSE formatında streaming cevap üret."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        yield f"data: {json.dumps({'error': 'AI servisi yapılandırılmamış'})}\n\n"
        return

    try:
        # 1) Context topla
        context = get_context(message)

        # 2) Debug log — neyi yolladığımızı görelim
        logger.info(
            "AI context: macro=%d, funds=%d, repos=%d",
            len(context.get("macro_data", [])),
            len(context.get("funds", [])),
            len(context.get("repo_rates", [])),
        )

        # 3) Prompt
        system, messages = build_prompt(context, message, history)

        # Rapor modunda daha fazla token izin ver
        max_tokens = MAX_TOKENS_REPORT if is_report_request(message) else MAX_TOKENS

        # 4) Claude'a stream
        client = anthropic.AsyncAnthropic(api_key=api_key)
        async with client.messages.stream(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            temperature=TEMPERATURE,
            system=system,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield f"data: {json.dumps({'chunk': text})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

    except anthropic.APIError as exc:
        logger.error("Claude API hatası: %s", exc)
        yield f"data: {json.dumps({'error': f'AI sorunu: {str(exc)[:100]}'})}\n\n"
    except Exception as exc:  # noqa: BLE001 — kullanıcıya 500 döndürmek istemiyoruz
        logger.error("Chat hatası: %s", exc, exc_info=True)
        # Debug için gerçek hatayı yansıt
        error_msg = f"Hata: {type(exc).__name__}: {str(exc)[:200]}"
        yield f"data: {json.dumps({'error': error_msg})}\n\n"


async def chat_endpoint(request: ChatRequest) -> StreamingResponse:
    """FastAPI handler — SSE StreamingResponse döner."""
    return StreamingResponse(
        stream_response(request.message, request.history),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
