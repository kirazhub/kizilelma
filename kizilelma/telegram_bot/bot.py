"""Telegram gönderici.

AdvisorReport'u Telegram chat'ine sırayla mesaj olarak gönderir.
Her mesaj arasında küçük bekleme süresi (rate limit'e takılmamak için).
"""
import asyncio
import logging

from telegram import Bot

from kizilelma.ai_advisor.advisor import AdvisorReport
from kizilelma.telegram_bot.formatters import split_into_messages


logger = logging.getLogger(__name__)

DELAY_BETWEEN_MESSAGES = 0.5  # saniye (Telegram limit: ~30 msg/sec)


class TelegramSender:
    """Telegram bot üzerinden rapor gönderir."""

    def __init__(self, token: str, chat_id: str) -> None:
        self.token = token
        self.chat_id = chat_id
        self._bot = Bot(token=token)

    async def send_report(self, report: AdvisorReport) -> int:
        """Raporu mesaj mesaj gönder.

        Returns:
            Başarılı gönderilen mesaj sayısı
        """
        messages = split_into_messages(report)
        sent_count = 0

        for i, message in enumerate(messages):
            success = False
            try:
                # Sade metin (parse_mode yok) — Telegram MarkdownV2 escape
                # sorunlarını tamamen baypas etmek için. Emoji ve satır sonları
                # yeterli okunabilirlik sağlıyor.
                await self._bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    disable_web_page_preview=True,
                )
                success = True
                logger.info(f"Mesaj {i+1}/{len(messages)} gönderildi")
            except Exception as exc:
                logger.error(f"Mesaj {i+1} gönderilemedi: {exc}")

            if success:
                sent_count += 1

            # Rate limit koruması
            if i < len(messages) - 1:
                await asyncio.sleep(DELAY_BETWEEN_MESSAGES)

        return sent_count

    async def send_test_message(self, text: str = "Kızılelma test mesajı 🌅") -> None:
        """Manuel test için tek mesaj gönder."""
        await self._bot.send_message(
            chat_id=self.chat_id,
            text=text,
            disable_web_page_preview=True,
        )
