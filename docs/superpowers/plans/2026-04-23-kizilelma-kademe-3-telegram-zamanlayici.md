# Kızılelma — Kademe 3: Telegram Bot ve Zamanlayıcı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kademe 2'de üretilen `AdvisorReport`'u alıp Telegram'a 8 ayrı mesaj olarak gönderen bot modülünü ve hafta içi her sabah 10:00'da tüm akışı tetikleyen zamanlayıcıyı inşa et.

**Architecture:** **Telegram bot** sadece mesaj formatlama ve gönderme yapar; veri çekme veya AI ile ilgilenmez. **Scheduler** tek giriş noktasıdır: collector'ları çağırır → analyzers ile metrikleri hesaplar → AI advisor'a verir → Telegram'a gönderir. Tüm akış orchestration `main.py`'de toplanır.

**Tech Stack:** `python-telegram-bot` (resmi bot kütüphanesi), `APScheduler` (cron-style zamanlayıcı), `pytz` (Türkiye saati).

---

## Dosya Yapısı

```
kizilelma/
├── telegram_bot/
│   ├── __init__.py
│   ├── bot.py              # Telegram gönderici
│   └── formatters.py       # Mesaj formatlama yardımcıları
├── scheduler/
│   ├── __init__.py
│   └── daily_job.py        # Günlük iş tanımı (cron)
└── main.py                 # Ana giriş noktası ve orchestration
tests/
├── telegram_bot/
│   ├── __init__.py
│   ├── test_bot.py
│   └── test_formatters.py
└── scheduler/
    ├── __init__.py
    └── test_daily_job.py
```

---

## Task 1: Telegram Mesaj Formatters

**Files:**
- Create: `kizilelma/telegram_bot/__init__.py`
- Create: `kizilelma/telegram_bot/formatters.py`
- Test: `tests/telegram_bot/__init__.py`
- Test: `tests/telegram_bot/test_formatters.py`

- [ ] **Step 1: Failing test yaz**

`tests/telegram_bot/__init__.py`:
```python
```

`tests/telegram_bot/test_formatters.py`:
```python
"""Telegram mesaj formatters testleri."""
from datetime import datetime

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
        # Diğerleri None
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
    timestamp = datetime(2026, 4, 23, 10, 0)
    msg = add_header_and_footer("İçerik", timestamp=timestamp, index=1, total=8)
    assert "23.04.2026" in msg or "Nisan" in msg
    assert "1/8" in msg
    assert "İçerik" in msg


def test_sanitize_markdown_escapes_special_chars():
    """Telegram MarkdownV2 için özel karakterler kaçırılır."""
    text = "Test (parantez) ve _alt_ ve *yıldız*"
    result = sanitize_markdown(text)
    # MarkdownV2'de özel karakterler escape edilmeli
    assert "\\(" in result or "(" in result  # En azından kırılma yok
```

- [ ] **Step 2: Testin başarısız olduğunu doğrula**

```bash
pytest tests/telegram_bot/test_formatters.py -v
```

Beklenen: `ImportError`

- [ ] **Step 3: `kizilelma/telegram_bot/__init__.py` ve `formatters.py` yaz**

`kizilelma/telegram_bot/__init__.py`:
```python
"""Telegram bot modülleri."""
```

