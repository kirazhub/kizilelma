"""Telegram bot gönderici testleri."""
from unittest.mock import AsyncMock, patch

import pytest

from kizilelma.ai_advisor.advisor import AdvisorReport
from kizilelma.telegram_bot.bot import TelegramSender


@pytest.mark.asyncio
async def test_telegram_sender_sends_each_message():
    """Her bölüm ayrı mesaj olarak gönderilir."""
    report = AdvisorReport(
        fund_section="📊 Fonlar",
        summary_section="🎯 Özet",
    )

    fake_bot = AsyncMock()
    fake_bot.send_message = AsyncMock()

    with patch("kizilelma.telegram_bot.bot.Bot", return_value=fake_bot):
        sender = TelegramSender(token="x", chat_id="123")
        sent_count = await sender.send_report(report)

    assert sent_count == 2
    assert fake_bot.send_message.call_count == 2


@pytest.mark.asyncio
async def test_telegram_sender_continues_on_individual_failure():
    """Bir mesaj başarısız olursa diğerleri yine gönderilir."""
    report = AdvisorReport(
        fund_section="📊 İlk",
        bond_section="🏛️ İkinci",
        summary_section="🎯 Üçüncü",
    )

    # Sade metin gönderilir (parse_mode yok), bir hata olursa sadece
    # o mesaj atlanır, diğerleri akar.
    fake_bot = AsyncMock()
    fake_bot.send_message = AsyncMock(
        side_effect=[
            None,  # 1. mesaj OK
            Exception("Network error"),  # 2. mesaj fail
            None,  # 3. mesaj OK
        ]
    )

    with patch("kizilelma.telegram_bot.bot.Bot", return_value=fake_bot):
        sender = TelegramSender(token="x", chat_id="123")
        sent_count = await sender.send_report(report)

    # 3 denendi, 2 başarılı (1. ve 3.)
    assert sent_count == 2
    assert fake_bot.send_message.call_count == 3


@pytest.mark.asyncio
async def test_send_test_message_works():
    """Manuel test mesajı gönderme."""
    fake_bot = AsyncMock()
    fake_bot.send_message = AsyncMock()

    with patch("kizilelma.telegram_bot.bot.Bot", return_value=fake_bot):
        sender = TelegramSender(token="x", chat_id="123")
        await sender.send_test_message("Merhaba dünya")

    fake_bot.send_message.assert_called_once()
