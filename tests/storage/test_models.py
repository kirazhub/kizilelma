"""Storage models testleri."""
import datetime as dt

from kizilelma.storage.models import (
    SnapshotRecord,
    FundRecord,
    RepoRecord,
    ReportRecord,
)


def test_snapshot_record_can_be_instantiated():
    """SnapshotRecord temel alanlarla oluşturulabilir."""
    snap = SnapshotRecord(
        timestamp=dt.datetime(2026, 4, 23, 10, 0),
        fund_count=100,
        bond_count=20,
        news_count=15,
        errors_json="{}",
    )
    assert snap.fund_count == 100


def test_fund_record_links_to_snapshot():
    """FundRecord snapshot_id ile bağlanır."""
    fund = FundRecord(
        snapshot_id=1,
        code="AFA",
        name="Test Fonu",
        category="Para Piyasası",
        price=1.234,
        return_1m=4.5,
        return_1y=52.0,
        date=dt.date.today(),
    )
    assert fund.code == "AFA"


def test_report_record_stores_full_report():
    """ReportRecord AI raporu metnini saklar."""
    record = ReportRecord(
        snapshot_id=1,
        timestamp=dt.datetime.now(),
        fund_section="📊 İçerik",
        summary_section="🎯 Özet",
        sent_messages=8,
        status="success",
    )
    assert record.sent_messages == 8
