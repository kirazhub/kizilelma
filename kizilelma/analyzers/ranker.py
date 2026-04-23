"""Sıralama ve filtreleme yardımcıları."""
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
