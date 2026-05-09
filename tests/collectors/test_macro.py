"""Macro collector testleri.

Doviz.com scraping pattern'larının doğru çalıştığını ve fallback'in
devreye girdiğini doğrular.
"""
import datetime as dt
from decimal import Decimal

import httpx
import pytest
import respx

from kizilelma.collectors.macro import (
    MacroCollector,
    _clean_number,
    _extract_value,
)
from kizilelma.models import MacroData


# Doviz.com ana sayfası — tüm sembollerin "satış" (s) attribute'ı ile
# yer aldığı sahte HTML. Gerçek formatla aynı: TR ondalık virgül,
# bazı değerlerde '$' öneki, binlik ayraç olarak nokta.
FAKE_HOMEPAGE_HTML = """
<html><body>
<span data-socket-key="USD" data-socket-attr="s" data-socket-animate="true">45,3532</span>
<span data-socket-key="EUR" data-socket-attr="s">48,7521</span>
<span data-socket-key="gram-altin" data-socket-attr="s">6.875,62</span>
<span data-socket-key="ons" data-socket-attr="s">$4.715,04</span>
<span data-socket-key="XU100" data-socket-attr="s">15.062,65</span>
<span data-socket-key="BRENT" data-socket-attr="s">$104,84</span>
</body></html>
"""

# BIST sayfası — BIST 30 burada bulunur
FAKE_BIST_HTML = """
<html><body>
<span data-socket-key="XU030" data-socket-attr="s">13.890,12</span>
</body></html>
"""

# Emtia sayfası — brent ana sayfada yoksa buradan
FAKE_COMMODITY_HTML = """
<html><body>
<span data-socket-key="BRENT" data-socket-attr="s">$78,45</span>
</body></html>
"""


# ---------- _clean_number birim testleri ----------


def test_clean_number_simple_decimal():
    assert _clean_number("39.52") == Decimal("39.52")


def test_clean_number_turkish_comma():
    assert _clean_number("39,52") == Decimal("39.52")


def test_clean_number_thousand_separator():
    assert _clean_number("12.450,75") == Decimal("12450.75")


def test_clean_number_dollar_prefix():
    """'$104,84' -> 104.84 (currency önekleri temizlenir)."""
    assert _clean_number("$104,84") == Decimal("104.84")


def test_clean_number_percent_prefix():
    assert _clean_number("%0,87") == Decimal("0.87")


def test_clean_number_empty():
    assert _clean_number("") is None
    assert _clean_number("   ") is None
    assert _clean_number("abc") is None


# ---------- _extract_value testleri ----------


def test_extract_value_with_attr_s():
    """Yeni doviz.com şablonu attr='s' (satış) kullanır."""
    html = '<span data-socket-key="USD" data-socket-attr="s">45,35</span>'
    assert _extract_value(html, "USD") == Decimal("45.35")


def test_extract_value_falls_back_to_last():
    """Eski şablon attr='last' da desteklenir."""
    html = '<span data-socket-key="USD" data-socket-attr="last">39,52</span>'
    assert _extract_value(html, "USD") == Decimal("39.52")


def test_extract_value_not_found():
    html = '<span data-socket-key="USD" data-socket-attr="s">45,35</span>'
    assert _extract_value(html, "EUR") is None


def test_extract_value_with_currency_symbol():
    """Sayıların önündeki '$' işareti temizlenir."""
    html = '<span data-socket-key="ons" data-socket-attr="s">$4.715,04</span>'
    assert _extract_value(html, "ons") == Decimal("4715.04")


# ---------- Collector entegrasyon testleri ----------


