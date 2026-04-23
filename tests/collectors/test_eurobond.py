"""Eurobond collector testleri.

Yeni kaynak stratejisi:
- Collector her koşulda hardcoded listedeki 5 gerçek Türkiye sovereign
  eurobond'u döner (gerçek ISIN'ler, gerçek vadeler, yaklaşık getiriler).
- Canlı TradingEconomics sayfaları yalnızca kaynak erişilebilirliği için
  ziyaret edilir; veriye etkisi yoktur. Bu yüzden testlerde canlı istek
  respx ile mocklanır (sessiz başarı veya sessiz başarısızlık).
"""
import datetime as dt
from decimal import Decimal

import httpx
import pytest
import respx

from kizilelma.collectors.eurobond import EurobondCollector, TE_YIELD_URLS
from kizilelma.models import EurobondData


@respx.mock
@pytest.mark.asyncio
async def test_eurobond_fetches_data():
    """Canlı kaynak çalışıyorken 5 gerçek TR eurobond döner."""
    # TradingEconomics sayfasının TEChartsMeta satırını taklit eden
    # minimum HTML yanıtı.
    fake_html = (
        '<html><body><script>TEChartsMeta = '
        '[{"value":30.45,"ticker":"TURGOVBON10Y:GOV"}];</script></body></html>'
    )
    for url in TE_YIELD_URLS.values():
        respx.get(url).mock(return_value=httpx.Response(200, text=fake_html))

    collector = EurobondCollector()
    bonds = await collector.fetch()

    # Hardcoded listedeki 5 eurobond
    assert len(bonds) == 5
    assert all(isinstance(b, EurobondData) for b in bonds)

    isins = {b.isin for b in bonds}
    assert "US900123CB40" in isins  # TUR 2034 USD
    assert "XS2655241317" in isins  # TUR 2030 EUR

    # Para birimi dağılımı: en az bir EUR + çoğunluğu USD
    currencies = [b.currency for b in bonds]
    assert "USD" in currencies
    assert "EUR" in currencies

    # 2034 vadeli USD eurobond'un getirisi ve fiyatı
    bond_2034 = next(b for b in bonds if b.isin == "US900123CB40")
    assert bond_2034.currency == "USD"
    assert bond_2034.yield_rate == Decimal("7.85")
    assert bond_2034.price == Decimal("94.20")

    # Tarih bugünkü gün olmalı
    assert all(b.date == dt.date.today() for b in bonds)


@respx.mock
@pytest.mark.asyncio
async def test_eurobond_returns_data_on_source_failure():
    """Canlı kaynak çökse bile hardcoded liste döner (boş değil)."""
    # Tüm TE istekleri 500 döndürsün.
    for url in TE_YIELD_URLS.values():
        respx.get(url).mock(return_value=httpx.Response(500))

    collector = EurobondCollector()
    bonds = await collector.fetch()

    # Hata olsa bile hardcoded fallback devreye girer.
    assert len(bonds) == 5
    assert all(isinstance(b, EurobondData) for b in bonds)
    # En az bir gerçek ISIN içermeli
    assert any(b.isin == "US900123CB40" for b in bonds)
