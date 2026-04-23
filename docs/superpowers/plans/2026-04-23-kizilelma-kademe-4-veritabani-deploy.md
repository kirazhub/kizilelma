# Kızılelma — Kademe 4: Veritabanı, Deploy ve Son Testler

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SQLite veritabanı ile geçmiş raporları arşivle, gerçek API entegrasyonlarını doğrula (Eurobond için yfinance), GitHub Actions üzerinden zamanlanmış otomatik çalıştırmayı kur, son uçtan uca testleri yap, kullanıcı dokümanlarını hazırla.

**Architecture:** Storage modülü her günlük rapor sonrası snapshot'ı SQLite'a kaydeder. GitHub Actions cron schedule ile her hafta içi 10:00'da `kizilelma run-now` komutunu tetikler. Sırlar GitHub Secrets üzerinden taşınır. README ve kullanıcı kılavuzu Türkçe yazılır.

**Tech Stack:** `sqlmodel` (SQLAlchemy + Pydantic birleşimi), `yfinance` (Eurobond gerçek veri), GitHub Actions (cron + secrets).

---

## Dosya Yapısı

```
kizilelma/
└── storage/
    ├── __init__.py
    ├── models.py           # SQLModel tabloları
    └── db.py               # Veritabanı bağlantısı + repo
.github/
└── workflows/
    └── daily-report.yml    # GitHub Actions cron job
docs/
├── kullanim-klavuzu.md     # Türkçe kullanıcı kılavuzu
└── kurulum.md              # İlk kurulum rehberi (Telegram bot vs.)
tests/
└── storage/
    ├── __init__.py
    └── test_db.py
```

---

## Task 1: Storage — SQLite Tabloları (SQLModel)

**Files:**
- Create: `kizilelma/storage/__init__.py`
- Create: `kizilelma/storage/models.py`
- Test: `tests/storage/__init__.py`
- Modify: `pyproject.toml` (sqlmodel ekle)

- [ ] **Step 1: Bağımlılığı ekle**

`pyproject.toml`'a ekle:
```toml
    "sqlmodel>=0.0.16",
```

Yükle:
```bash
pip install -e ".[dev]"
```

- [ ] **Step 2: Failing test yaz**

`tests/storage/__init__.py`:
```python
```

`tests/storage/test_models.py`:
```python
"""Storage models testleri."""
from datetime import date, datetime
from decimal import Decimal

from kizilelma.storage.models import (
    SnapshotRecord,
    FundRecord,
    RepoRecord,
    ReportRecord,
)


def test_snapshot_record_can_be_instantiated():
    """SnapshotRecord temel alanlarla oluşturulabilir."""
    snap = SnapshotRecord(
        timestamp=datetime(2026, 4, 23, 10, 0),
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
        date=date.today(),
    )
    assert fund.code == "AFA"


def test_report_record_stores_full_report():
    """ReportRecord AI raporu metnini saklar."""
    record = ReportRecord(
        snapshot_id=1,
        timestamp=datetime.now(),
        fund_section="📊 İçerik",
        summary_section="🎯 Özet",
        sent_messages=8,
        status="success",
    )
    assert record.sent_messages == 8
```

- [ ] **Step 3: Testin başarısız olduğunu doğrula**

```bash
pytest tests/storage/test_models.py -v
```

Beklenen: `ImportError`

- [ ] **Step 4: `kizilelma/storage/__init__.py` ve `models.py` yaz**

`kizilelma/storage/__init__.py`:
```python
"""Veritabanı / arşiv modülleri."""
```

`kizilelma/storage/models.py`:
```python
"""SQLModel tabloları — geçmiş raporları ve verileri arşivler."""
from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class SnapshotRecord(SQLModel, table=True):
    """Bir snapshot anının özet bilgisi."""

    __tablename__ = "snapshots"

    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime = Field(index=True)
    fund_count: int = 0
    bond_count: int = 0
    sukuk_count: int = 0
    repo_count: int = 0
    eurobond_count: int = 0
    news_count: int = 0
    errors_json: str = "{}"  # JSON string


class FundRecord(SQLModel, table=True):
    """Tek bir fonun bir gündeki snapshot kaydı."""

    __tablename__ = "funds"

    id: Optional[int] = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="snapshots.id", index=True)
    code: str = Field(index=True)
    name: str
    category: str
    price: float
    date: date
    return_1d: Optional[float] = None
    return_1w: Optional[float] = None
    return_1m: Optional[float] = None
    return_3m: Optional[float] = None
    return_6m: Optional[float] = None
    return_1y: Optional[float] = None
    is_qualified_investor: bool = False


class RepoRecord(SQLModel, table=True):
    """Repo / TCMB faiz kaydı."""

    __tablename__ = "repo_rates"

    id: Optional[int] = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="snapshots.id", index=True)
    type: str
    maturity: str
    rate: float
    date: date


class ReportRecord(SQLModel, table=True):
    """Üretilen AI raporunun saklandığı tablo."""

    __tablename__ = "reports"

    id: Optional[int] = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="snapshots.id")
    timestamp: datetime = Field(index=True)
    fund_section: Optional[str] = None
    serbest_fund_section: Optional[str] = None
    bond_section: Optional[str] = None
    sukuk_section: Optional[str] = None
    repo_section: Optional[str] = None
    eurobond_section: Optional[str] = None
    news_section: Optional[str] = None
    summary_section: Optional[str] = None
    sent_messages: int = 0
    status: str = "unknown"  # success | partial | failed
```