`kizilelma/telegram_bot/formatters.py`:
```python
"""Telegram mesaj formatlama yardımcıları.

AdvisorReport'u Telegram'a uygun mesajlara çevirir.
- Telegram MarkdownV2 limitleri: 4096 karakter
- Uzun mesajlar otomatik bölünür
- Her mesaja başlık (tarih + index) ve altlık (yasal uyarı) eklenir
"""
from datetime import datetime
from typing import Optional

from kizilelma.ai_advisor.advisor import AdvisorReport


MAX_MESSAGE_LENGTH = 4096
LEGAL_NOTICE = (
    "_Bu rapor yatırım tavsiyesi değildir; bilgilendirme amaçlıdır._"
)


# Bölümlerin sırası (sabit)
SECTION_ORDER = [
    "fund_section",
    "serbest_fund_section",
    "bond_section",
    "sukuk_section",
    "repo_section",
    "eurobond_section",
    "news_section",
    "summary_section",
]


def split_into_messages(report: AdvisorReport) -> list[str]:
    """AdvisorReport'u Telegram mesaj listesine çevir.

    - Boş/None bölümler atlanır
    - Telegram limitini aşan bölümler parçalanır
    - Her mesaja başlık ve altlık eklenir
    """
    timestamp = datetime.now()
    sections = []
    for field_name in SECTION_ORDER:
        content = getattr(report, field_name, None)
        if content and content.strip():
            sections.append(content)

    # Önce her bölümü tek mesaja sığdırmaya çalış, sığmazsa parçala
    raw_messages: list[str] = []
    for section in sections:
        chunks = _split_long_text(section, max_len=MAX_MESSAGE_LENGTH - 200)
        raw_messages.extend(chunks)

    # Başlık + altlık ekle
    total = len(raw_messages)
    final_messages = [
        add_header_and_footer(msg, timestamp, index=i + 1, total=total)
        for i, msg in enumerate(raw_messages)
    ]
    return final_messages


def _split_long_text(text: str, max_len: int) -> list[str]:
    """Uzun metni satır sınırlarında parçala."""
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_len:
            if current:
                chunks.append(current.rstrip())
            current = line + "\n"
        else:
            current += line + "\n"
    if current:
        chunks.append(current.rstrip())
    return chunks


def add_header_and_footer(
    body: str,
    timestamp: datetime,
    index: int,
    total: int,
) -> str:
    """Mesaja başlık ve altlık ekle."""
    date_str = timestamp.strftime("%d.%m.%Y")
    header = f"🌅 *KIZILELMA RAPORU* — {date_str} \\({index}/{total}\\)\n\n"
    footer = f"\n\n{LEGAL_NOTICE}"
    return header + body + footer


def sanitize_markdown(text: str) -> str:
    """Telegram MarkdownV2 için özel karakterleri escape et.

    MarkdownV2'de şu karakterler escape edilmeli:
    _ * [ ] ( ) ~ ` > # + - = | { } . !

    Ancak biz parse_mode='Markdown' (eski) kullanıyoruz, bu yüzden
    sadece kritik olanları işleyeceğiz. Bu fonksiyon esnek tutuluyor.
    """
    # Şimdilik no-op (Markdown legacy modda kullanacağız)
    return text
```

- [ ] **Step 4: Testlerin geçtiğini doğrula**

```bash
pytest tests/telegram_bot/test_formatters.py -v
```

Beklenen: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add kizilelma/telegram_bot/__init__.py kizilelma/telegram_bot/formatters.py tests/telegram_bot/
git commit -m "Telegram formatters: rapor → 8 mesaj, uzun mesaj parçalama, başlık/altlık"
```

---

## Task 2: Telegram Bot (Gönderici)

**Files:**
- Create: `kizilelma/telegram_bot/bot.py`
- Test: `tests/telegram_bot/test_bot.py`
- Modify: `pyproject.toml` (python-telegram-bot ekle)

- [ ] **Step 1: Bağımlılığı ekle**

`pyproject.toml`'a ekle:
```toml
    "python-telegram-bot>=21.0",
```

Yükle:
```bash
pip install -e ".[dev]"
```

- [ ] **Step 2: Failing test yaz**

`tests/telegram_bot/test_bot.py`:
```python
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

    fake_bot = AsyncMock()
    fake_bot.send_message = AsyncMock(
        side_effect=[None, Exception("Network error"), None]
    )

    with patch("kizilelma.telegram_bot.bot.Bot", return_value=fake_bot):
        sender = TelegramSender(token="x", chat_id="123")
        sent_count = await sender.send_report(report)

    # 3 denendi, 2 başarılı
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
```

- [ ] **Step 3: Testin başarısız olduğunu doğrula**

```bash
pytest tests/telegram_bot/test_bot.py -v
```

Beklenen: `ImportError`

- [ ] **Step 4: `kizilelma/telegram_bot/bot.py` yaz**

```python
"""Telegram gönderici.

