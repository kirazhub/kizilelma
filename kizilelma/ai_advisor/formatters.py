"""Veri odaklı rapor formatter'ları.

Hikaye/yorum YOK. Saf tablo/liste. Kullanıcı ham veriyi istiyor:
"hangi fon ne kadar veriyor, hangi araç ne kadar kazandırıyor".

Tüm tablolar Telegram'ın sade metin (parse_mode olmadan) akışı için
hazırlanmıştır. Sabit genişlikli (monospace) görünüm hedeflenmez;
kullanıcı mobil ekranda okuyacağı için "satır başına tek fon" + dikey
hizalamak yerine "anahtar: değer" stilinde kompakt format tercih edilmiştir.
"""
from decimal import Decimal
from typing import Optional

from kizilelma.models import (
    BondData,
    EurobondData,
    FundData,
    RepoRate,
    SukukData,
)


def _fmt_pct(value: Optional[Decimal]) -> str:
    """Getiri yüzdesini tek satırda biçimlendir."""
    if value is None:
        return "—"
    try:
        return f"%{float(value):+.1f}"
    except (TypeError, ValueError):
        return "—"


def _fmt_price(value: Optional[Decimal], decimals: int = 4) -> str:
    """Fiyatı biçimlendir."""
    if value is None:
        return "—"
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return "—"


