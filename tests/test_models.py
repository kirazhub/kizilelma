"""Veri modellerinin test edilmesi."""
from datetime import date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from kizilelma.models import (
    FundData,
    BondData,
    SukukData,
    RepoRate,
    EurobondData,
    NewsItem,
    MarketSnapshot,
)


def test_fund_data_creates_with_valid_fields():
    """Geçerli alanlarla fon verisi oluşur."""
    fund = FundData(
        code="AFA",
        name="Ak Portföy Para Piyasası Fonu",
        category="Para Piyasası",
        price=Decimal("1.234567"),
        date=date(2026, 4, 23),
        return_1d=Decimal("0.15"),
        return_1m=Decimal("4.20"),
        return_1y=Decimal("48.50"),
    )
    assert fund.code == "AFA"
    assert fund.return_1y == Decimal("48.50")


def test_fund_data_rejects_invalid_price():
    """Negatif fiyat reddedilir."""
    with pytest.raises(ValidationError):
        FundData(
            code="AFA",
            name="Test",
            category="Test",
            price=Decimal("-1"),
            date=date.today(),
        )


def test_news_item_requires_title_and_url():
    """Haber başlık ve URL zorunlu."""
    news = NewsItem(
        title="TCMB faiz kararını açıkladı",
        url="https://example.com/haber",
        source="AA Ekonomi",
        published=datetime(2026, 4, 23, 9, 0),
    )
    assert news.title.startswith("TCMB")


def test_market_snapshot_aggregates_all_data():
    """MarketSnapshot tüm veri tiplerini bir araya getirir."""
    snapshot = MarketSnapshot(
        timestamp=datetime(2026, 4, 23, 10, 0),
        funds=[],
        bonds=[],
        sukuks=[],
        repo_rates=[],
        eurobonds=[],
        news=[],
    )
    assert snapshot.timestamp.hour == 10