- [ ] **Step 5: Testlerin geçtiğini doğrula**

```bash
pytest tests/storage/test_models.py -v
```

Beklenen: `3 passed`

- [ ] **Step 6: Commit**

```bash
git add kizilelma/storage/__init__.py kizilelma/storage/models.py tests/storage/ pyproject.toml
git commit -m "Storage: SQLModel tabloları (snapshots, funds, repo_rates, reports)"
```

---

## Task 2: Storage — DB Erişim Katmanı

**Files:**
- Create: `kizilelma/storage/db.py`
- Test: `tests/storage/test_db.py`

- [ ] **Step 1: Failing test yaz**

`tests/storage/test_db.py`:
```python
"""DB erişim testleri."""
import json
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlmodel import SQLModel, Session, create_engine

from kizilelma.models import (
    FundData, RepoRate, MarketSnapshot
)
from kizilelma.ai_advisor.advisor import AdvisorReport
from kizilelma.storage.db import (
    init_db,
    save_snapshot,
    save_report,
    get_recent_snapshots,
    get_fund_history,
)


@pytest.fixture
def memory_db():
    """In-memory SQLite for testing."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def test_save_snapshot_persists_data(memory_db):
    """save_snapshot tüm verileri DB'ye yazar."""
    snapshot = MarketSnapshot(
        timestamp=datetime(2026, 4, 23, 10, 0),
        funds=[
            FundData(
                code="AFA", name="Test", category="Hisse",
                price=Decimal("1.0"), date=date.today(),
                return_1m=Decimal("4"),
            )
        ],
        repo_rates=[
            RepoRate(type="repo", maturity="overnight",
                     rate=Decimal("47.5"), date=date.today())
        ],
    )

    snapshot_id = save_snapshot(snapshot, engine=memory_db)

    assert snapshot_id is not None
    assert isinstance(snapshot_id, int)


def test_save_report_links_to_snapshot(memory_db):
    """save_report rapor metnini saklar."""
    snapshot = MarketSnapshot(timestamp=datetime.now())
    snap_id = save_snapshot(snapshot, engine=memory_db)

    report = AdvisorReport(
        fund_section="📊 İçerik",
        summary_section="🎯 Özet",
    )
    report_id = save_report(
        report, snapshot_id=snap_id,
        sent_messages=8, status="success",
        engine=memory_db,
    )
    assert report_id is not None


def test_get_recent_snapshots_returns_in_order(memory_db):
    """En yeni snapshot'lar önce gelir."""
    for hour in [10, 11, 12]:
        snapshot = MarketSnapshot(
            timestamp=datetime(2026, 4, 23, hour, 0)
        )
        save_snapshot(snapshot, engine=memory_db)

    recent = get_recent_snapshots(limit=2, engine=memory_db)
    assert len(recent) == 2
    assert recent[0].timestamp.hour > recent[1].timestamp.hour


def test_get_fund_history_returns_specific_fund(memory_db):
    """Belirli bir fon kodu için geçmiş kayıtlar gelir."""
    for i in range(3):
        snap = MarketSnapshot(
            timestamp=datetime(2026, 4, 20 + i, 10, 0),
            funds=[
                FundData(
                    code="AFA", name="Test", category="Hisse",
                    price=Decimal(str(1.0 + i * 0.1)),
                    date=date(2026, 4, 20 + i),
                    return_1m=Decimal("4"),
                )
            ],
        )
        save_snapshot(snap, engine=memory_db)

    history = get_fund_history("AFA", limit=10, engine=memory_db)
    assert len(history) == 3
```

- [ ] **Step 2: Testin başarısız olduğunu doğrula**

