"""TCMB collector testleri.

TCMB collector artık EVDS API yerine TCMB ana sayfasından scraping ile
çalışıyor. Hata durumunda exception fırlatmıyor; boş/fallback liste döner.
"""
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from kizilelma.collectors.tcmb import TcmbCollector
from kizilelma.models import RepoRate


FIXTURE = Path(__file__).parent.parent / "fixtures" / "tcmb_page.html"


@pytest.fixture
def tcmb_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


@respx.mock
@pytest.mark.asyncio
async def test_tcmb_fetch_returns_repo_rates(tcmb_html):
    """TCMB ana sayfasından 3 repo oranı da doğru çekilir."""
    respx.get("https://www.tcmb.gov.tr/").mock(
        return_value=httpx.Response(200, text=tcmb_html)
    )

    collector = TcmbCollector()
    rates = await collector.fetch()

    # En az 1 oran dönmeli, ideal olarak 3
    assert len(rates) >= 1
    assert all(isinstance(r, RepoRate) for r in rates)

    # Fixture'daki 3 oran da yakalanmış olmalı
    assert len(rates) == 3

    by_key = {(r.type, r.maturity): r.rate for r in rates}
    assert by_key[("repo", "1w")] == Decimal("37")
    assert by_key[("repo", "overnight")] == Decimal("40")
    assert by_key[("ters_repo", "overnight")] == Decimal("35.5")


@respx.mock
@pytest.mark.asyncio
async def test_tcmb_returns_fallback_on_failure():
    """Sayfa 500 hata verirse exception fırlatmaz, fallback döner."""
    respx.get("https://www.tcmb.gov.tr/").mock(
        return_value=httpx.Response(500)
    )

    collector = TcmbCollector()
    rates = await collector.fetch()

    # Exception atılmamalı; fallback olarak tek politika faizi dönmeli
    assert isinstance(rates, list)
    # Fallback en az bir RepoRate üretir ki downstream kod kırılmasın
    assert len(rates) >= 1
    assert all(isinstance(r, RepoRate) for r in rates)


@respx.mock
@pytest.mark.asyncio
async def test_tcmb_backward_compatible_api_key_arg():
    """Geriye dönük uyumluluk: api_key parametresi kabul edilmeli."""
    respx.get("https://www.tcmb.gov.tr/").mock(
        return_value=httpx.Response(200, text="<html></html>")
    )
    # api_key verilmesi patlamamalı
    collector = TcmbCollector(api_key="eski_anahtar")
    rates = await collector.fetch()
    assert isinstance(rates, list)
