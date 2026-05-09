"""Sıralama ve filtreleme yardımcıları."""
import datetime as dt
from collections import defaultdict
from decimal import Decimal
from typing import Literal

from kizilelma.models import FundData


ReturnMetric = Literal[
    "return_1d", "return_1w", "return_1m", "return_3m", "return_6m", "return_1y"
]


def top_funds_by_return(
    funds: list[FundData],
    metric: ReturnMetric = "return_1m",
    limit: int = 10,
) -> list[FundData]:
    """Belirtilen getiri metriğine göre en iyi N fonu döner.

    None değerli fonlar listenin sonuna düşer.
    """
    def sort_key(fund: FundData) -> tuple[int, Decimal]:
        value = getattr(fund, metric)
        if value is None:
            return (1, Decimal(0))  # None'lar sonda
        return (0, -value)  # değerli olanlar başta, büyükten küçüğe

    sorted_funds = sorted(funds, key=sort_key)
    return sorted_funds[:limit]


def top_funds_by_category(
    funds: list[FundData],
    metric: ReturnMetric = "return_1m",
    limit: int = 5,
) -> dict[str, list[FundData]]:
    """Her kategori için ayrı en iyi N listesi.

    Returns:
        {kategori_adı: [top fonlar]}
    """
    by_category: dict[str, list[FundData]] = defaultdict(list)
    for fund in funds:
        by_category[fund.category].append(fund)

    result: dict[str, list[FundData]] = {}
    for category, items in by_category.items():
        result[category] = top_funds_by_return(items, metric=metric, limit=limit)
    return result


def filter_qualified(
    funds: list[FundData],
) -> tuple[list[FundData], list[FundData]]:
    """Standart fonlar ve serbest fonları ayır.

    Returns:
        (standart_fonlar, serbest_fonlar) tuple'ı
    """
    standart: list[FundData] = []
    serbest: list[FundData] = []
    for fund in funds:
        if fund.is_qualified_investor:
            serbest.append(fund)
        else:
            standart.append(fund)
    return standart, serbest


def filter_active_funds(
    funds: list[FundData],
    max_age_days: int = 7,
) -> list[FundData]:
    """İşlem görmeyen / ölü / yeni kurulmuş fonları filtrele.

    Bir fon aktif sayılır eğer:
    - Fiyatı > 0 (Pydantic zaten zorluyor ama defansif kontrol)
    - Fiyatının tarihi son `max_age_days` gün içinde
    - En az bir anlamlı getiri değeri (1A veya 1Y) sıfırdan farklı
    - 1Y getirisi varsa mutlak değeri en az %0.5 (yeni kurulmuş /
      durağan fonları eler)

    Args:
        funds: Tüm fonların listesi
        max_age_days: Fiyat tarihinin en eski olabileceği gün sayısı

    Returns:
        Sadece aktif (TEFAS'ta hâlâ işlem gören) fonların listesi.
    """
    today = dt.date.today()
    cutoff = today - dt.timedelta(days=max_age_days)
    active: list[FundData] = []

    for f in funds:
        # Kontrol 1: Fiyat pozitif olmalı
        if f.price is None or f.price <= 0:
            continue

        # Kontrol 2: Tarih güncel olmalı (son max_age_days içinde)
        if f.date is None or f.date < cutoff:
            continue

        # Kontrol 3: 1A veya 1Y getirisi anlamlı olmalı
        has_1m = f.return_1m is not None and f.return_1m != Decimal(0)
        has_1y = f.return_1y is not None and f.return_1y != Decimal(0)

        if not (has_1m or has_1y):
            # Ne 1A ne 1Y verisi var = ölü fon
            continue

        # Kontrol 4: 1Y getirisi varsa anlamlı bir hareket göstermeli
        # (yeni kurulmuş / durağan fonlar mutlak %0.5'in altındadır)
        if has_1y and abs(f.return_1y) < Decimal("0.5"):
            continue

        active.append(f)

    return active