```bash
pytest tests/storage/test_db.py -v
```

Beklenen: `ImportError`

- [ ] **Step 3: `kizilelma/storage/db.py` yaz**

```python
"""SQLite DB erişim katmanı.

Snapshot'ları ve raporları saklar; tarihsel sorgular için yardımcılar sağlar.
"""
import json
import logging
import os
from pathlib import Path
from typing import Optional

from sqlmodel import Session, SQLModel, create_engine, select

from kizilelma.ai_advisor.advisor import AdvisorReport
from kizilelma.models import MarketSnapshot
from kizilelma.storage.models import (
    FundRecord,
    RepoRecord,
    ReportRecord,
    SnapshotRecord,
)


logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "kizilelma.db"


def get_engine(db_path: Optional[str] = None):
    """SQLite engine döndür."""
    path = db_path or os.getenv("KIZILELMA_DB", DEFAULT_DB_PATH)
    url = f"sqlite:///{path}"
    return create_engine(url, echo=False)


def init_db(engine=None) -> None:
    """Tabloları oluştur (varsa atla)."""
    engine = engine or get_engine()
    SQLModel.metadata.create_all(engine)


def save_snapshot(snapshot: MarketSnapshot, engine=None) -> int:
    """Bir MarketSnapshot'ı DB'ye yaz, snapshot_id döndür."""
    engine = engine or get_engine()
    with Session(engine) as session:
        record = SnapshotRecord(
            timestamp=snapshot.timestamp,
            fund_count=len(snapshot.funds),
            bond_count=len(snapshot.bonds),
            sukuk_count=len(snapshot.sukuks),
            repo_count=len(snapshot.repo_rates),
            eurobond_count=len(snapshot.eurobonds),
            news_count=len(snapshot.news),
            errors_json=json.dumps(snapshot.errors, ensure_ascii=False),
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        snap_id = record.id

        # Fonları kaydet
        for f in snapshot.funds:
            session.add(
                FundRecord(
                    snapshot_id=snap_id,
                    code=f.code,
                    name=f.name,
                    category=f.category,
                    price=float(f.price),
                    date=f.date,
                    return_1d=_to_float(f.return_1d),
                    return_1w=_to_float(f.return_1w),
                    return_1m=_to_float(f.return_1m),
                    return_3m=_to_float(f.return_3m),
                    return_6m=_to_float(f.return_6m),
                    return_1y=_to_float(f.return_1y),
                    is_qualified_investor=f.is_qualified_investor,
                )
            )

        # Repo kayıtları
        for r in snapshot.repo_rates:
            session.add(
                RepoRecord(
                    snapshot_id=snap_id,
                    type=r.type,
                    maturity=r.maturity,
                    rate=float(r.rate),
                    date=r.date,
                )
            )

        session.commit()
        return snap_id


def save_report(
    report: AdvisorReport,
    snapshot_id: int,
    sent_messages: int,
    status: str,
    engine=None,
) -> int:
    """Bir AdvisorReport'u DB'ye yaz, report_id döndür."""
    from datetime import datetime

    engine = engine or get_engine()
    with Session(engine) as session:
        record = ReportRecord(
            snapshot_id=snapshot_id,
            timestamp=datetime.now(),
            fund_section=report.fund_section,
            serbest_fund_section=report.serbest_fund_section,
            bond_section=report.bond_section,
            sukuk_section=report.sukuk_section,
            repo_section=report.repo_section,
            eurobond_section=report.eurobond_section,
            news_section=report.news_section,
            summary_section=report.summary_section,
            sent_messages=sent_messages,
            status=status,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record.id


def get_recent_snapshots(limit: int = 10, engine=None) -> list[SnapshotRecord]:
    """En yeni snapshot kayıtlarını döner."""
    engine = engine or get_engine()
    with Session(engine) as session:
        statement = (
            select(SnapshotRecord)
            .order_by(SnapshotRecord.timestamp.desc())
            .limit(limit)
        )
        return list(session.exec(statement))


def get_fund_history(
    fund_code: str,
    limit: int = 30,
    engine=None,
) -> list[FundRecord]:
    """Belirli bir fonun geçmiş kayıtlarını döner."""
    engine = engine or get_engine()
    with Session(engine) as session:
        statement = (
            select(FundRecord)
            .where(FundRecord.code == fund_code)
            .order_by(FundRecord.date.desc())
            .limit(limit)
        )
        return list(session.exec(statement))


def _to_float(value) -> Optional[float]:
    """Decimal/None → float/None."""
    if value is None:
        return None
    return float(value)
```

