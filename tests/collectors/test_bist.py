"""BIST collector testleri."""
import datetime as dt
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
    """BIST'ten DİBS ve sukuk verileri çekilir, ISIN'den vade çıkarılır."""
    html = FIXTURE_DIBS.read_text()
    # Yeni kaynak tek URL; collector her iki veri tipi için de aynı sayfayı çeker
    respx.get(url__regex=r".*uzmanpara.*|.*tahvil-bono.*").mock(
        return_value=httpx.Response(200, text=html)
    )

    collector = BistCollector()
    bonds, sukuks = await collector.fetch()

    # Fixture'da 3 DİBS (2 TRT + 1 TRB) ve 2 sukuk (TRD) var
    assert len(bonds) >= 2
    assert all(isinstance(b, BondData) for b in bonds)
    assert len(sukuks) >= 2
    assert all(isinstance(s, SukukData) for s in sukuks)

    # ISIN ve getiri doğru parse edilmeli
    isins = {b.isin for b in bonds}
    assert "TRT191028T18" in isins
    trt = next(b for b in bonds if b.isin == "TRT191028T18")
    assert trt.yield_rate == Decimal("42.50")
    # Vade tarihi ISIN'den türetilir: 19/10/2028
    assert trt.maturity_date == dt.date(2028, 10, 19)

    # Sukuk kontrolü: TRD061027T33 → 06/10/2027
    sukuk_isins = {s.isin for s in sukuks}
    assert "TRD061027T33" in sukuk_isins
    trd = next(s for s in sukuks if s.isin == "TRD061027T33")
    assert trd.maturity_date == dt.date(2027, 10, 6)
    assert trd.issuer == "Hazine"

    # Şirket tahvili (TRPTMK...) atlanmış olmalı
    assert not any(b.isin.startswith("TRPTMK") for b in bonds)


@respx.mock
@pytest.mark.asyncio
async def test_bist_returns_fallback_on_failure_not_raises():
    """BIST scraping 500 dönerse fallback veri seti kullanılır, exception atılmaz."""
    respx.get(url__regex=r".*").mock(return_value=httpx.Response(500))

    collector = BistCollector()
    bonds, sukuks = await collector.fetch()

    # Fallback devrede: boş değil ama hata da atmıyor
    assert isinstance(bonds, list)
    assert isinstance(sukuks, list)
    assert all(isinstance(b, BondData) for b in bonds)
    assert all(isinstance(s, SukukData) for s in sukuks)
    # Fallback en az 3 tahvil + 3 sukuk garanti ediyor
    assert len(bonds) >= 3
    assert len(sukuks) >= 3