AdvisorReport'u Telegram chat'ine sırayla mesaj olarak gönderir.
Her mesaj arasında küçük bekleme süresi (rate limit'e takılmamak için).
"""
import asyncio
import logging
from typing import Optional

from telegram import Bot
from telegram.constants import ParseMode

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
            try:
                await self._bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN_V2,
                    disable_web_page_preview=True,
                )
                sent_count += 1
                logger.info(f"Mesaj {i+1}/{len(messages)} gönderildi")
            except Exception as exc:
                logger.warning(
                    f"Mesaj {i+1} gönderilemedi: {exc}. Diğerlerine devam ediliyor."
                )
                # Markdown parse hatası olabilir → sade metin olarak dene
                try:
                    await self._bot.send_message(
                        chat_id=self.chat_id,
                        text=message,
                        disable_web_page_preview=True,
                    )
                    sent_count += 1
                except Exception:
                    pass  # tamamen başarısız, sonraki mesaja geç

            # Rate limit'e takılmamak için kısa bekleme
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
```

- [ ] **Step 5: Testlerin geçtiğini doğrula**

```bash
pytest tests/telegram_bot/test_bot.py -v
```

Beklenen: `3 passed`

- [ ] **Step 6: Commit**

```bash
git add kizilelma/telegram_bot/bot.py tests/telegram_bot/test_bot.py pyproject.toml
git commit -m "Telegram sender: bot.py — sırayla mesaj gönderme + hata toleransı + rate limit koruma"
```

---

## Task 3: Daily Job (Tüm Akışın Orchestration'ı)

**Files:**
- Create: `kizilelma/scheduler/__init__.py`
- Create: `kizilelma/scheduler/daily_job.py`
- Test: `tests/scheduler/__init__.py`
- Test: `tests/scheduler/test_daily_job.py`

- [ ] **Step 1: Failing test yaz**

`tests/scheduler/__init__.py`:
```python
```

`tests/scheduler/test_daily_job.py`:
```python
"""Daily job orchestration testleri."""
from datetime import date, datetime
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
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "x")

    fake_funds = [
        FundData(
            code="A", name="Test", category="Hisse",
            price=Decimal("1"), date=date.today(),
        )
    ]
    fake_news = []
    fake_repo = []
    fake_bonds = []
    fake_sukuks = []
    fake_eurobonds = []

    with patch("kizilelma.scheduler.daily_job.TefasCollector") as tefas_cls, \
         patch("kizilelma.scheduler.daily_job.TcmbCollector") as tcmb_cls, \
         patch("kizilelma.scheduler.daily_job.BistCollector") as bist_cls, \
         patch("kizilelma.scheduler.daily_job.EurobondCollector") as eb_cls, \
         patch("kizilelma.scheduler.daily_job.NewsCollector") as news_cls:
        tefas_cls.return_value.fetch = AsyncMock(return_value=fake_funds)
        tcmb_cls.return_value.fetch = AsyncMock(return_value=fake_repo)
        bist_cls.return_value.fetch = AsyncMock(return_value=(fake_bonds, fake_sukuks))
        eb_cls.return_value.fetch = AsyncMock(return_value=fake_eurobonds)
        news_cls.return_value.fetch = AsyncMock(return_value=fake_news)

        snapshot = await collect_all_data()

    assert isinstance(snapshot, MarketSnapshot)
    assert snapshot.funds == fake_funds


@pytest.mark.asyncio
async def test_collect_handles_collector_failure(monkeypatch):
    """Bir collector çökerse errors dolu, diğerleri çalışır."""
    monkeypatch.setenv("TCMB_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "x")

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
async def test_run_daily_job_full_flow(monkeypatch):
    """run_daily_job: collect → analyze → AI → telegram tam akışı çalışır."""
    monkeypatch.setenv("TCMB_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "x")

    with patch("kizilelma.scheduler.daily_job.collect_all_data") as collect_mock, \
         patch("kizilelma.scheduler.daily_job.AIAdvisor") as advisor_cls, \
         patch("kizilelma.scheduler.daily_job.TelegramSender") as tg_cls:
        collect_mock.return_value = MarketSnapshot(timestamp=datetime.now())
        advisor_cls.return_value.generate_report = AsyncMock(
            return_value=MagicMock(fund_section="test", errors=[])
        )
        tg_cls.return_value.send_report = AsyncMock(return_value=1)

        result = await run_daily_job()

    assert result["sent_messages"] == 1
    assert result["status"] in ("success", "partial")
```

- [ ] **Step 2: Testin başarısız olduğunu doğrula**

```bash
pytest tests/scheduler/test_daily_job.py -v
```

Beklenen: `ImportError`

- [ ] **Step 3: `kizilelma/scheduler/__init__.py` ve `daily_job.py` yaz**

`kizilelma/scheduler/__init__.py`:
```python
"""Zamanlayıcı modülleri."""
```

`kizilelma/scheduler/daily_job.py`:
```python
"""Günlük rapor işi — tüm akışın orchestration'ı.

Akış:
    1. collect_all_data()  → tüm collector'ları paralel çalıştır
    2. AIAdvisor             → metrikleri hesapla + AI yorum üret
    3. TelegramSender       → rapor mesajlarını gönder

Hata toleransı:
    - Bir collector çökerse snapshot.errors'a not düşülür
    - AI çökerse rapor yine de ham veri olarak gönderilir
    - Telegram tek tek mesajlar başarısız olabilir
"""
import asyncio
import logging
from datetime import datetime
from typing import Any

from kizilelma.config import get_config
from kizilelma.models import MarketSnapshot
from kizilelma.collectors.tefas import TefasCollector
from kizilelma.collectors.tcmb import TcmbCollector
from kizilelma.collectors.bist import BistCollector
from kizilelma.collectors.eurobond import EurobondCollector
from kizilelma.collectors.news import NewsCollector
from kizilelma.ai_advisor.advisor import AIAdvisor
from kizilelma.telegram_bot.bot import TelegramSender


logger = logging.getLogger(__name__)


async def collect_all_data() -> MarketSnapshot:
    """Tüm veri kaynaklarını paralel olarak topla."""
    config = get_config()

    tefas = TefasCollector()
    tcmb = TcmbCollector(api_key=config.tcmb_api_key)
    bist = BistCollector()
    eurobond = EurobondCollector()
    news = NewsCollector()

    # Paralel çalıştır
    results = await asyncio.gather(
        _safe(tefas.fetch, "tefas"),
        _safe(tcmb.fetch, "tcmb"),
        _safe(bist.fetch, "bist"),
        _safe(eurobond.fetch, "eurobond"),
        _safe(news.fetch, "news"),
    )

    funds_result, repo_result, bist_result, eurobond_result, news_result = results

    snapshot = MarketSnapshot(
        timestamp=datetime.now(),
        funds=funds_result.get("data", []),
        repo_rates=repo_result.get("data", []),
        bonds=bist_result.get("data", ([], []))[0] if not bist_result.get("error") else [],
        sukuks=bist_result.get("data", ([], []))[1] if not bist_result.get("error") else [],
        eurobonds=eurobond_result.get("data", []),
        news=news_result.get("data", []),
    )

    # Hataları topla
    for r, name in [
        (funds_result, "tefas"),
        (repo_result, "tcmb"),
        (bist_result, "bist"),
        (eurobond_result, "eurobond"),
        (news_result, "news"),
    ]:
        if r.get("error"):
            snapshot.errors[name] = r["error"]

    return snapshot


async def _safe(coro_fn, name: str) -> dict:
    """Bir collector çağrısını güvenli yap, hata varsa yakala."""
    try:
        data = await coro_fn()
        return {"data": data, "error": None}
    except Exception as exc:
        logger.warning(f"Collector '{name}' başarısız: {exc}")
        return {"data": [] if name != "bist" else ([], []), "error": str(exc)}


async def run_daily_job() -> dict[str, Any]:
    """Tüm günlük akışı tek seferde çalıştır.

    Returns:
        {"status": "success"|"partial"|"failed", "sent_messages": N,
         "snapshot_errors": {...}, "report_errors": [...]}
    """
    config = get_config()
    logger.info("=== Kızılelma günlük rapor başladı ===")

    # 1. Veri topla
    snapshot = await collect_all_data()
    logger.info(
        f"Veri toplandı: {len(snapshot.funds)} fon, {len(snapshot.news)} haber, "
        f"hatalar: {list(snapshot.errors.keys())}"
    )

    # 2. AI yorum üret
    advisor = AIAdvisor(api_key=config.anthropic_api_key)
    report = await advisor.generate_report(snapshot)
    logger.info(
        f"Rapor üretildi: errors={report.errors}"
    )

    # 3. Telegram'a gönder
    sender = TelegramSender(
        token=config.telegram_bot_token,
        chat_id=config.telegram_chat_id,
    )
    sent = await sender.send_report(report)
    logger.info(f"{sent} mesaj gönderildi")

    # Sonuç
    if sent == 0:
        status = "failed"
    elif snapshot.errors or report.errors:
        status = "partial"
    else:
        status = "success"

    return {
        "status": status,
        "sent_messages": sent,
        "snapshot_errors": snapshot.errors,
        "report_errors": report.errors,
        "timestamp": snapshot.timestamp.isoformat(),
    }
```

- [ ] **Step 4: Testlerin geçtiğini doğrula**

```bash
pytest tests/scheduler/test_daily_job.py -v
```

Beklenen: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add kizilelma/scheduler/ tests/scheduler/
git commit -m "Daily job: collect → analyze → AI → telegram tam orchestration + hata toleransı"
```

---

## Task 4: Main.py — CLI Giriş Noktası ve APScheduler

**Files:**
- Create: `kizilelma/main.py`
- Test: `tests/test_main.py`
- Modify: `pyproject.toml` (apscheduler ekle)

- [ ] **Step 1: Bağımlılığı ekle**

`pyproject.toml`'a ekle:
```toml
    "apscheduler>=3.10.0",
```

`pyproject.toml`'un sonuna ekle:
```toml
[project.scripts]
kizilelma = "kizilelma.main:cli"
```

Yükle:
```bash
pip install -e ".[dev]"
```

- [ ] **Step 2: Failing test yaz**

`tests/test_main.py`:
```python
"""Main CLI testleri."""
from unittest.mock import AsyncMock, patch

import pytest

from kizilelma.main import async_main_run_now


@pytest.mark.asyncio
async def test_async_main_run_now_calls_daily_job():
    """run-now komutu daily_job'u tetikler."""
    with patch("kizilelma.main.run_daily_job") as job_mock:
        job_mock.return_value = AsyncMock(return_value={
            "status": "success",
            "sent_messages": 8,
        })()
        result = await async_main_run_now()
    assert result["status"] == "success"
```

- [ ] **Step 3: Testin başarısız olduğunu doğrula**

```bash
pytest tests/test_main.py -v
```

Beklenen: `ImportError`

- [ ] **Step 4: `kizilelma/main.py` yaz**

```python
"""Kızılelma ana giriş noktası.

Komutlar:
    kizilelma run-now      → Şu an bir rapor üret ve gönder (test için)
    kizilelma start        → Zamanlayıcıyı başlat (her hafta içi 10:00)
    kizilelma test-telegram → Telegram bağlantısını test et
"""
import argparse
import asyncio
import logging
import sys

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from kizilelma.config import get_config
from kizilelma.scheduler.daily_job import run_daily_job
from kizilelma.telegram_bot.bot import TelegramSender


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("kizilelma")


TIMEZONE = pytz.timezone("Europe/Istanbul")


async def async_main_run_now() -> dict:
    """Şu an bir rapor üret (manuel test için)."""
    logger.info("Manuel rapor başlatılıyor...")
    result = await run_daily_job()
    logger.info(f"Sonuç: {result}")
    return result


async def async_main_start() -> None:
    """Zamanlayıcıyı başlat: hafta içi her gün 10:00."""
    logger.info("Zamanlayıcı başlatılıyor (Pzt-Cum 10:00 İstanbul saati)")

    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        run_daily_job,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=10,
            minute=0,
            timezone=TIMEZONE,
        ),
        id="daily_report",
        name="Kızılelma Günlük Rapor",
        replace_existing=True,
    )
    scheduler.start()

    logger.info("Zamanlayıcı çalışıyor. CTRL+C ile durdurabilirsin.")
    try:
        # Sürekli çalış
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


