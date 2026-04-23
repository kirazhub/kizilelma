"""Telegram mesaj formatters testleri."""
import datetime as dt

from kizilelma.ai_advisor.advisor import AdvisorReport
from kizilelma.telegram_bot.formatters import (
    split_into_messages,
    add_header_and_footer,
    sanitize_markdown,
    MAX_MESSAGE_LENGTH,
)


def test_split_into_messages_returns_8_sections():
    """AdvisorReport 8 bölümlük mesaj listesine çevrilir (boş olanlar atılır)."""
    report = AdvisorReport(
        fund_section="📊 Fonlar içerik",
        serbest_fund_section="💎 Serbest içerik",
        bond_section="🏛️ Tahvil içerik",
        sukuk_section="🕌 Sukuk içerik",
        repo_section="🔄 Repo içerik",
        eurobond_section="🌍 Eurobond içerik",
        news_section="📰 Haberler içerik",
        summary_section="🎯 Özet içerik",
    )
    messages = split_into_messages(report)
    assert len(messages) == 8


def test_split_skips_empty_sections():
    """None veya boş bölümler mesaj listesine eklenmez."""
    report = AdvisorReport(
        fund_section="📊 Var",
        summary_section="🎯 Var",
    )
    messages = split_into_messages(report)
    assert len(messages) == 2


def test_long_message_is_split():
    """Telegram limiti (4096 karakter) aşan mesaj parçalanır."""
    long_text = "📊 Test\n" + ("a" * 5000)
    report = AdvisorReport(fund_section=long_text)
    messages = split_into_messages(report)
    assert all(len(m) <= MAX_MESSAGE_LENGTH for m in messages)
    assert len(messages) >= 2  # Parçalandı


def test_add_header_and_footer():
    """Mesajlara başlık ve altlık eklenir."""
    timestamp = dt.datetime(2026, 4, 23, 10, 0)
    msg = add_header_and_footer("İçerik", timestamp=timestamp, index=1, total=8)
    assert "23.04.2026" in msg or "Nisan" in msg
    assert "1/8" in msg
    assert "İçerik" in msg


def test_sanitize_markdown_does_not_break():
    """sanitize_markdown çağrılabilir (esnek davranış)."""
    text = "Test (parantez) ve _alt_ ve *yıldız*"
    result = sanitize_markdown(text)
    assert isinstance(result, str)