@respx.mock
@pytest.mark.asyncio
async def test_macro_fetch_all_categories():
    """Ana sayfa + BIST sayfası ile tüm kategoriler çekilir."""
    respx.get("https://www.doviz.com/").mock(
        return_value=httpx.Response(200, text=FAKE_HOMEPAGE_HTML)
    )
    respx.get("https://borsa.doviz.com/").mock(
        return_value=httpx.Response(200, text=FAKE_BIST_HTML)
    )
    # Brent ana sayfada zaten var, emtia sayfasına gerek yok ama
    # kod yine de istek atabilir - mocklayalım ki ConnectError olmasın
    respx.get("https://www.doviz.com/emtia").mock(
        return_value=httpx.Response(200, text=FAKE_COMMODITY_HTML)
    )

    c = MacroCollector(timeout=5.0)
    data = await c.fetch()

    symbols = {m.symbol for m in data}
    # Temel semboller hepsi var
    assert "USDTRY" in symbols
    assert "EURTRY" in symbols
    assert "GOLD_GR" in symbols
    assert "GOLD_OZ" in symbols
    assert "BIST100" in symbols
    assert "BIST30" in symbols
    assert "BRENT" in symbols

    # USD doğru değer
    usd = next(m for m in data if m.symbol == "USDTRY")
    assert usd.value == Decimal("45.3532")
    assert usd.currency == "TRY"
    assert usd.category == "currency"

    # Gram altın binlik ayraçlı
    gram = next(m for m in data if m.symbol == "GOLD_GR")
    assert gram.value == Decimal("6875.62")

    # Ons altın USD ($ önekiyle)
    ons = next(m for m in data if m.symbol == "GOLD_OZ")
    assert ons.value == Decimal("4715.04")
    assert ons.currency == "USD"

    # BIST 100
    bist100 = next(m for m in data if m.symbol == "BIST100")
    assert bist100.value == Decimal("15062.65")

    # BIST 30 (ek sayfadan geldi)
    bist30 = next(m for m in data if m.symbol == "BIST30")
    assert bist30.value == Decimal("13890.12")


@respx.mock
@pytest.mark.asyncio
async def test_macro_fetch_homepage_failure_uses_subpages():
    """Ana sayfa 500 dönse bile alt sayfalardan kısmi veri gelir."""
    respx.get("https://www.doviz.com/").mock(return_value=httpx.Response(500))
    respx.get("https://borsa.doviz.com/").mock(
        return_value=httpx.Response(200, text=FAKE_BIST_HTML)
    )
    respx.get("https://www.doviz.com/emtia").mock(
        return_value=httpx.Response(200, text=FAKE_COMMODITY_HTML)
    )

    c = MacroCollector(timeout=5.0)
    data = await c.fetch()

    # Ana sayfa fail, BIST 30 ve Brent ek sayfalardan gelmiş olmalı
    symbols = {m.symbol for m in data}
    assert "BIST30" in symbols
    assert "BRENT" in symbols


@respx.mock
@pytest.mark.asyncio
async def test_macro_fetch_total_failure_uses_fallback():
    """Tüm scraping çökünce fallback verileri döner."""
    respx.get("https://www.doviz.com/").mock(return_value=httpx.Response(500))
    respx.get("https://borsa.doviz.com/").mock(return_value=httpx.Response(500))
    respx.get("https://www.doviz.com/emtia").mock(return_value=httpx.Response(500))

    c = MacroCollector(timeout=5.0)
    data = await c.fetch()

    symbols = {m.symbol for m in data}
    assert len(data) >= 4
    assert "USDTRY" in symbols
    assert "BIST100" in symbols
    assert all(isinstance(m, MacroData) for m in data)


def test_fallback_data_structure():
    """Fallback verisi her zaman hazır, doğru yapıda ve makul değerlerde."""
    fallback = MacroCollector._fallback_data(dt.date.today())
    assert len(fallback) >= 4
    symbols = [m.symbol for m in fallback]
    assert "USDTRY" in symbols
    assert "EURTRY" in symbols
    assert "GOLD_GR" in symbols
    assert "BIST100" in symbols

    for m in fallback:
        assert m.value > 0
        assert m.category in ("currency", "commodity", "index")


@pytest.mark.asyncio
async def test_macro_fetch_never_raises():
    """Network erişilemez olsa bile exception fırlatmaz, fallback döner."""
    c = MacroCollector(timeout=0.001)
    data = await c.fetch()
    assert isinstance(data, list)
    assert len(data) > 0
