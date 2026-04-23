"""TCMB EVDS collector testleri."""
import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from kizilelma.collectors.tcmb import TcmbCollector
from kizilelma.models import RepoRate


FIXTURE = Path(__file__).parent.parent / "fixtures" / "tcmb_response.json"


@pytest.fixture
def tcmb_response():
    return json.loads(FIXTURE.read_text())


@respx.mock
@pytest.mark.asyncio
async def test_tcmb_fetch_returns_repo_rates(tcmb_response):
    """TCMB EVDS API'sinden repo oranları çekilir."""
    respx.get(url__regex=r"https://evds2\.tcmb\.gov\.tr/service/evds.*").mock(
        return_value=httpx.Response(200, json=tcmb_response)
    )

    collector = TcmbCollector(api_key="test_key")
    rates = await collector.fetch()

    assert len(rates) >= 1
    assert all(isinstance(r, RepoRate) for r in rates)
    rate_values = [r.rate for r in rates]
    assert Decimal("47.5") in rate_values


@respx.mock
@pytest.mark.asyncio
async def test_tcmb_raises_on_error():
    from kizilelma.collectors.base import CollectorError
    respx.get(url__regex=r"https://evds2\.tcmb\.gov\.tr/.*").mock(
        return_value=httpx.Response(500)
    )

    collector = TcmbCollector(api_key="test_key")
    with pytest.raises(CollectorError):
        await collector.fetch()
