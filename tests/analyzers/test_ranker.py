"""Ranker testleri."""
import datetime as dt
from decimal import Decimal

import pytest

from kizilelma.models import FundData
from kizilelma.analyzers.ranker import (
    top_funds_by_return,
    top_funds_by_category,
    filter_qualified,
)


def _make_fund(code: str, return_1m: Decimal, category: str = "Hisse",
               qualified: bool = False) -> FundData:
    return FundData(
        code=code,
        name=f"Fon {code}",
        category=category,
        price=Decimal("1.0"),
        date=dt.date.today(),
        return_1m=return_1m,
        return_1y=return_1m * 12,
        is_qualified_investor=qualified,
    )


def test_top_funds_by_return_orders_by_metric():
    """Belirtilen metriğe göre azalan sıralama yapar."""
    funds = [
        _make_fund("A", Decimal("3")),
        _make_fund("B", Decimal("5")),
        _make_fund("C", Decimal("1")),
    ]
    top = top_funds_by_return(funds, metric="return_1m", limit=3)
    assert [f.code for f in top] == ["B", "A", "C"]


def test_top_funds_by_return_respects_limit():
    """Limit kadar fon döner."""
    funds = [_make_fund(f"F{i}", Decimal(str(i))) for i in range(10)]
    top = top_funds_by_return(funds, metric="return_1m", limit=3)
    assert len(top) == 3


def test_top_funds_by_category_groups_correctly():
    """Kategoriye göre gruplama yapar, her kategori için top N."""
    funds = [
        _make_fund("A1", Decimal("5"), category="Hisse"),
        _make_fund("A2", Decimal("3"), category="Hisse"),
        _make_fund("B1", Decimal("4"), category="Tahvil"),
        _make_fund("B2", Decimal("2"), category="Tahvil"),
    ]
    grouped = top_funds_by_category(funds, metric="return_1m", limit=1)
    assert "Hisse" in grouped
    assert "Tahvil" in grouped
    assert grouped["Hisse"][0].code == "A1"
    assert grouped["Tahvil"][0].code == "B1"


def test_filter_qualified_separates_serbest_funds():
    """Serbest fonlar (nitelikli yatırımcı) ayrı bir listede toplanır."""
    funds = [
        _make_fund("A", Decimal("5"), qualified=False),
        _make_fund("B", Decimal("10"), qualified=True),
    ]
    standart, serbest = filter_qualified(funds)
    assert len(standart) == 1
    assert len(serbest) == 1
    assert serbest[0].code == "B"


def test_top_funds_handles_none_metric_safely():
    """Metric None olan fonlar listede sona düşer."""
    funds = [
        _make_fund("A", Decimal("5")),
        FundData(
            code="X",
            name="No data",
            category="Hisse",
            price=Decimal("1"),
            date=dt.date.today(),
            return_1m=None,
        ),
    ]
    top = top_funds_by_return(funds, metric="return_1m", limit=10)
    assert top[0].code == "A"
