"""BIST collector testleri."""
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from kizilelma.collectors.bist import BistCollector
from kizilelma.models import BondData, SukukData


FIXTURE_DIBS = Path(__file__).parent.parent / "fixtures" / "bist_dibs.html"


@respx.mock
@pytest.mark.asyncio
async def test_bist_fetches_dibs_and_sukuk():
    """BIST'ten DİBS ve sukuk verileri çekilir."""
    html = FIXTURE_DIBS.read_text()
    respx.get(url__regex=r".*bond.*").mock(
        return_value=httpx.Response(200, text=html)
    )
    respx.get(url__regex=r".*sukuk.*").mock(
        return_value=httpx.Response(200, text=html)
    )

    collector = BistCollector()
    bonds, sukuks = await collector.fetch()

    assert len(bonds) >= 2
    assert all(isinstance(b, BondData) for b in bonds)
    assert bonds[0].isin == "TRT191028T18"
    assert bonds[0].yield_rate == Decimal("42.50")


@respx.mock
@pytest.mark.asyncio
async def test_bist_returns_empty_on_failure_not_raises():
    """BIST scraping başarısız olursa boş liste döner."""
    respx.get(url__regex=r".*").mock(
        return_value=httpx.Response(500)
    )

    collector = BistCollector()
    bonds, sukuks = await collector.fetch()

    assert bonds == []
    assert sukuks == []
