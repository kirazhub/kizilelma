"""DB erişim testleri."""
import datetime as dt
from decimal import Decimal

import pytest
from sqlmodel import SQLModel, create_engine

from kizilelma.models import (
    FundData, RepoRate, MarketSnapshot
)
from kizilelma.ai_advisor.advisor import AdvisorReport
from kizilelma.storage.db import (
    init_db,
    save_snapshot,
    save_report,
    get_recent_snapshots,
    get_fund_history,
)


@pytest.fixture
def memory_db():
    """In-memory SQLite for testing."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def test_save_snapshot_persists_data(memory_db):
    """save_snapshot tüm verileri DB'ye yazar."""
    snapshot = MarketSnapshot(
        timestamp=dt.datetime(2026, 4, 23, 10, 0),
        funds=[
            FundData(
                code="AFA", name="Test", category="Hisse",
                price=Decimal("1.0"), date=dt.date.today(),
                return_1m=Decimal("4"),
            )
        ],
        repo_rates=[
            RepoRate(type="repo", maturity="overnight",
                     rate=Decimal("47.5"), date=dt.date.today())
        ],
    )

    snapshot_id = save_snapshot(snapshot, engine=memory_db)

    assert snapshot_id is not None
    assert isinstance(snapshot_id, int)


def test_save_report_links_to_snapshot(memory_db):
    """save_report rapor metnini saklar."""
    snapshot = MarketSnapshot(timestamp=dt.datetime.now())
    snap_id = save_snapshot(snapshot, engine=memory_db)

    report = AdvisorReport(
        fund_section="📊 İçerik",
        summary_section="🎯 Özet",
    )
    report_id = save_report(
        report, snapshot_id=snap_id,
        sent_messages=8, status="success",
        engine=memory_db,
    )
    assert report_id is not None


def test_get_recent_snapshots_returns_in_order(memory_db):
    """En yeni snapshot'lar önce gelir."""
    for hour in [10, 11, 12]:
        snapshot = MarketSnapshot(
            timestamp=dt.datetime(2026, 4, 23, hour, 0)
        )
        save_snapshot(snapshot, engine=memory_db)

    recent = get_recent_snapshots(limit=2, engine=memory_db)
    assert len(recent) == 2
    assert recent[0].timestamp.hour > recent[1].timestamp.hour


def test_get_fund_history_returns_specific_fund(memory_db):
    """Belirli bir fon kodu için geçmiş kayıtlar gelir."""
    for i in range(3):
        snap = MarketSnapshot(
            timestamp=dt.datetime(2026, 4, 20 + i, 10, 0),
            funds=[
                FundData(
                    code="AFA", name="Test", category="Hisse",
                    price=Decimal(str(1.0 + i * 0.1)),
                    date=dt.date(2026, 4, 20 + i),
                    return_1m=Decimal("4"),
                )
            ],
        )
        save_snapshot(snap, engine=memory_db)

    history = get_fund_history("AFA", limit=10, engine=memory_db)
    assert len(history) == 3