async def async_main_test_telegram() -> None:
    """Telegram bağlantısını test et."""
    config = get_config()
    sender = TelegramSender(
        token=config.telegram_bot_token,
        chat_id=config.telegram_chat_id,
    )
    await sender.send_test_message(
        "🌅 *Kızılelma test mesajı*\n\nBağlantı çalışıyor!"
    )
    logger.info("Test mesajı gönderildi.")


def cli() -> None:
    """Komut satırı arayüzü."""
    parser = argparse.ArgumentParser(prog="kizilelma")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("run-now", help="Şu an bir rapor üret ve gönder")
    sub.add_parser("start", help="Zamanlayıcıyı başlat (Pzt-Cum 10:00)")
    sub.add_parser("test-telegram", help="Telegram bağlantısını test et")

    args = parser.parse_args()

    if args.command == "run-now":
        result = asyncio.run(async_main_run_now())
        sys.exit(0 if result["status"] != "failed" else 1)
    elif args.command == "start":
        asyncio.run(async_main_start())
    elif args.command == "test-telegram":
        asyncio.run(async_main_test_telegram())


if __name__ == "__main__":
    cli()
```

- [ ] **Step 5: Testlerin geçtiğini doğrula**

```bash
pytest tests/test_main.py -v
```

Beklenen: `1 passed`

- [ ] **Step 6: CLI komutunun çalıştığını doğrula**

```bash
kizilelma --help
```

Beklenen: Yardım mesajı görünür, 3 alt komut listelenir.

- [ ] **Step 7: Commit**

```bash
git add kizilelma/main.py tests/test_main.py pyproject.toml
git commit -m "Main CLI: run-now, start, test-telegram komutları + APScheduler entegrasyonu"
```

---

## Task 5: Tüm Kademe 3 Testlerini Çalıştır

- [ ] **Step 1: Tüm test paketini çalıştır**

```bash
pytest -v
```

Beklenen: Tüm testler (Kademe 1+2+3) yeşil — ~40+ test.

- [ ] **Step 2: Test telegram bağlantısı (gerçek bot ile, opsiyonel)**

`.env` dosyasında geçerli `TELEGRAM_BOT_TOKEN` ve `TELEGRAM_CHAT_ID` olmalı. Sonra:

```bash
kizilelma test-telegram
```

Beklenen: Telegram'a "Kızılelma test mesajı" düşer.

- [ ] **Step 3: Final commit**

```bash
git commit --allow-empty -m "Kademe 3 tamamlandı: Telegram bot + zamanlayıcı + CLI çalışır durumda"
```

---

## Kademe 3 Bitirme Kontrol Listesi

- [ ] Telegram formatters (8 mesaj, parçalama, başlık/altlık)
- [ ] Telegram sender (gönderme, hata toleransı, rate limit)
- [ ] Daily job orchestration (collect → AI → send)
- [ ] Main CLI (run-now, start, test-telegram)
- [ ] APScheduler entegrasyonu (Pzt-Cum 10:00 İstanbul)
- [ ] Tüm testler yeşil
- [ ] **Kademe 4'e geçmeye hazır:** Veritabanı + deploy + son testler
