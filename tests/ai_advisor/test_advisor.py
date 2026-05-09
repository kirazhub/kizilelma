"""AI Advisor (veri odaklı) testleri.

AI çağrısı yok — doğrudan formatters ile tablolar üretilir.
"""
import datetime as dt
from decimal import Decimal

import pytest

from kizilelma.ai_advisor.advisor import AdvisorReport, AIAdvisor
from kizilelma.models import (
    BondData,
    EurobondData,
    FundData,
    MarketSnapshot,
    RepoRate,
    SukukData,
)


@pytest.fixture
def rich_snapshot():
    """Her kategoriden örnek veri içeren snapshot.

    Not: `filter_active_funds` fonların tarihinin son 7 gün içinde olmasını
    bekler. Bu yüzden fixture'da bugünün tarihini kullanıyoruz, sabit tarih
    değil — yoksa testler zamanla bayatlayıp kırılır.
    """
    today = dt.date.today()
    return MarketSnapshot(
        timestamp=dt.datetime.combine(today, dt.time(10, 0)),
        funds=[
            FundData(
                code="AFA", name="Ak Portföy Para Piyasası",
                category="Para Piyasası Fonu",
                price=Decimal("1.2345"), date=today,
                return_1m=Decimal("4.2"), return_3m=Decimal("12.5"),
                return_6m=Decimal("25.8"), return_1y=Decimal("48.5"),
            ),
            FundData(
                code="TGE", name="Garanti Hisse Senedi Fonu",
                category="Hisse Senedi Fonu",
                price=Decimal("10.55"), date=today,
                return_1m=Decimal("8.1"), return_1y=Decimal("65.2"),
            ),
            FundData(
                code="IPJ", name="İş Portföy Karma Fonu",
                category="Değişken Fon",
                price=Decimal("5.12"), date=today,
                return_1y=Decimal("52.3"),
            ),
            FundData(
                code="ZPK", name="Ziraat Katılım Kira Sertifikası",
                category="Katılım Fonu",
                price=Decimal("2.10"), date=today,
                return_1y=Decimal("38.9"),
            ),
            FundData(
                code="YAS", name="Serbest Test Fonu",
                category="Serbest Fon",
                price=Decimal("100.0"), date=today,
                return_1y=Decimal("82.0"),
                is_qualified_investor=True,
            ),
            FundData(
                code="BRC", name="Borçlanma Araçları Fonu",
                category="Borçlanma Araçları Fonu",
                price=Decimal("3.0"), date=today,
                return_1y=Decimal("42.1"),
            ),
        ],
        bonds=[
            BondData(
                isin="TRT050729T15", maturity_date=dt.date(2029, 7, 5),
                yield_rate=Decimal("38.5"), price=Decimal("92.30"),
                coupon_rate=Decimal("25.0"), date=today,
            ),
        ],
        sukuks=[
            SukukData(
                isin="TRD080726K10", issuer="Hazine",
                maturity_date=dt.date(2026, 7, 8),
                yield_rate=Decimal("35.1"), price=Decimal("98.50"),
                date=today,
            ),
        ],
        repo_rates=[
            RepoRate(type="repo", maturity="overnight",
                     rate=Decimal("45.0"), date=today),
        ],
        eurobonds=[
            EurobondData(
                isin="US900123CK58", maturity_date=dt.date(2030, 3, 1),
                currency="USD", yield_rate=Decimal("7.8"),
                price=Decimal("95.10"), date=today,
            ),
        ],
        news=[],
    )


@pytest.mark.asyncio
async def test_advisor_generates_all_sections(rich_snapshot):
    """Advisor tüm bölümleri veri tablosu olarak üretir (AI çağrısı yok)."""
    advisor = AIAdvisor()  # api_key'siz de çalışmalı
    report = await advisor.generate_report(rich_snapshot)

    assert isinstance(report, AdvisorReport)
    assert report.errors == []

    # Fon kategorileri dolu
    assert report.fund_section and "AFA" in report.fund_section
    assert report.hisse_section and "TGE" in report.hisse_section
    assert report.karma_section and "IPJ" in report.karma_section
    assert report.serbest_fund_section and "YAS" in report.serbest_fund_section
    assert report.katilim_section and "ZPK" in report.katilim_section
    assert report.borc_section and "BRC" in report.borc_section

    # Sabit getirili
    assert report.bond_section and "TRT050729T15" in report.bond_section
    assert report.sukuk_section and "TRD080726K10" in report.sukuk_section
    assert report.eurobond_section and "US900123CK58" in report.eurobond_section
    assert report.repo_section and "Repo" in report.repo_section

    # Çapraz karşılaştırma
    assert report.summary_section
    assert "GÜNÜN EN İYİ" in report.summary_section

    # Haber bölümü artık kullanılmıyor
    assert report.news_section is None


@pytest.mark.asyncio
async def test_advisor_handles_empty_snapshot():
    """Veri yoksa bölümlerde 'veri alınamadı' mesajı olur ama hata çıkmaz."""
    empty = MarketSnapshot(
        timestamp=dt.datetime(2026, 4, 23, 10, 0),
        funds=[], bonds=[], sukuks=[], repo_rates=[],
        eurobonds=[], news=[],
    )
    advisor = AIAdvisor()
    report = await advisor.generate_report(empty)

    assert report.errors == []
    # Her bölüm tanımlı (None değil), içeriğinde uyarı var
    assert report.fund_section and "veri alınamadı" in report.fund_section.lower()
    assert report.bond_section and "veri alınamadı" in report.bond_section.lower()


@pytest.mark.asyncio
async def test_advisor_no_ai_call(rich_snapshot):
    """AIAdvisor artık anthropic import'u yapmıyor / çağırmıyor."""
    # Anthropic yüklü olmasa bile çalışmalı — minimal varsayım: import hatası yok.
    advisor = AIAdvisor(api_key="unused-key")
    report = await advisor.generate_report(rich_snapshot)
    assert report.errors == []
    # En az bir bölümde gerçek veri (fon kodu) var — AI üretimi değil
    assert "AFA" in (report.fund_section or "")
