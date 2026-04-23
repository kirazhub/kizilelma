"""AI Advisor testleri."""
import datetime as dt
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kizilelma.models import FundData, MarketSnapshot
from kizilelma.ai_advisor.advisor import AIAdvisor, AdvisorReport


@pytest.fixture
def sample_snapshot():
    return MarketSnapshot(
        timestamp=dt.datetime(2026, 4, 23, 10, 0),
        funds=[
            FundData(
                code="AFA", name="Test", category="Para Piyasası",
                price=Decimal("1.0"), date=dt.date.today(),
                return_1m=Decimal("4"), return_1y=Decimal("48"),
            )
        ],
        bonds=[],
        sukuks=[],
        repo_rates=[],
        eurobonds=[],
        news=[],
    )


@pytest.mark.asyncio
async def test_advisor_generates_full_report(sample_snapshot):
    """Advisor tüm bölümleri içeren rapor üretir."""
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text="📊 Test bölümü içeriği")]

    with patch("kizilelma.ai_advisor.advisor.anthropic.AsyncAnthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=fake_response)
        mock_client_cls.return_value = mock_client

        advisor = AIAdvisor(api_key="test_key")
        report = await advisor.generate_report(sample_snapshot)

    assert isinstance(report, AdvisorReport)
    # En az bir bölüm üretildi
    assert report.fund_section or report.summary_section
    # Hata yok
    assert report.errors == []


@pytest.mark.asyncio
async def test_advisor_handles_api_failure_gracefully(sample_snapshot):
    """API hatası olursa rapor yine de döner ama errors dolu olur."""
    with patch("kizilelma.ai_advisor.advisor.anthropic.AsyncAnthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API down"))
        mock_client_cls.return_value = mock_client

        advisor = AIAdvisor(api_key="test_key")
        report = await advisor.generate_report(sample_snapshot)

    assert len(report.errors) > 0
