"""TEFAS collector testleri.

Gerçek ağ çağrısı yapılmaması için ``tefas.Crawler`` yerine sahte bir
``crawler_factory`` enjekte ediyoruz.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pandas as pd
import pytest

from kizilelma.collectors.base import CollectorError
from kizilelma.collectors.tefas import TefasCollector
from kizilelma.models import FundData


def _make_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """tefas.Crawler.fetch() çıktısını taklit eden bir DataFrame kurar."""
    return pd.DataFrame(
        rows,
        columns=["date", "code", "title", "price", "market_cap"],
    )


class _FakeCrawler:
    """tefas.Crawler'ı taklit eden sahte sınıf."""

    def __init__(self, responses: list[pd.DataFrame] | Exception) -> None:
        self._responses = responses
        self.calls: list[dict[str, Any]] = []

    def fetch(
        self,
        start: str,
        end: str | None = None,
        columns: list[str] | None = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        self.calls.append({"start": start, "end": end, "columns": columns})
        if isinstance(self._responses, Exception):
            raise self._responses
        if not self._responses:
            return _make_dataframe([])
        return self._responses.pop(0)


@pytest.fixture
def sample_rows() -> list[dict[str, Any]]:
    return [
        {
            "date": "2026-04-22",
            "code": "AFA",
            "title": "Ak Portföy Para Piyasası Fonu",
            "price": 1.234567,
            "market_cap": 1_000_000.0,
        },
        {
            "date": "2026-04-22",
            "code": "TGE",
            "title": "Test Serbest Fonu (Nitelikli Yatırımcıya)",
            "price": 5.678901,
            "market_cap": 250_000.0,
        },
    ]


@pytest.mark.asyncio
async def test_tefas_fetch_returns_fund_list(sample_rows):
    """TEFAS'tan (mocklanmış) fon listesi çekilebilir ve FundData'ya dönüşür."""
    fake = _FakeCrawler([_make_dataframe(sample_rows)])
    collector = TefasCollector(crawler_factory=lambda: fake)

    funds = await collector.fetch()

    assert len(funds) == 2
    assert all(isinstance(f, FundData) for f in funds)

    afa = next(f for f in funds if f.code == "AFA")
    assert afa.price == Decimal("1.234567")
    assert afa.date == dt.date(2026, 4, 22)
    assert afa.is_qualified_investor is False
    assert "Para Piyasası" in afa.category


@pytest.mark.asyncio
async def test_tefas_marks_serbest_fund_as_qualified(sample_rows):
    """Fon adında 'SERBEST' geçenler nitelikli yatırımcı fonu olarak işaretlenir."""
    fake = _FakeCrawler([_make_dataframe(sample_rows)])
    collector = TefasCollector(crawler_factory=lambda: fake)

    funds = await collector.fetch()

    serbest = next(f for f in funds if f.code == "TGE")
    assert serbest.is_qualified_investor is True
    assert "Serbest" in serbest.category


@pytest.mark.asyncio
async def test_tefas_raises_when_all_lookback_days_empty():
    """Tüm geriye dönük günler boş dönerse CollectorError fırlatılır."""
    fake = _FakeCrawler([])  # her çağrıda boş DataFrame dönecek
    collector = TefasCollector(
        crawler_factory=lambda: fake, max_lookback_days=3
    )

    with pytest.raises(CollectorError) as excinfo:
        await collector.fetch()

    assert "tefas" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_tefas_raises_on_persistent_fetch_error():
    """Crawler sürekli exception atarsa CollectorError fırlatılır."""
    fake = _FakeCrawler(RuntimeError("WAF reddi"))
    collector = TefasCollector(
        crawler_factory=lambda: fake, max_lookback_days=2
    )

    with pytest.raises(CollectorError) as excinfo:
        await collector.fetch()

    assert "WAF reddi" in str(excinfo.value) or "veri çekilemedi" in str(
        excinfo.value
    )


@pytest.mark.asyncio
async def test_tefas_skips_weekend_then_returns_first_available(sample_rows):
    """Hafta sonundaysak TEFAS'ın son iş gününe inilmeli ve dolu DataFrame kullanılmalı."""
    # İlk çağrıda boş, ikinci çağrıda dolu DataFrame dönecek
    fake = _FakeCrawler(
        [_make_dataframe([]), _make_dataframe(sample_rows)]
    )
    collector = TefasCollector(
        crawler_factory=lambda: fake, max_lookback_days=5
    )

    funds = await collector.fetch()
    assert len(funds) == 2
    # En az 2 çağrı yapılmış olmalı (ilk günü boş görünce bir önceki güne geçti)
    assert len(fake.calls) >= 2
