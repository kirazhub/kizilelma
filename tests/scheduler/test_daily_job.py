"""Daily job orchestration testleri."""
import datetime as dt
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kizilelma.models import FundData, MarketSnapshot
from kizilelma.scheduler.daily_job import (
    collect_all_data,
    run_daily_job,
)


@pytest.mark.asyncio
async def test_collect_all_data_aggregates_all_sources(monkeypatch):
    """collect_all_data tüm collector'ları çağırır ve MarketSnapshot döner."""
    monkeypatch.setenv("TCMB_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")

    fake_funds = [
        FundData(
            code="A", name="Test", category="Hisse",
            price=Decimal("1"), date=dt.date.today(),
        )
    ]

    with patch("kizilelma.scheduler.daily_job.TefasCollector") as tefas_cls, \
         patch("kizilelma.scheduler.daily_job.TcmbCollector") as tcmb_cls, \
         patch("kizilelma.scheduler.daily_job.BistCollector") as bist_cls, \
         patch("kizilelma.scheduler.daily_job.EurobondCollector") as eb_cls, \
         patch("kizilelma.scheduler.daily_job.NewsCollector") as news_cls:
        tefas_cls.return_value.fetch = AsyncMock(return_value=fake_funds)
        tcmb_cls.return_value.fetch = AsyncMock(return_value=[])
        bist_cls.return_value.fetch = AsyncMock(return_value=([], []))
        eb_cls.return_value.fetch = AsyncMock(return_value=[])
        news_cls.return_value.fetch = AsyncMock(return_value=[])

        snapshot = await collect_all_data()

    assert isinstance(snapshot, MarketSnapshot)
    assert snapshot.funds == fake_funds


@pytest.mark.asyncio
async def test_collect_handles_collector_failure(monkeypatch):
    """Bir collector çökerse errors dolu, diğerleri çalışır."""
    monkeypatch.setenv("TCMB_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")

    with patch("kizilelma.scheduler.daily_job.TefasCollector") as tefas_cls, \
         patch("kizilelma.scheduler.daily_job.TcmbCollector") as tcmb_cls, \
         patch("kizilelma.scheduler.daily_job.BistCollector") as bist_cls, \
         patch("kizilelma.scheduler.daily_job.EurobondCollector") as eb_cls, \
         patch("kizilelma.scheduler.daily_job.NewsCollector") as news_cls:
        tefas_cls.return_value.fetch = AsyncMock(side_effect=Exception("TEFAS down"))
        tcmb_cls.return_value.fetch = AsyncMock(return_value=[])
        bist_cls.return_value.fetch = AsyncMock(return_value=([], []))
        eb_cls.return_value.fetch = AsyncMock(return_value=[])
        news_cls.return_value.fetch = AsyncMock(return_value=[])

        snapshot = await collect_all_data()

    assert "tefas" in snapshot.errors
    assert snapshot.funds == []


@pytest.mark.asyncio
async def test_run_daily_job_full_flow(monkeypatch, tmp_path):
    """run_daily_job: collect → AI → DB tam akışı çalışır."""
    monkeypatch.setenv("TCMB_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("KIZILELMA_DB", str(tmp_path / "test.db"))

    with patch("kizilelma.scheduler.daily_job.collect_all_data") as collect_mock, \
         patch("kizilelma.scheduler.daily_job.AIAdvisor") as advisor_cls:
        collect_mock.return_value = MarketSnapshot(timestamp=dt.datetime.now())
        advisor_cls.return_value.generate_report = AsyncMock(
            return_value=MagicMock(
                fund_section="test",
                serbest_fund_section=None,
                bond_section=None,
                sukuk_section=None,
                repo_section=None,
                eurobond_section=None,
                news_section=None,
                summary_section="özet",
                errors=[],
            )
        )

        result = await run_daily_job()

    assert result["status"] in ("success", "partial")
    assert result["snapshot_id"] is not None


@pytest.mark.asyncio
async def test_daily_job_persists_to_db(monkeypatch, tmp_path):
    """Daily job snapshot ve raporu DB'ye kaydeder."""
    monkeypatch.setenv("TCMB_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("KIZILELMA_DB", str(tmp_path / "test.db"))

    from kizilelma.storage.db import init_db, get_recent_snapshots, get_engine

    engine = get_engine()
    init_db(engine)

    with patch("kizilelma.scheduler.daily_job.collect_all_data") as collect_mock, \
         patch("kizilelma.scheduler.daily_job.AIAdvisor") as advisor_cls:
        collect_mock.return_value = MarketSnapshot(timestamp=dt.datetime.now())
        advisor_cls.return_value.generate_report = AsyncMock(
            return_value=MagicMock(
                fund_section="test",
                serbest_fund_section=None,
                bond_section=None,
                sukuk_section=None,
                repo_section=None,
                eurobond_section=None,
                news_section=None,
                summary_section="özet",
                errors=[],
            )
        )

        await run_daily_job()

    snapshots = get_recent_snapshots(limit=5, engine=engine)
    assert len(snapshots) >= 1
