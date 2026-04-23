"""ai_advisor.formatters testleri — fon listesi biçimlendirme.

Özellikle ``format_funds_by_category`` fonksiyonunun 1G (günlük getiri)
sütununu ve sektör/varlık etiketlerini (🏷️ satırı) doğru yerleştirdiğini
doğrular.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from kizilelma.ai_advisor.formatters import format_funds_by_category
from kizilelma.models import FundData


def _make_fund(
    code: str = "ABC",
    name: str = "TEST PORTFÖY HİSSE FONU",
    category: str = "Hisse Senedi Fonu",
    asset_tags: list[str] | None = None,
    return_1d: Decimal | None = Decimal("0.12"),
) -> FundData:
    return FundData(
        code=code,
        name=name,
        category=category,
        price=Decimal("1.2345"),
        date=dt.date(2026, 4, 23),
        return_1d=return_1d,
        return_1m=Decimal("3.5"),
        return_3m=Decimal("9.8"),
        return_6m=Decimal("18.2"),
        return_1y=Decimal("52.1"),
        asset_tags=asset_tags if asset_tags is not None else ["Hisse", "Teknoloji"],
    )


def test_format_shows_daily_return() -> None:
    """Çıktıda 1G (günlük getiri) sütunu görünmeli."""
    out = format_funds_by_category([_make_fund()], "Hisse", "📈", limit=5)
    assert "1G:" in out
    # %+0.1 formatında (return_1d = 0.12 → %+0.1)
    assert "%+0.1" in out


def test_format_shows_asset_tags_line() -> None:
    """Etiketi olan fonun altında 🏷️ satırı olmalı."""
    fund = _make_fund(asset_tags=["Hisse", "Teknoloji", "BIST30"])
    out = format_funds_by_category([fund], "Hisse", "📈", limit=5)
    assert "🏷️" in out
    assert "Hisse" in out
    assert "Teknoloji" in out
    assert "BIST30" in out
    # Etiketler '·' ile ayrılmış olmalı
    assert "·" in out


def test_format_omits_tags_line_when_empty() -> None:
    """Etiketi olmayan fon için 🏷️ satırı çıkmamalı."""
    fund = _make_fund(asset_tags=[])
    out = format_funds_by_category([fund], "Hisse", "📈", limit=5)
    assert "🏷️" not in out


def test_format_handles_missing_daily_return() -> None:
    """return_1d=None olduğunda '—' gösterilmeli, çökmemeli."""
    fund = _make_fund(return_1d=None)
    out = format_funds_by_category([fund], "Hisse", "📈", limit=5)
    assert "1G: —" in out


def test_format_empty_fund_list() -> None:
    """Boş liste için bilgilendirme mesajı dönmeli."""
    out = format_funds_by_category([], "Hisse", "📈", limit=5)
    assert "veri alınamadı" in out.lower()
