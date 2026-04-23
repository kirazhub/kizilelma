"""Returns analyzer testleri."""
from decimal import Decimal

import pytest

from kizilelma.analyzers.returns import (
    annualized_return,
    classify_by_return_band,
    inflation_adjusted_return,
)


def test_annualized_return_from_monthly():
    """Aylık getiriden yıllık eşdeğeri hesaplanır."""
    # %4 aylık → yıllıkta yaklaşık %60 (bileşik)
    annual = annualized_return(monthly_return_pct=Decimal("4"))
    assert Decimal("59") < annual < Decimal("61")


def test_inflation_adjusted_return_positive():
    """Enflasyon üstü reel getiri doğru hesaplanır."""
    # %50 nominal, %40 enflasyon → reel ≈ %7.14
    real = inflation_adjusted_return(
        nominal_return_pct=Decimal("50"),
        inflation_pct=Decimal("40"),
    )
    assert Decimal("7") < real < Decimal("8")


def test_inflation_adjusted_return_negative():
    """Enflasyon altı kaldıysa reel getiri negatif olur."""
    real = inflation_adjusted_return(
        nominal_return_pct=Decimal("30"),
        inflation_pct=Decimal("50"),
    )
    assert real < 0


def test_classify_by_return_band():
    """Yıllık getiriye göre bant sınıflandırması."""
    assert classify_by_return_band(Decimal("100")) == "çok_yüksek"
    assert classify_by_return_band(Decimal("60")) == "yüksek"
    assert classify_by_return_band(Decimal("40")) == "orta"
    assert classify_by_return_band(Decimal("15")) == "düşük"
    assert classify_by_return_band(Decimal("-5")) == "negatif"