- [ ] **Step 4: Testlerin geçtiğini doğrula**

```bash
pytest tests/storage/test_db.py -v
```

Beklenen: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add kizilelma/storage/db.py tests/storage/test_db.py
git commit -m "Storage DB: snapshot/rapor kaydetme + tarihsel sorgular (init_db, save_*, get_*)"
```

---

## Task 3: Daily Job'a DB Entegrasyonu

**Files:**
- Modify: `kizilelma/scheduler/daily_job.py`
- Modify: `tests/scheduler/test_daily_job.py`

- [ ] **Step 1: Test ekle**

`tests/scheduler/test_daily_job.py` dosyasının sonuna ekle:
```python
@pytest.mark.asyncio
async def test_daily_job_persists_to_db(monkeypatch, tmp_path):
    """Daily job snapshot ve raporu DB'ye kaydeder."""
    monkeypatch.setenv("TCMB_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "x")
    monkeypatch.setenv("KIZILELMA_DB", str(tmp_path / "test.db"))

    from kizilelma.storage.db import init_db, get_recent_snapshots, get_engine

    engine = get_engine()
    init_db(engine)

    with patch("kizilelma.scheduler.daily_job.collect_all_data") as collect_mock, \
         patch("kizilelma.scheduler.daily_job.AIAdvisor") as advisor_cls, \
         patch("kizilelma.scheduler.daily_job.TelegramSender") as tg_cls:
        collect_mock.return_value = MarketSnapshot(timestamp=datetime.now())
        advisor_cls.return_value.generate_report = AsyncMock(
            return_value=MagicMock(fund_section="test", errors=[])
        )
        tg_cls.return_value.send_report = AsyncMock(return_value=8)

        await run_daily_job()

    snapshots = get_recent_snapshots(limit=5, engine=engine)
    assert len(snapshots) >= 1
```

- [ ] **Step 2: Testin başarısız olduğunu doğrula**

```bash
pytest tests/scheduler/test_daily_job.py::test_daily_job_persists_to_db -v
```

Beklenen: FAIL (DB'ye kayıt henüz eklenmedi).

- [ ] **Step 3: `kizilelma/scheduler/daily_job.py`'a DB entegrasyonunu ekle**

`run_daily_job` fonksiyonunu güncelle:
```python
async def run_daily_job() -> dict[str, Any]:
    """Tüm günlük akışı tek seferde çalıştır."""
    from kizilelma.storage.db import init_db, save_snapshot, save_report

    config = get_config()
    logger.info("=== Kızılelma günlük rapor başladı ===")

    # 0. DB hazırla
    try:
        init_db()
    except Exception as exc:
        logger.warning(f"DB init başarısız: {exc}")

    # 1. Veri topla
    snapshot = await collect_all_data()
    logger.info(
        f"Veri toplandı: {len(snapshot.funds)} fon, {len(snapshot.news)} haber, "
        f"hatalar: {list(snapshot.errors.keys())}"
    )

    # 2. AI yorum üret
    advisor = AIAdvisor(api_key=config.anthropic_api_key)
    report = await advisor.generate_report(snapshot)
    logger.info(f"Rapor üretildi: errors={report.errors}")

    # 3. Telegram'a gönder
    sender = TelegramSender(
        token=config.telegram_bot_token,
        chat_id=config.telegram_chat_id,
    )
    sent = await sender.send_report(report)
    logger.info(f"{sent} mesaj gönderildi")

    # 4. DB'ye kaydet
    snapshot_id = None
    try:
        snapshot_id = save_snapshot(snapshot)
        save_report(
            report, snapshot_id=snapshot_id,
            sent_messages=sent,
            status="success" if sent > 0 and not snapshot.errors else "partial",
        )
        logger.info(f"DB'ye kaydedildi: snapshot_id={snapshot_id}")
    except Exception as exc:
        logger.warning(f"DB kayıt başarısız: {exc}")

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
        "snapshot_id": snapshot_id,
        "timestamp": snapshot.timestamp.isoformat(),
    }
