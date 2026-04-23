"""Eurobond collector testleri."""
import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from kizilelma.collectors.eurobond import EurobondCollector
from kizilelma.models import EurobondData


FIXTURE = Path(__file__).parent.parent / "fixtures" / "eurobond_response.json"


@respx.mock
@pytest.mark.asyncio
async def test_eurobond_fetches_data():
    """Eurobond verisi çekilebilir."""
    data = json.loads(FIXTURE.read_text())
    respx.get(url__regex=r".*eurobond.*").mock(
        return_value=httpx.Response(200, json=data)
    )

    collector = EurobondCollector(url="https://api.example.com/eurobond")
    bonds = await collector.fetch()

    assert len(bonds) == 2
    assert all(isinstance(b, EurobondData) for b in bonds)
    assert bonds[0].currency == "USD"
    assert bonds[0].yield_rate == Decimal("7.85")


@respx.mock
@pytest.mark.asyncio
async def test_eurobond_returns_empty_on_failure():
    """Hata durumunda boş liste döner."""
    respx.get(url__regex=r".*").mock(
        return_value=httpx.Response(500)
    )
    collector = EurobondCollector(url="https://api.example.com/eurobond")
    bonds = await collector.fetch()
    assert bonds == []
