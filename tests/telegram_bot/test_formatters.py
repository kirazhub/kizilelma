"""Telegram mesaj formatters testleri."""
import datetime as dt

from kizilelma.ai_advisor.advisor import AdvisorReport
from kizilelma.telegram_bot.formatters import (
    split_into_messages,
    add_header_and_footer,
    sanitize_markdown,
    MAX_MESSAGE_LENGTH,
)


def test_split_into_messages_returns_all_sections():
    """AdvisorReport tüm veri bölümleri için mesaj üretir (haber hariç).

    Yeni yapıda 11 bölüm var: 6 fon kategorisi + 4 sabit getirili + özet.
    news_section kullanıcı talebiyle kaldırıldı; doldurulsa bile SECTION_ORDER
    içinde olmadığı için mesaj olarak gönderilmez.
    """
    report = AdvisorReport(
        fund_section="📊 Para Piy.",
        hisse_section="📈 Hisse",
        karma_section="🎯 Karma",
        serbest_fund_section="💎 Serbest",
        katilim_section="🕌 Katılım",
        borc_section="📜 Borçlanma",
        bond_section="🏛️ Tahvil",
        sukuk_section="🕌 Sukuk",
        eurobond_section="🌍 Eurobond",
        repo_section="🔄 Repo",
        summary_section="🎯 Özet",
    )
    messages = split_into_messages(report)
    assert len(messages) == 11


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