def _truncate(text: str, max_len: int = 38) -> str:
    """Uzun isimleri kısalt."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _tr_upper(text: str) -> str:
    """Türkçe uyumlu büyük harf dönüşümü.

    Python'un varsayılan ``.upper()`` metodu "i" harfini noktasız "I" yapar;
    bu Türkçe için yanlıştır. ``i → İ`` ve ``ı → I`` dönüşümünü elle uygular.
    """
    return text.translate(str.maketrans("iı", "İI")).upper()


def format_funds_by_category(
    funds: list[FundData],
    category_name: str,
    emoji: str,
    limit: int = 10,
) -> str:
    """Bir kategori için fon listesi.

    Mobil için optimize: her fon 3 satır (etiketi olanlar için).
      Satır 1: sıra. KOD — Fon adı
      Satır 2: Fiyat | 1G | 1A | 3A | 6A | 1Y
      Satır 3: 🏷️ Etiket1 · Etiket2 · ... (varsa)
    """
    header = f"{emoji} {_tr_upper(category_name)} — EN İYİ {limit}"

    if not funds:
        return f"{header}\n\nBugün bu kategoride veri alınamadı."

    lines = [header, ""]
    for i, f in enumerate(funds[:limit], start=1):
        name = _truncate(f.name, 50)
        lines.append(f"{i:>2}. {f.code} — {name}")
        lines.append(
            f"    Fiyat: {_fmt_price(f.price)} TL | "
            f"1G: {_fmt_pct(f.return_1d)} | "
            f"1A: {_fmt_pct(f.return_1m)} | "
            f"3A: {_fmt_pct(f.return_3m)} | "
            f"6A: {_fmt_pct(f.return_6m)} | "
            f"1Y: {_fmt_pct(f.return_1y)}"
        )
        # Etiket satırı (varsa)
        if f.asset_tags:
            tags_str = " · ".join(f.asset_tags)
            lines.append(f"    🏷️ {tags_str}")
        lines.append("")  # Fonlar arası boşluk

    return "\n".join(lines).rstrip()


def format_bonds(bonds: list[BondData], limit: int = 10) -> str:
    """DİBS listesi."""
    header = f"🏛️ DEVLET TAHVİLLERİ (DİBS) — EN YÜKSEK GETİRİ {limit}"

    if not bonds:
        return f"{header}\n\nBugün veri alınamadı."

    sorted_bonds = sorted(bonds, key=lambda b: b.yield_rate, reverse=True)
    lines = [header, ""]

    for i, b in enumerate(sorted_bonds[:limit], start=1):
        kupon = (
            f"%{float(b.coupon_rate):.2f}" if b.coupon_rate is not None else "—"
        )
        lines.append(f"{i:>2}. {b.isin}")
        lines.append(
            f"    Vade: {b.maturity_date.strftime('%d.%m.%Y')} | "
            f"Getiri: %{float(b.yield_rate):.2f} | "
            f"Fiyat: {float(b.price):.2f} | "
            f"Kupon: {kupon}"
        )
        lines.append("")

    return "\n".join(lines).rstrip()


def format_sukuks(sukuks: list[SukukData], limit: int = 10) -> str:
    """Sukuk (kira sertifikası) listesi."""
    header = f"🕌 KİRA SERTİFİKALARI (SUKUK) — EN YÜKSEK GETİRİ {limit}"

    if not sukuks:
        return f"{header}\n\nBugün veri alınamadı."

    sorted_sukuks = sorted(sukuks, key=lambda s: s.yield_rate, reverse=True)
    lines = [header, ""]

    for i, s in enumerate(sorted_sukuks[:limit], start=1):
        lines.append(f"{i:>2}. {s.isin} — {_truncate(s.issuer, 40)}")
        lines.append(
            f"    Vade: {s.maturity_date.strftime('%d.%m.%Y')} | "
            f"Getiri: %{float(s.yield_rate):.2f} | "
            f"Fiyat: {float(s.price):.2f}"
        )
        lines.append("")

    return "\n".join(lines).rstrip()


def format_eurobonds(eurobonds: list[EurobondData], limit: int = 10) -> str:
    """Eurobond listesi."""
    header = f"🌍 TÜRKİYE EUROBONDLARI — EN YÜKSEK GETİRİ {limit}"

    if not eurobonds:
        return f"{header}\n\nBugün veri alınamadı."

    sorted_eb = sorted(eurobonds, key=lambda e: e.yield_rate, reverse=True)
    lines = [header, ""]

    for i, e in enumerate(sorted_eb[:limit], start=1):
        lines.append(f"{i:>2}. {e.isin} ({e.currency})")
        lines.append(
            f"    Vade: {e.maturity_date.strftime('%d.%m.%Y')} | "
            f"Getiri: %{float(e.yield_rate):.2f} | "
            f"Fiyat: {float(e.price):.2f}"
        )
        lines.append("")

    return "\n".join(lines).rstrip()


def format_repo_rates(rates: list[RepoRate]) -> str:
    """TCMB ve repo oranları."""
    header = "🔄 TCMB POLİTİKA FAİZİ / REPO ORANLARI"

    if not rates:
        return f"{header}\n\nBugün veri alınamadı."

    lines = [header, ""]
    for r in rates:
        tur = r.type.replace("_", " ").title()
        lines.append(
            f"• {tur} ({r.maturity}): %{float(r.rate):.2f}  —  "
            f"{r.date.strftime('%d.%m.%Y')}"
        )

    return "\n".join(lines)


def format_top_picks(
    funds: list[FundData],
    bonds: list[BondData],
    sukuks: list[SukukData],
    eurobonds: list[EurobondData],
    limit: int = 15,
) -> str:
    """Tüm kaynaklardan en yüksek getirili enstrümanlar tek listede.

    Fonlar için 1 yıllık getiri, DİBS/Sukuk/Eurobond için yield_rate kullanılır.
    """
    header = f"🎯 GÜNÜN EN İYİ GETİRİ SIRALAMASI (TOP {limit})"
    items: list[tuple[str, str, Decimal, str]] = []

    for f in funds:
        if f.return_1y is not None and f.return_1y > 0:
            # Kategori çok uzunsa kısalt
            cat = _truncate(f.category, 28)
            items.append((f.code, f"Fon · {cat}", f.return_1y, "Fon"))

    for b in bonds:
        items.append((b.isin, "DİBS (Devlet Tahvili)", b.yield_rate, "Tahvil"))

    for s in sukuks:
        items.append((s.isin, f"Sukuk · {_truncate(s.issuer, 20)}", s.yield_rate, "Sukuk"))

    for e in eurobonds:
        items.append((e.isin, f"Eurobond {e.currency}", e.yield_rate, "Eurobond"))

    if not items:
        return f"{header}\n\nBugün karşılaştırılabilir veri yok."

    items.sort(key=lambda x: x[2], reverse=True)
    lines = [header, ""]

    for i, (code, category, rate, tip) in enumerate(items[:limit], start=1):
        lines.append(f"{i:>2}. {code} — %{float(rate):.2f}")
        lines.append(f"    {category}  [{tip}]")
        lines.append("")

    return "\n".join(lines).rstrip()
