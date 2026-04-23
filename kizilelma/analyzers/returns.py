"""Getiri hesaplamaları.

Saf matematiksel fonksiyonlar — HTTP veya AI çağrısı yok, hızlı ve test edilebilir.
"""
from decimal import Decimal


def annualized_return(monthly_return_pct: Decimal) -> Decimal:
    """Aylık getiriden yıllık bileşik getiri hesapla.

    Formül: (1 + r/100)^12 - 1

    Args:
        monthly_return_pct: Aylık getiri yüzde olarak (örn. 4 = %4)

    Returns:
        Yıllık bileşik getiri yüzde olarak
    """
    monthly_factor = Decimal(1) + monthly_return_pct / Decimal(100)
    annual_factor = monthly_factor ** 12
    return (annual_factor - Decimal(1)) * Decimal(100)


def inflation_adjusted_return(
    nominal_return_pct: Decimal,
    inflation_pct: Decimal,
) -> Decimal:
    """Reel getiri hesapla (Fisher denklemi).

    Formül: ((1 + nominal) / (1 + enflasyon) - 1) * 100
    """
    nominal_factor = Decimal(1) + nominal_return_pct / Decimal(100)
    inflation_factor = Decimal(1) + inflation_pct / Decimal(100)
    return (nominal_factor / inflation_factor - Decimal(1)) * Decimal(100)


def classify_by_return_band(annual_return_pct: Decimal) -> str:
    """Yıllık getiriyi bantlara ayır.

    Bantlar:
        - çok_yüksek: > 80%
        - yüksek:     50-80%
        - orta:       30-50%
        - düşük:      0-30%
        - negatif:    < 0%
    """
    if annual_return_pct < 0:
        return "negatif"
    if annual_return_pct < 30:
        return "düşük"
    if annual_return_pct < 50:
        return "orta"
    if annual_return_pct < 80:
        return "yüksek"
    return "çok_yüksek"
