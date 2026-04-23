"""TEFAS collector testleri."""
import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from kizilelma.collectors.tefas import TefasCollector
from kizilelma.models import FundData


FIXTURE = Path(__file__).parent.parent / "fixtures" / "tefas_response.json"


@pytest.fixture
def tefas_response():
    return json.loads(FIXTURE.read_text())


@respx.mock
@pytest.mark.asyncio
async def test_tefas_fetch_returns_fund_list(tefas_response):
    """TEFAS API'sinden fon listesi çekilebilir."""
    respx.post("https://www.tefas.gov.tr/api/DB/BindHistoryInfo").mock(
        return_value=httpx.Response(200, json=tefas_response)
    )

    collector = TefasCollector()
    funds = await collector.fetch()

    assert len(funds) == 2
    assert all(isinstance(f, FundData) for f in funds)
    assert funds[0].code == "AFA"
    assert funds[0].price == Decimal("1.234567")
    assert funds[0].return_1y == Decimal("48.50")
    assert funds[0].is_qualified_investor is False


@respx.mock
@pytest.mark.asyncio
async def test_tefas_marks_serbest_fund_as_qualified(tefas_response):
    """Serbest fonlar nitelikli yatırımcı bayrağıyla işaretlenir."""
    respx.post("https://www.tefas.gov.tr/api/DB/BindHistoryInfo").mock(
        return_value=httpx.Response(200, json=tefas_response)
    )

    collector = TefasCollector()
    funds = await collector.fetch()

    serbest = next(f for f in funds if f.code == "TGE")
    assert serbest.is_qualified_investor is True
    assert "Serbest" in serbest.category


@respx.mock
@pytest.mark.asyncio
async def test_tefas_raises_on_http_error():
    """HTTP hatası CollectorError olarak fırlatılır."""
    from kizilelma.collectors.base import CollectorError

    respx.post("https://www.tefas.gov.tr/api/DB/BindHistoryInfo").mock(
        return_value=httpx.Response(500)
    )

    collector = TefasCollector()
    with pytest.raises(CollectorError):
        await collector.fetch()
