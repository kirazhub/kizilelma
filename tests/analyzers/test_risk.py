"""Risk analyzer testleri."""
from decimal import Decimal

import pytest

from kizilelma.analyzers.risk import (
    estimate_risk_score,
    sharpe_ratio,
    risk_level_label,
)


def test_estimate_risk_score_from_returns():
    """Getiri büyüklüğüne göre risk skoru tahmin edilir.

    Yüksek getiri → yüksek risk varsayımı (basit heuristik).
    """
    score_high = estimate_risk_score(annual_return_pct=Decimal("150"))
    score_low = estimate_risk_score(annual_return_pct=Decimal("30"))
    assert score_high > score_low
    assert 0 <= score_low <= 100
    assert 0 <= score_high <= 100


def test_sharpe_ratio_positive_when_above_risk_free():
    """Risksiz orandan yüksek getiride Sharpe pozitif olur."""
    sharpe = sharpe_ratio(
        annual_return_pct=Decimal("60"),
        risk_free_rate_pct=Decimal("47.5"),
        volatility_pct=Decimal("10"),
    )
    assert sharpe > 0


def test_sharpe_ratio_negative_when_below_risk_free():
    """Risksiz orandan düşük getiride Sharpe negatif olur."""
    sharpe = sharpe_ratio(
        annual_return_pct=Decimal("30"),
        risk_free_rate_pct=Decimal("47.5"),
        volatility_pct=Decimal("10"),
    )
    assert sharpe < 0


def test_sharpe_zero_when_zero_volatility():
    """Volatilite sıfır ise Sharpe tanımsız → 0 dönülür."""
    sharpe = sharpe_ratio(
        annual_return_pct=Decimal("60"),
        risk_free_rate_pct=Decimal("47.5"),
        volatility_pct=Decimal("0"),
    )
    assert sharpe == 0


def test_risk_level_labels():
    """Risk skoruna göre etiket dönüşümü."""
    assert risk_level_label(10) == "çok düşük"
    assert risk_level_label(35) == "düşük"
    assert risk_level_label(55) == "orta"
    assert risk_level_label(75) == "yüksek"
    assert risk_level_label(95) == "çok yüksek"