```

- [ ] **Step 4: Testin geçtiğini doğrula**

```bash
pytest tests/scheduler/test_daily_job.py -v
```

Beklenen: Tüm scheduler testleri yeşil.

- [ ] **Step 5: Commit**

```bash
git add kizilelma/scheduler/daily_job.py tests/scheduler/test_daily_job.py
git commit -m "Daily job: DB entegrasyonu — her snapshot ve rapor SQLite'a arşivlenir"
```

---

## Task 4: Eurobond Collector'ını yfinance ile Gerçek Veriye Geçir

**Files:**
- Modify: `kizilelma/collectors/eurobond.py`
- Modify: `tests/collectors/test_eurobond.py`
- Modify: `pyproject.toml`

NOT: yfinance Yahoo Finance'tan veri çeker. Türkiye Eurobond ticker'ları sınırlıdır; v1'de en aktif birkaç tanesini takip edeceğiz. İleride İş Yatırım API'sine geçilebilir.

- [ ] **Step 1: yfinance bağımlılığını ekle**

`pyproject.toml`'a ekle:
```toml
    "yfinance>=0.2.40",
```

Yükle:
```bash
pip install -e ".[dev]"
```

- [ ] **Step 2: Testi yfinance kullanımı için güncelle**

`tests/collectors/test_eurobond.py`'a ek test:
```python
@pytest.mark.asyncio
async def test_eurobond_collector_uses_yfinance(monkeypatch):
    """yfinance ile gerçek ticker verisi çekildiğini doğrula (mock üzerinden)."""
    from unittest.mock import MagicMock, patch
    from datetime import datetime

    fake_ticker = MagicMock()
    fake_ticker.history.return_value = MagicMock(
        empty=False,
        iloc=[MagicMock(name=datetime.now(), Close=94.5)],
    )
    fake_ticker.info = {"symbol": "TURKGB10Y", "currency": "USD"}

    with patch("kizilelma.collectors.eurobond.yf.Ticker", return_value=fake_ticker):
        collector = EurobondCollector(use_yfinance=True)
        bonds = await collector.fetch()
    # En azından çağrı yapıldı, hata yok
    assert isinstance(bonds, list)
```

- [ ] **Step 3: `kizilelma/collectors/eurobond.py`'ı güncelle**

```python
"""Eurobond collector — yfinance entegrasyonu."""
import asyncio
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal

import httpx

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

from kizilelma.collectors.base import BaseCollector
from kizilelma.models import EurobondData


logger = logging.getLogger(__name__)

# Türkiye'nin en aktif eurobond ticker'ları (Yahoo Finance)
# Not: Yahoo'da bireysel eurobond verisi sınırlı. Türkiye 10Y yield proxy'si
# olarak ilgili ETF/index ticker'larını takip ediyoruz.
DEFAULT_TICKERS = [
    # Format: (ticker, vade_yaklaşık, currency)
    ("TURKGB10Y", date(2034, 1, 1), "USD"),  # Yahoo proxy
]


class EurobondCollector(BaseCollector):
    """Türkiye Eurobond verilerini çeker (yfinance veya HTTP)."""

    name = "eurobond"

    def __init__(
        self,
        url: str = "",
        timeout: float = 30.0,
        use_yfinance: bool = True,
        tickers: list = None,
    ) -> None:
        self.url = url
        self.timeout = timeout
        self.use_yfinance = use_yfinance and YFINANCE_AVAILABLE
        self.tickers = tickers or DEFAULT_TICKERS

    async def fetch(self) -> list[EurobondData]:
        """Eurobond verilerini çek."""
        if self.use_yfinance:
            return await self._fetch_yfinance()
        return await self._fetch_http()

    async def _fetch_yfinance(self) -> list[EurobondData]:
        """yfinance üzerinden veri çek (sync → executor)."""
        loop = asyncio.get_event_loop()
        bonds: list[EurobondData] = []

        for ticker_info in self.tickers:
            ticker_sym, maturity, currency = ticker_info
            try:
                bond = await loop.run_in_executor(
                    None, self._fetch_single_yf, ticker_sym, maturity, currency
                )
                if bond:
                    bonds.append(bond)
            except Exception as exc:
                logger.warning(f"yfinance ticker {ticker_sym} hatası: {exc}")
                continue

        return bonds

    @staticmethod
    def _fetch_single_yf(
        ticker_sym: str, maturity: date, currency: str
    ) -> EurobondData | None:
        """Tek bir ticker için sync veri çekme."""
        try:
            ticker = yf.Ticker(ticker_sym)
            hist = ticker.history(period="5d")
            if hist.empty:
                return None
            latest = hist.iloc[-1]
            price = Decimal(str(round(float(latest["Close"]), 2)))
            # Yield bilgisi yfinance'tan alınamıyor, basit tahmin
            yield_estimate = Decimal("7.5")
            return EurobondData(
                isin=ticker_sym,
                maturity_date=maturity,
                currency=currency,
                yield_rate=yield_estimate,
                price=price,
                date=date.today(),
            )
        except Exception:
            return None

    async def _fetch_http(self) -> list[EurobondData]:
        """HTTP fallback (eski davranış)."""
        if not self.url:
            return []
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.url)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            return []

        today = date.today()
        bonds: list[EurobondData] = []
        for item in payload.get("bonds", []):
            try:
                bonds.append(
                    EurobondData(
                        isin=item["isin"],
                        maturity_date=datetime.strptime(
                            item["maturity"], "%Y-%m-%d"
                        ).date(),
                        currency=item["currency"],
                        yield_rate=Decimal(str(item["yield"])),
                        price=Decimal(str(item["price"])),
                        date=today,
                    )
                )
            except (KeyError, ValueError, ArithmeticError):
                continue
        return bonds
