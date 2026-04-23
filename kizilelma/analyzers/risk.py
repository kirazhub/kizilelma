"""Risk hesaplamaları: volatilite, Sharpe oranı, risk skoru.

NOT: v1'de geçmiş veri biriktirilmediğinden gerçek volatilite hesaplanamaz.
Bunun yerine getiri büyüklüğüne göre basit bir heuristic kullanıyoruz.
v3'te geçmiş veri biriktirildiğinde gerçek standart sapma hesaplanacak.
"""
from decimal import Decimal


def estimate_risk_score(annual_return_pct: Decimal) -> int:
    """Yıllık getiriden risk skoru tahmini (0-100).

    Heuristic: Yüksek getiri = yüksek risk (genel kural).
    İlerideki versiyonlarda gerçek volatilite ile değiştirilecek.
    """
    abs_ret = abs(annual_return_pct)
    if abs_ret < Decimal("20"):
        return 10
    if abs_ret < Decimal("40"):
        return 25
    if abs_ret < Decimal("60"):
        return 45
    if abs_ret < Decimal("100"):
        return 70
    return 90


def sharpe_ratio(
    annual_return_pct: Decimal,
    risk_free_rate_pct: Decimal,
    volatility_pct: Decimal,
) -> Decimal:
    """Sharpe oranı: risk başına düşen ekstra getiri.

    Formül: (Getiri - Risksiz Oran) / Volatilite
    """
    if volatility_pct == 0:
        return Decimal(0)
    return (annual_return_pct - risk_free_rate_pct) / volatility_pct


def risk_level_label(risk_score: int) -> str:
    """Risk skorunu Türkçe etikete çevir."""
    if risk_score < 20:
        return "çok düşük"
    if risk_score < 40:
        return "düşük"
    if risk_score < 60:
        return "orta"
    if risk_score < 80:
        return "yüksek"
    return "çok yüksek"
