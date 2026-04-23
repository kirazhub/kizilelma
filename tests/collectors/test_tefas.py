"""TEFAS collector testleri.

Gerçek ağ çağrısı yapılmaması için ``respx`` ile TEFAS resmi API'sini
mock'luyoruz. Eski sürüm tefas-crawler'ın DataFrame'lerini mock'luyordu;
bu sürüm doğrudan ``https://www.tefas.gov.tr/api/DB/BindHistoryInfo``
endpoint'ini hedef alır.
"""
from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from kizilelma.collectors.base import CollectorError
from kizilelma.collectors.tefas import TefasCollector
from kizilelma.models import FundData

# TEFAS resmi API yanıt formatı (timestamp + FONKODU/FONUNVAN/FIYAT)
FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent / "fixtures" / "tefas_api_response.json"
)


def _fixture_payload() -> dict[str, Any]:
    """TEFAS resmi API formatında sabit bir yanıt üretir (2 fon)."""
    # 2026-04-22 UTC -> 1777161600000 ms (gerçek ms değerine ihtiyacımız yok,
    # _coerce_date doğru parse ederse 2026-04-22'ye yaklaşık düşer).
    ts_ms = int(
        dt.datetime(2026, 4, 22, tzinfo=dt.timezone.utc).timestamp() * 1000
    )
    return {
        "draw": 0,
        "recordsTotal": 2,
        "recordsFiltered": 2,
        "data": [
            {
                "TARIH": str(ts_ms),
                "FONKODU": "AFA",
                "FONUNVAN": "Ak Portföy Para Piyasası Fonu",
                "FIYAT": 1.234567,
                "TEDPAYSAYISI": 959246.0,
                "KISISAYISI": 771.0,
                "PORTFOYBUYUKLUK": 33971906.60,
                "BORSABULTENFIYAT": "-",
            },
            {
                "TARIH": str(ts_ms),
                "FONKODU": "TGE",
                "FONUNVAN": "Test Serbest Fonu (Nitelikli Yatırımcıya)",
                "FIYAT": 5.678901,
                "TEDPAYSAYISI": 50000.0,
                "KISISAYISI": 42.0,
                "PORTFOYBUYUKLUK": 250000.0,
                "BORSABULTENFIYAT": "-",
            },
        ],
    }


@pytest.fixture
def tefas_payload() -> dict[str, Any]:
    # Fixture dosyası varsa onu tercih et, yoksa in-line üret.
    if FIXTURE_PATH.exists():
        return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return _fixture_payload()


@pytest.fixture
def _mock_home_ok() -> respx.Route:
    """TEFAS ana sayfasını (session cookie isteğini) mock'lar."""
    return respx.get(
        "https://www.tefas.gov.tr/TarihselVeriler.aspx"
    ).mock(return_value=httpx.Response(200, text="<html></html>"))


@respx.mock
@pytest.mark.asyncio
async def test_tefas_fetch_returns_fund_list(tefas_payload):
    """TEFAS resmi API'sinden fon listesi çekilebilir ve FundData'ya dönüşür."""
    respx.get("https://www.tefas.gov.tr/TarihselVeriler.aspx").mock(
        return_value=httpx.Response(200, text="<html></html>")
    )
    respx.post("https://www.tefas.gov.tr/api/DB/BindHistoryInfo").mock(
        return_value=httpx.Response(200, json=tefas_payload)
    )

    collector = TefasCollector(max_retries=1, retry_delay_range=(0.0, 0.0))
    funds = await collector.fetch()

    assert len(funds) == 2
    assert all(isinstance(f, FundData) for f in funds)

    afa = next(f for f in funds if f.code == "AFA")
    assert afa.price == Decimal("1.234567")
    # Timestamp'ten dönen tarih 2026-04-22 civarı olmalı (tz dönüşümü ±1 gün sapabilir)
    assert abs((afa.date - dt.date(2026, 4, 22)).days) <= 1
    assert afa.is_qualified_investor is False
    assert "Para Piyasası" in afa.category


@respx.mock
@pytest.mark.asyncio
async def test_tefas_marks_serbest_fund_as_qualified(tefas_payload):
    """Fon adında 'Serbest' geçenler nitelikli yatırımcı fonu olarak işaretlenir."""
    respx.get("https://www.tefas.gov.tr/TarihselVeriler.aspx").mock(
        return_value=httpx.Response(200, text="<html></html>")
    )
    respx.post("https://www.tefas.gov.tr/api/DB/BindHistoryInfo").mock(
        return_value=httpx.Response(200, json=tefas_payload)
    )

    collector = TefasCollector(max_retries=1, retry_delay_range=(0.0, 0.0))
    funds = await collector.fetch()

    serbest = next(f for f in funds if f.code == "TGE")
    assert serbest.is_qualified_investor is True
    assert "Serbest" in serbest.category