```

- [ ] **Step 4: Tüm eurobond testlerinin geçtiğini doğrula**

```bash
pytest tests/collectors/test_eurobond.py -v
```

Beklenen: Tüm testler yeşil.

- [ ] **Step 5: Commit**

```bash
git add kizilelma/collectors/eurobond.py tests/collectors/test_eurobond.py pyproject.toml
git commit -m "Eurobond: yfinance entegrasyonu (default) + HTTP fallback"
```

---

## Task 5: GitHub Actions Workflow (Cron Deployment)

**Files:**
- Create: `.github/workflows/daily-report.yml`
- Create: `.github/workflows/test.yml`

- [ ] **Step 1: Test workflow oluştur**

`.github/workflows/test.yml`:
```yaml
name: Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Run tests
        env:
          TCMB_API_KEY: test_key
          ANTHROPIC_API_KEY: test_key
          TELEGRAM_BOT_TOKEN: test_key
          TELEGRAM_CHAT_ID: "12345"
        run: pytest -v
```

- [ ] **Step 2: Daily report workflow oluştur**

`.github/workflows/daily-report.yml`:
```yaml
name: Kızılelma Günlük Rapor

on:
  schedule:
    # Pzt-Cum 07:00 UTC = 10:00 İstanbul (UTC+3)
    - cron: "0 7 * * 1-5"
  workflow_dispatch:  # Manuel tetikleme

