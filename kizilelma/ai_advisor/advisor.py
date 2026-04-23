"""AI Advisor — Claude API ile yorum üretici.

MarketSnapshot'ı alır, her bölüm için ayrı AI çağrısı yapar,
sonuçları AdvisorReport olarak döner.

Hata toleranslı: Bir bölüm başarısız olursa diğerleri çalışır.
Tüm AI başarısız olursa AdvisorReport yine döner ama errors dolu olur.
"""
import asyncio
from dataclasses import dataclass, field
from typing import Optional

import anthropic

from kizilelma.models import MarketSnapshot
from kizilelma.analyzers.ranker import (
    top_funds_by_return,
    filter_qualified,
)
from kizilelma.ai_advisor.prompts import (
    SYSTEM_PROMPT,
    build_fund_section_prompt,
    build_serbest_fund_prompt,
    build_repo_section_prompt,
    build_news_section_prompt,
    build_summary_prompt,
)


CLAUDE_MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 1024


@dataclass
class AdvisorReport:
    """AI tarafından üretilen tam rapor.

    Her alan bir Telegram mesajına karşılık gelir.
    """
    fund_section: Optional[str] = None
    serbest_fund_section: Optional[str] = None
    bond_section: Optional[str] = None
    sukuk_section: Optional[str] = None
    repo_section: Optional[str] = None
    eurobond_section: Optional[str] = None
    news_section: Optional[str] = None
    summary_section: Optional[str] = None
    errors: list[str] = field(default_factory=list)


class AIAdvisor:
    """Claude API üzerinden Türkçe yatırım yorumu üretir."""

    def __init__(self, api_key: str, model: str = CLAUDE_MODEL) -> None:
        self.api_key = api_key
        self.model = model

    async def generate_report(self, snapshot: MarketSnapshot) -> AdvisorReport:
        """Tüm bölümler için paralel AI çağrıları yap."""
        report = AdvisorReport()
        client = anthropic.AsyncAnthropic(api_key=self.api_key)

        standart_funds, serbest_funds = filter_qualified(snapshot.funds)
        top_standart = top_funds_by_return(standart_funds, "return_1m", limit=10)
        top_serbest = top_funds_by_return(serbest_funds, "return_1y", limit=5)

        sections = [
            ("fund_section", build_fund_section_prompt(top_standart)),
            ("serbest_fund_section", build_serbest_fund_prompt(top_serbest)),
            ("repo_section", build_repo_section_prompt(snapshot.repo_rates)),
            ("news_section", build_news_section_prompt(snapshot.news)),
            ("summary_section", build_summary_prompt(snapshot, {})),
        ]

        # Bölümleri paralel oluştur
        tasks = [
            self._call_claude(client, prompt) for _, prompt in sections
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for (field_name, _), result in zip(sections, results):
            if isinstance(result, Exception):
                report.errors.append(f"{field_name}: {result}")
                setattr(report, field_name, None)
            else:
                setattr(report, field_name, result)

        # DİBS, sukuk, eurobond için basit metin (AI yok, ham veri özeti)
        report.bond_section = self._format_bonds_simple(snapshot)
        report.sukuk_section = self._format_sukuks_simple(snapshot)
        report.eurobond_section = self._format_eurobonds_simple(snapshot)

        return report

    async def _call_claude(
        self,
        client: anthropic.AsyncAnthropic,
        prompt: str,
    ) -> str:
        """Claude API'ye tek bir çağrı yap."""
        response = await client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    @staticmethod
    def _format_bonds_simple(snapshot: MarketSnapshot) -> str:
        """DİBS için basit format (AI'sız)."""
        if not snapshot.bonds:
            return "🏛️ *DİBS / DEVLET TAHVİLLERİ*\n\nBugün veri alınamadı."
        lines = ["🏛️ *DİBS / DEVLET TAHVİLLERİ*\n"]
        sorted_bonds = sorted(snapshot.bonds, key=lambda b: b.yield_rate, reverse=True)
        for b in sorted_bonds[:5]:
            lines.append(
                f"• {b.isin} | Vade: {b.maturity_date} | Getiri: %{b.yield_rate}"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_sukuks_simple(snapshot: MarketSnapshot) -> str:
        """Sukuk için basit format."""
        if not snapshot.sukuks:
            return "🕌 *KİRA SERTİFİKALARI (SUKUK)*\n\nBugün veri alınamadı."
        lines = ["🕌 *KİRA SERTİFİKALARI (SUKUK)*\n"]
        sorted_sukuks = sorted(snapshot.sukuks, key=lambda s: s.yield_rate, reverse=True)
        for s in sorted_sukuks[:5]:
            lines.append(
                f"• {s.isin} | İhraççı: {s.issuer} | Vade: {s.maturity_date} | "
                f"Getiri: %{s.yield_rate}"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_eurobonds_simple(snapshot: MarketSnapshot) -> str:
        """Eurobond için basit format."""
        if not snapshot.eurobonds:
            return "🌍 *EUROBOND*\n\nBugün veri alınamadı."
        lines = ["🌍 *EUROBOND*\n"]
        sorted_eb = sorted(snapshot.eurobonds, key=lambda e: e.yield_rate, reverse=True)
        for e in sorted_eb[:5]:
            lines.append(
                f"• {e.isin} | {e.currency} | Vade: {e.maturity_date} | "
                f"Getiri: %{e.yield_rate}"
            )
        return "\n".join(lines)
