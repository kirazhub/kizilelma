"""Prompt şablonu testleri."""
import datetime as dt
from decimal import Decimal

from kizilelma.models import (
    FundData, BondData, RepoRate, NewsItem, MarketSnapshot
)
from kizilelma.ai_advisor.prompts import (
    build_fund_section_prompt,
    build_summary_prompt,
    SYSTEM_PROMPT,
)


def test_system_prompt_is_turkish():
    """Sistem promptu Türkçe ve danışman karakterli."""
    assert "Türkçe" in SYSTEM_PROMPT or "Türkiye" in SYSTEM_PROMPT
    assert "yatırım" in SYSTEM_PROMPT.lower()
    # Yasal uyarı içermeli
    assert "tavsiye" in SYSTEM_PROMPT.lower()


def test_fund_section_prompt_includes_fund_data():
    """Fon prompt'ı top fonların verisini içerir."""
    funds = [
        FundData(
            code="AFA", name="Test Fonu", category="Para Piyasası",
            price=Decimal("1.234"), date=dt.date.today(),
            return_1m=Decimal("4.5"), return_1y=Decimal("52"),
        )
    ]
    prompt = build_fund_section_prompt(top_funds=funds)
    assert "AFA" in prompt
    assert "52" in prompt or "4.5" in prompt
    # 3 profilli yorum istenmeli
    assert "muhafazak" in prompt.lower()
    assert "dengeli" in prompt.lower()
    assert "agresif" in prompt.lower()


def test_summary_prompt_aggregates_all_data():
    """Özet prompt'ı tüm veri tiplerini içerir."""
    snapshot = MarketSnapshot(
        timestamp=dt.datetime.now(),
        funds=[],
        bonds=[],
        sukuks=[],
        repo_rates=[],
        eurobonds=[],
        news=[],
    )
    prompt = build_summary_prompt(snapshot=snapshot, top_picks={})
    assert "özet" in prompt.lower() or "karşılaştırma" in prompt.lower()
    assert "muhafazak" in prompt.lower()
    assert "dengeli" in prompt.lower()
    assert "agresif" in prompt.lower()