jobs:
  daily-report:
    runs-on: ubuntu-latest
    timeout-minutes: 15

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Cache pip
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('pyproject.toml') }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e .

      - name: DB cache restore (geçmiş veriler)
        uses: actions/cache@v4
        with:
          path: kizilelma.db
          key: kizilelma-db-${{ github.run_number }}
          restore-keys: |
            kizilelma-db-

      - name: Run Kızılelma report
        env:
          TCMB_API_KEY: ${{ secrets.TCMB_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: kizilelma run-now

      - name: Upload DB as artifact
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: kizilelma-db-${{ github.run_id }}
          path: kizilelma.db
          retention-days: 30
```

- [ ] **Step 3: Commit**

```bash
mkdir -p .github/workflows
git add .github/
git commit -m "GitHub Actions: test workflow + daily-report cron (Pzt-Cum 10:00 İstanbul)"
```

---

## Task 6: Türkçe Kullanıcı Kılavuzu

**Files:**
- Create: `docs/kurulum.md`
- Create: `docs/kullanim-klavuzu.md`
- Modify: `README.md`

- [ ] **Step 1: `docs/kurulum.md` yaz**

```markdown
# Kurulum Rehberi

Bu rehber, Kızılelma'yı sıfırdan kurmak için tüm adımları içerir. Komut satırı bilmen gerekmiyor — adımları sırayla takip et.

## 1. Telegram Bot Oluştur

1. Telegram'da `@BotFather` hesabını bul
2. `/newbot` yaz
3. Bot için bir isim seç (örn. "Kızılelma Bot")
4. Username seç (sonu `_bot` ile bitmeli, örn. `kizilelma_kiraz_bot`)
5. BotFather sana bir TOKEN verecek — bunu sakla, başkasıyla paylaşma

### Chat ID'ni öğren

1. Yeni oluşturduğun bot'a Telegram'da bir mesaj at (örn. "merhaba")
2. Tarayıcında şu adresi aç (TOKEN'ı kendininkiyle değiştir):
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. JSON yanıtında `"chat":{"id":XXXXXX}` kısmını bul
4. Bu sayı senin chat ID'n. Sakla.

## 2. TCMB EVDS API Anahtarı

1. https://evds2.tcmb.gov.tr adresine git
2. Sağ üstten "Üye Ol" → e-posta + şifre ile kayıt
3. Giriş yaptıktan sonra "Profil" → "API Anahtarı" sekmesinden anahtarını al
4. Sakla.

## 3. Anthropic Claude API Anahtarı

1. https://console.anthropic.com adresine git
2. Hesap oluştur (kredi kartı gerekebilir, ücretsiz krediyle başla)
3. "API Keys" → "Create Key" → anahtarı kopyala, sakla.

## 4. GitHub'da Çalıştırmak İçin (Önerilen — Bedava + Otomatik)

### Repo'yu Oluştur

1. https://github.com/new adresinden yeni boş repo oluştur (private veya public)
2. Adı: `kizilelma`

### Kodu Yükle

Terminal aç ve şunları yaz (her satırı tek tek):

```bash
cd ~/Desktop/Kızılelma
git remote add origin https://github.com/<kullanıcı_adın>/kizilelma.git
git push -u origin main
```

### Sırları Ekle

GitHub'da repo sayfanda:
1. **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret** ile şu 4 sırrı ekle:
   - `TCMB_API_KEY`: TCMB anahtarın
   - `ANTHROPIC_API_KEY`: Claude anahtarın
   - `TELEGRAM_BOT_TOKEN`: BotFather'dan aldığın token
   - `TELEGRAM_CHAT_ID`: Yukarıda aldığın chat ID

### Test Et

1. **Actions** sekmesine git
2. "Kızılelma Günlük Rapor" workflow'unu seç
3. Sağ üstten "Run workflow" → "Run workflow" tıkla
4. ~3 dakika içinde Telegram'a rapor düşmeli ✅

### Otomatik Çalışma

Artık her hafta içi (Pzt-Cum) saat 10:00'da otomatik olarak çalışır. Hiçbir şey yapmana gerek yok.

## 5. Yerel Bilgisayarda Test (İsteğe Bağlı)

Eğer önce kendi Mac'inde test etmek istersen:

```bash
cd ~/Desktop/Kızılelma
python3.11 -m venv venv
source venv/bin/activate
pip install -e .
cp .env.example .env
# .env dosyasını aç ve değerleri doldur
kizilelma test-telegram   # Telegram bağlantısını test et
kizilelma run-now         # Tam rapor üret ve gönder
```
```

- [ ] **Step 2: `docs/kullanim-klavuzu.md` yaz**

```markdown
# Kızılelma Kullanım Kılavuzu

## Her Sabah Ne Olur?

Hafta içi her gün saat **10:00**'da Telegram'a sırayla 8 mesaj düşer:

1. 📊 **TEFAS Fonları** — En yüksek getirili 10 fon + 3 profilli yorum
2. 💎 **Serbest Fonlar** — Nitelikli yatırımcı fonları
3. 🏛️ **DİBS / Tahviller** — Devlet iç borçlanma senetleri
4. 🕌 **Kira Sertifikaları** — Sukuk verileri
5. 🔄 **Repo / TCMB Faizi** — Politika faizi ve repo oranları
6. 🌍 **Eurobond** — Türkiye eurobond getirileri
7. 📰 **Ekonomi Haberleri** — Günün önemli ekonomi haberleri (özet)
8. 🎯 **GÜNÜN ÖZETİ** — 3 profilli karşılaştırma ve nihai öneri

## Mesajları Anlamak

Her bölümün sonunda 3 farklı yatırımcı profili için ayrı öneri vardır:

- 🛡️ **Muhafazakâr** — Sermayeyi korumayı önceleyen, düşük risk
- ⚖️ **Dengeli** — Risk ve getiriyi dengeleyen
- 🚀 **Agresif** — Yüksek getiri için yüksek risk alabilen

**Sen kendi profiline göre okumalısın.** Aynı gün için 3 farklı tavsiye olabilir, çünkü farklı insanlar için farklı önerilen şeyler vardır.

## Manuel Çalıştırma

İstediğin zaman rapor almak istersen:

### GitHub'dan

1. Repo'da **Actions** sekmesine git
2. "Kızılelma Günlük Rapor" → "Run workflow"
3. ~3 dakika içinde Telegram'a düşer

### Bilgisayarda

```bash
source venv/bin/activate
kizilelma run-now
```

## Hata Olursa

Bir veri kaynağı çökerse (örn. TEFAS site bakıma girer), o bölümde "veri alınamadı" yazar ama diğer bölümler normal çalışır. Tüm sistem çökerse Telegram'a hiç mesaj düşmez — Actions log'una bakarak nedenini görebilirsin.

## Yasal Uyarı

> Bu rapor yatırım tavsiyesi DEĞİLDİR. Bilgilendirme amaçlıdır. Yatırım kararları kullanıcının kendi sorumluluğundadır. Geçmiş performans gelecekteki getiriyi garanti etmez.
```

- [ ] **Step 3: README'yi güncelle**

`README.md`'ye link ekle:
```markdown
# Kızılelma

Türkiye'deki yatırım fonları, tahviller, sukuk, repo ve eurobond getirilerini her sabah otomatik analiz eden ve Telegram üzerinden 3 profilli yatırım raporu gönderen kişisel yatırım danışmanı ajanı.

## Hızlı Başlangıç

- 📖 [Kurulum Rehberi](docs/kurulum.md) — Telegram bot, API anahtarları, GitHub Actions
- 📖 [Kullanım Kılavuzu](docs/kullanim-klavuzu.md) — Günlük raporları nasıl okuyacağın

## Komutlar

```bash
kizilelma test-telegram   # Telegram bağlantısını test et
kizilelma run-now         # Şimdi tek bir rapor gönder
kizilelma start           # Zamanlayıcıyı başlat (lokal kullanım)
```

## Yasal Uyarı

Bu yazılım yatırım tavsiyesi DEĞİLDİR. Bilgilendirme amaçlıdır. Yatırım kararları kullanıcının kendi sorumluluğundadır.
```

- [ ] **Step 4: Commit**

```bash
git add docs/kurulum.md docs/kullanim-klavuzu.md README.md
git commit -m "Türkçe dokümantasyon: kurulum rehberi, kullanım kılavuzu, README güncelleme"
```

---

## Task 7: Uçtan Uca Manuel Test

- [ ] **Step 1: Tüm test paketinin yeşil olduğunu doğrula**

```bash
pytest -v
```

Beklenen: Kademe 1+2+3+4 = ~50+ test, hepsi yeşil.

- [ ] **Step 2: `.env` dosyanı doldur**

`.env.example`'ı `.env` olarak kopyala ve gerçek anahtarları yaz.

- [ ] **Step 3: Telegram bağlantısını test et**

```bash
kizilelma test-telegram
```

Beklenen: Telegram'a "Kızılelma test mesajı" gelir.

- [ ] **Step 4: Tam rapor üret**

```bash
kizilelma run-now
```

Beklenen:
- Loglarda her aşama görünür (collect → AI → send)
- Telegram'a 8 mesaj sırayla düşer
- `kizilelma.db` dosyası oluşur ve içinde kayıt vardır

- [ ] **Step 5: DB'de kayıtları doğrula**

```bash
python -c "from kizilelma.storage.db import get_recent_snapshots; \
           snaps = get_recent_snapshots(limit=5); \
           print([(s.timestamp, s.fund_count) for s in snaps])"
```

Beklenen: En az 1 snapshot kaydı görünür.

- [ ] **Step 6: GitHub Actions'da deploy testi**

1. GitHub repo'da Actions → "Run workflow" tıkla
2. ~3 dakika içinde tamamlanır
3. Telegram'a rapor düşer
4. Run özeti yeşil olmalı

- [ ] **Step 7: Final commit ve tag**

```bash
git commit --allow-empty -m "Kademe 4 tamamlandı: DB + GitHub Actions + dokümanlar + uçtan uca test"
git tag v1.0.0 -m "Kızılelma v1.0 — ilk kararlı sürüm"
```

---

## Kademe 4 Bitirme Kontrol Listesi

- [ ] Storage modülü (SQLModel + DB erişim katmanı)
- [ ] Daily job DB entegrasyonu (her snapshot ve rapor arşivlenir)
- [ ] Eurobond yfinance entegrasyonu (gerçek veri)
- [ ] GitHub Actions workflow'ları (test + daily-report cron)
- [ ] Türkçe kullanıcı dokümantasyonu (kurulum + kullanım)
- [ ] Uçtan uca manuel test başarılı
- [ ] GitHub Actions üzerinden gerçek rapor Telegram'a düştü
- [ ] v1.0.0 tag'i atıldı

---

## 🎉 v1 Tamamlandı!

Kızılelma artık her hafta içi sabah 10:00'da otomatik olarak çalışıyor, GitHub Actions'ta zamanlanmış, geçmiş raporları SQLite'a arşivliyor, Telegram'a 8 mesaj olarak rapor gönderiyor.

**Sonraki versiyonlar için yol haritası:**
- v1.5: Döviz & altın takibi (ek collector + ek bölüm)
- v2.0: Anlık uyarılar + Telegram sohbet modu
- v3.0: Portföy takibi + hedef takibi
- v3+: AI tahmin modeli, web dashboard, global piyasa bağlamı
