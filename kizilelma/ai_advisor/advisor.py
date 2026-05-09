"""Advisor — veri odaklı rapor üreticisi.

Eskiden Claude API ile hikâye/yorum üretiyordu. Kullanıcı talebi gereği
artık TAMAMEN VERİ ODAKLI çalışıyor: her kategoriden en iyi 10 araç,
özellikleriyle birlikte saf tablo/liste olarak listelenir.

- Haber bölümü YOK (kullanıcı istemedi)
- Profil bazlı öneri (muhafazakar/dengeli/agresif) YOK
- AI çağrısı YOK (hız + sıfır maliyet)

Sınıf adı geriye dönük uyumluluk için `AIAdvisor` olarak kaldı; fakat
içinde AI çağrısı yoktur. `api_key` parametresi artık opsiyonel.
"""
from dataclasses import dataclass, field
from typing import Optional

from kizilelma.ai_advisor.formatters import (
    format_bonds,
    format_eurobonds,
    format_funds_by_category,
    format_repo_rates,
    format_sukuks,
    format_top_picks,
)
from kizilelma.analyzers.ranker import (
    filter_active_funds,
    filter_qualified,
    top_funds_by_return,
)
from kizilelma.models import FundData, MarketSnapshot


@dataclass
class AdvisorReport:
    """Günlük raporun tüm bölümleri.

    Her alan rapor içinde ayrı bir bölüme karşılık gelir. None olan alanlar
    sunum sırasında atlanır.
    """

    # Fon kategorileri (TOP 10)
    fund_section: Optional[str] = None          # Para Piyasası
    hisse_section: Optional[str] = None         # Hisse
    karma_section: Optional[str] = None         # Karma/Değişken
    serbest_fund_section: Optional[str] = None  # Serbest / Nitelikli
    katilim_section: Optional[str] = None       # Katılım
    borc_section: Optional[str] = None          # Borçlanma/Tahvil fonları

    # Sabit getirili araçlar
    bond_section: Optional[str] = None          # DİBS
    sukuk_section: Optional[str] = None         # Sukuk
    eurobond_section: Optional[str] = None      # Eurobond
    repo_section: Optional[str] = None          # TCMB/Repo

    # Çapraz karşılaştırma
    summary_section: Optional[str] = None       # Günün Zirveleri

    # Geriye dönük uyumluluk (kullanılmıyor — her zaman None)
    news_section: Optional[str] = None

    errors: list[str] = field(default_factory=list)


def _match_category(fund: FundData, keywords: list[str]) -> bool:
    """Fon kategorisi anahtar kelimelerden birini içeriyor mu?"""
    cat = fund.category.lower()
    return any(k in cat for k in keywords)


class AIAdvisor:
    """Veri odaklı rapor üreticisi.

    Adı geriye dönük uyumluluk için korunmuştur; AI çağrısı yapmaz.
    """

    def __init__(
        self, api_key: Optional[str] = None, model: Optional[str] = None
    ) -> None:
        # Parametreler geriye dönük uyumluluk için tutuluyor, kullanılmıyor.
        self.api_key = api_key
        self.model = model

    async def generate_report(self, snapshot: MarketSnapshot) -> AdvisorReport:
        """Tüm bölümleri veri tabloları olarak üret (AI yok)."""
        report = AdvisorReport()

        try:
            # Önce TEFAS'ta aktif işlem görmeyen (fiyatı eski / tüm getirileri
            # 0 olan) fonları ele — rapor temizliği için kritik.
            active_funds = filter_active_funds(snapshot.funds)
            standart_funds, serbest_funds = filter_qualified(active_funds)

            # Kategori eşleşmeleri — Türkçe/İngilizce ve küçük harf farklarını
            # karşılamak için birden çok anahtar kelime kullanılıyor.
            para_piyasasi = [
                f for f in standart_funds
                if _match_category(f, ["para piyas", "likit", "kısa vadeli"])
            ]
            hisse = [
                f for f in standart_funds
                if _match_category(f, ["hisse", "equity"])
            ]
            karma = [
                f for f in standart_funds
                if _match_category(f, ["karma", "değişken", "degisken", "fon sepeti"])
            ]
            katilim = [
                f for f in active_funds  # Katılım hem standart hem serbest olabilir
                if _match_category(f, ["katılım", "katilim"])
            ]
            borc = [
                f for f in standart_funds
                if _match_category(f, ["borç", "borclanma", "tahvil", "bono"])
            ]

            # Her kategori için 1Y getiriye göre TOP 10
            report.fund_section = format_funds_by_category(
                top_funds_by_return(para_piyasasi, "return_1y", limit=10),
                "Para Piyasası Fonları",
                "📊",
            )
            report.hisse_section = format_funds_by_category(
                top_funds_by_return(hisse, "return_1y", limit=10),
                "Hisse Senedi Fonları",
                "📈",
            )
            report.karma_section = format_funds_by_category(
                top_funds_by_return(karma, "return_1y", limit=10),
                "Karma / Değişken Fonlar",
                "🎯",
            )
            report.serbest_fund_section = format_funds_by_category(
                top_funds_by_return(serbest_funds, "return_1y", limit=10),
                "Serbest (Nitelikli) Fonlar",
                "💎",
            )
            report.katilim_section = format_funds_by_category(
                top_funds_by_return(katilim, "return_1y", limit=10),
                "Katılım Fonları",
                "🕌",
            )
            report.borc_section = format_funds_by_category(
                top_funds_by_return(borc, "return_1y", limit=10),
                "Borçlanma / Tahvil Fonları",
                "📜",
            )

            # Sabit getirili
            report.bond_section = format_bonds(snapshot.bonds)
            report.sukuk_section = format_sukuks(snapshot.sukuks)
            report.eurobond_section = format_eurobonds(snapshot.eurobonds)
            report.repo_section = format_repo_rates(snapshot.repo_rates)

            # Çapraz karşılaştırma
            report.summary_section = format_top_picks(
                snapshot.funds,
                snapshot.bonds,
                snapshot.sukuks,
                snapshot.eurobonds,
            )
        except Exception as exc:  # defansif: tek seferde asla çökmesin
            report.errors.append(f"generate_report: {exc}")

        # Haber bölümü artık kullanılmıyor (kullanıcı istemedi)
        report.news_section = None

        return report