@respx.mock
@pytest.mark.asyncio
async def test_tefas_raises_when_all_lookback_days_empty():
    """Tüm geriye dönük günler boş dönerse CollectorError fırlatılır."""
    respx.get("https://www.tefas.gov.tr/TarihselVeriler.aspx").mock(
        return_value=httpx.Response(200, text="<html></html>")
    )
    # Boş "data" listesi — API geçerli ama sonuç yok.
    respx.post("https://www.tefas.gov.tr/api/DB/BindHistoryInfo").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    collector = TefasCollector(
        max_lookback_days=3, max_retries=1, retry_delay_range=(0.0, 0.0)
    )

    with pytest.raises(CollectorError) as excinfo:
        await collector.fetch()

    assert "tefas" in str(excinfo.value).lower()


@respx.mock
@pytest.mark.asyncio
async def test_tefas_raises_on_persistent_http_error():
    """API sürekli hata dönerse CollectorError fırlatılır."""
    respx.get("https://www.tefas.gov.tr/TarihselVeriler.aspx").mock(
        return_value=httpx.Response(200, text="<html></html>")
    )
    respx.post("https://www.tefas.gov.tr/api/DB/BindHistoryInfo").mock(
        return_value=httpx.Response(503, text="Service Unavailable")
    )

    collector = TefasCollector(
        max_lookback_days=2, max_retries=2, retry_delay_range=(0.0, 0.0)
    )

    with pytest.raises(CollectorError) as excinfo:
        await collector.fetch()

    msg = str(excinfo.value).lower()
    assert "tefas" in msg
    assert "veri çekilemedi" in msg or "deneme başarısız" in msg


@respx.mock
@pytest.mark.asyncio
async def test_tefas_retries_before_giving_up_on_day():
    """Aynı gün için max_retries kadar istek atılır."""
    respx.get("https://www.tefas.gov.tr/TarihselVeriler.aspx").mock(
        return_value=httpx.Response(200, text="<html></html>")
    )
    route = respx.post(
        "https://www.tefas.gov.tr/api/DB/BindHistoryInfo"
    ).mock(return_value=httpx.Response(500))

    collector = TefasCollector(
        max_lookback_days=0,  # sadece bugünü dene
        max_retries=3,
        retry_delay_range=(0.0, 0.0),
    )

    with pytest.raises(CollectorError):
        await collector.fetch()

    # Bugün hafta sonu değilse en az 3 deneme yapılmalı.
    # Hafta sonu ise hiç denenmez — o durumda bu assertion esnetilir.
    today = dt.date.today()
    if today.weekday() < 5:
        assert route.call_count == 3


@respx.mock
@pytest.mark.asyncio
async def test_tefas_skips_weekend_then_returns_first_available(tefas_payload):
    """Boş gün dönerse bir önceki iş gününe geri dönülür."""
    respx.get("https://www.tefas.gov.tr/TarihselVeriler.aspx").mock(
        return_value=httpx.Response(200, text="<html></html>")
    )

    call_count = {"n": 0}

    def _side_effect(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return httpx.Response(200, json={"data": []})
        return httpx.Response(200, json=tefas_payload)

    respx.post("https://www.tefas.gov.tr/api/DB/BindHistoryInfo").mock(
        side_effect=_side_effect
    )

    collector = TefasCollector(
        max_lookback_days=5, max_retries=1, retry_delay_range=(0.0, 0.0)
    )
    funds = await collector.fetch()

    assert len(funds) == 2
    assert call_count["n"] >= 2


@pytest.mark.asyncio
async def test_tefas_invalid_row_is_skipped_not_fatal():
    """Tek bir bozuk fon kaydı toplama işlemini kırmamalıdır."""
    payload = {
        "data": [
            # Geçersiz: fiyat 0
            {
                "TARIH": "1777161600000",
                "FONKODU": "ZRO",
                "FONUNVAN": "Kapalı Fon",
                "FIYAT": 0,
            },
            # Geçerli
            {
                "TARIH": "1777161600000",
                "FONKODU": "AFA",
                "FONUNVAN": "Ak Portföy Para Piyasası Fonu",
                "FIYAT": 1.23,
            },
        ]
    }

    with respx.mock(assert_all_called=False) as mock_router:
        mock_router.get(
            "https://www.tefas.gov.tr/TarihselVeriler.aspx"
        ).mock(return_value=httpx.Response(200, text="<html></html>"))
        mock_router.post(
            "https://www.tefas.gov.tr/api/DB/BindHistoryInfo"
        ).mock(return_value=httpx.Response(200, json=payload))

        collector = TefasCollector(max_retries=1, retry_delay_range=(0.0, 0.0))
        funds = await collector.fetch()

    assert len(funds) == 1
    assert funds[0].code == "AFA"
