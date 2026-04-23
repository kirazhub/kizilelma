# Kızılelma — Kademe 1: Temel Kurulum ve Veri Toplayıcılar

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Proje iskeletini kur ve tüm veri kaynaklarından (TEFAS, TCMB, BIST, Eurobond, RSS haberleri) standart formatta veri çekebilen bağımsız modüller yaz.

**Architecture:** Her veri kaynağı için ayrı bir collector modülü. Hepsi `fetch()` fonksiyonu sağlar ve aynı standart `MarketData` veri tipini döner. Asenkron HTTP çağrıları (`httpx`) ile paralel çalışabilir. Her collector tek başına test edilebilir.

**Tech Stack:** Python 3.11+, `httpx` (async HTTP), `beautifulsoup4` (HTML parse), `feedparser` (RSS), `pydantic` (veri modeli), `pytest` (test), `python-dotenv` (env yönetimi).

---

## Dosya Yapısı

Bu kademede oluşturulacak dosyalar:

```
kizilelma/
├── .gitignore                          # Git'e koymayacaklarımız
├── .env.example                        # Örnek API anahtar dosyası
├── pyproject.toml                      # Proje tanımı + bağımlılıklar
├── README.md                           # Kısa proje açıklaması
├── kizilelma/
│   ├── __init__.py
│   ├── models.py                       # MarketData, FundData, vb. tipler
│   ├── config.py                       # Ayarlar (env okuma)
│   └── collectors/
│       ├── __init__.py
│       ├── base.py                     # Ortak Collector arayüzü
│       ├── tefas.py                    # TEFAS fonları
│       ├── tcmb.py                     # TCMB EVDS API
│       ├── bist.py                     # DİBS, sukuk
│       ├── eurobond.py                 # Eurobond getirileri
│       └── news.py                     # RSS haberleri
└── tests/
    ├── __init__.py
    ├── fixtures/                       # Mock API yanıtları
    │   ├── tefas_response.json
    │   ├── tcmb_response.xml
    │   └── news_feed.xml
    └── collectors/
        ├── __init__.py
        ├── test_tefas.py
        ├── test_tcmb.py
        ├── test_bist.py
        ├── test_eurobond.py
        └── test_news.py
```

---

## Task 1: Proje İskeleti ve Bağımlılıklar

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `kizilelma/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: `.gitignore` dosyasını oluştur**

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.venv/
venv/

# Env / sırlar
.env
*.db
*.sqlite

# IDE
.vscode/
.idea/
.DS_Store

# Build
dist/
build/
```

- [ ] **Step 2: `.env.example` dosyasını oluştur**

```
# TCMB EVDS API anahtarı (ücretsiz, https://evds2.tcmb.gov.tr adresinden alınır)
TCMB_API_KEY=your_tcmb_key_here

# Anthropic Claude API anahtarı
ANTHROPIC_API_KEY=your_anthropic_key_here

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Çalışma ortamı
ENVIRONMENT=development
```

- [ ] **Step 3: `pyproject.toml` dosyasını oluştur**

```toml
[project]
name = "kizilelma"
version = "0.1.0"
description = "Türkiye finansal piyasa enstrümanlarını izleyen kişisel yatırım danışmanı ajanı"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27.0",
    "beautifulsoup4>=4.12.0",
    "lxml>=5.0.0",
    "feedparser>=6.0.0",
    "pydantic>=2.6.0",
    "python-dotenv>=1.0.0",
    "pytz>=2024.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-mock>=3.12.0",
    "respx>=0.20.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 4: `README.md` dosyasını oluştur**

```markdown
# Kızılelma

Türkiye'deki yatırım fonları, tahviller, sukuk, repo ve eurobond getirilerini her sabah otomatik analiz eden ve Telegram üzerinden 3 profilli (muhafazakâr / dengeli / agresif) yatırım raporu gönderen kişisel yatırım danışmanı ajanı.

## Kurulum

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # ve değerleri doldur
```

## Test

```bash
pytest
```

## Yasal Uyarı

Bu yazılım yatırım tavsiyesi DEĞİLDİR. Bilgilendirme amaçlıdır. Yatırım kararları kullanıcının kendi sorumluluğundadır.
```

- [ ] **Step 5: Boş paket dosyalarını oluştur**

`kizilelma/__init__.py`:
```python
"""Kızılelma — Türkiye finansal piyasa danışman ajanı."""
__version__ = "0.1.0"
```

`tests/__init__.py`:
```python
```

- [ ] **Step 6: Sanal ortam kur ve bağımlılıkları yükle**

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

Beklenen: Hata vermeden tüm paketler kurulur.

- [ ] **Step 7: pytest'in çalıştığını doğrula**

```bash
pytest --version
```

Beklenen: `pytest 8.x.x` çıktısı.

- [ ] **Step 8: Commit**

```bash
git add .
git commit -m "Proje iskeleti: pyproject, .gitignore, README ve sanal ortam kuruldu"
```

---

## Task 2: Veri Modelleri (Pydantic)

**Files:**
- Create: `kizilelma/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Failing test yaz**

`tests/test_models.py`:
```python
"""Veri modellerinin test edilmesi."""
from datetime import date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from kizilelma.models import (
    FundData,
    BondData,
    SukukData,
    RepoRate,
    EurobondData,
    NewsItem,
    MarketSnapshot,
)


def test_fund_data_creates_with_valid_fields():
    """Geçerli alanlarla fon verisi oluşur."""
    fund = FundData(
        code="AFA",
        name="Ak Portföy Para Piyasası Fonu",
        category="Para Piyasası",
        price=Decimal("1.234567"),
        date=date(2026, 4, 23),
        return_1d=Decimal("0.15"),
        return_1m=Decimal("4.20"),
        return_1y=Decimal("48.50"),
    )
    assert fund.code == "AFA"
    assert fund.return_1y == Decimal("48.50")


def test_fund_data_rejects_invalid_price():
    """Negatif fiyat reddedilir."""
    with pytest.raises(ValidationError):
        FundData(
            code="AFA",
            name="Test",
            category="Test",
            price=Decimal("-1"),
            date=date.today(),
        )


def test_news_item_requires_title_and_url():
    """Haber başlık ve URL zorunlu."""
    news = NewsItem(
        title="TCMB faiz kararını açıkladı",
        url="https://example.com/haber",
        source="AA Ekonomi",
        published=datetime(2026, 4, 23, 9, 0),
    )
    assert news.title.startswith("TCMB")


def test_market_snapshot_aggregates_all_data():
    """MarketSnapshot tüm veri tiplerini bir araya getirir."""
    snapshot = MarketSnapshot(
        timestamp=datetime(2026, 4, 23, 10, 0),
        funds=[],
        bonds=[],
        sukuks=[],
        repo_rates=[],
        eurobonds=[],
        news=[],
    )
    assert snapshot.timestamp.hour == 10
```

- [ ] **Step 2: Testin başarısız olduğunu doğrula**

```bash
pytest tests/test_models.py -v
```

Beklenen: `ImportError: cannot import name 'FundData' from 'kizilelma.models'`

- [ ] **Step 3: `kizilelma/models.py` dosyasını yaz**

```python
"""Kızılelma veri modelleri.

Tüm collector'lar bu modelleri kullanarak standart formatta veri döner.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


class FundData(BaseModel):
    """Tek bir yatırım fonunun günlük verisi."""

    code: str = Field(..., description="Fon kodu (örn. AFA, TGE)")
    name: str = Field(..., description="Fonun tam adı")
    category: str = Field(..., description="Fon kategorisi")
    price: Decimal = Field(..., gt=0, description="Birim pay fiyatı (TL)")
    date: date = Field(..., description="Fiyatın geçerli olduğu tarih")
    return_1d: Optional[Decimal] = Field(None, description="Günlük getiri (%)")
    return_1w: Optional[Decimal] = Field(None, description="Haftalık getiri (%)")
    return_1m: Optional[Decimal] = Field(None, description="Aylık getiri (%)")
    return_3m: Optional[Decimal] = Field(None, description="3 aylık getiri (%)")
    return_6m: Optional[Decimal] = Field(None, description="6 aylık getiri (%)")
    return_1y: Optional[Decimal] = Field(None, description="1 yıllık getiri (%)")
    is_qualified_investor: bool = Field(
        False, description="Nitelikli yatırımcı (serbest) fonu mu?"
    )


class BondData(BaseModel):
    """DİBS / devlet tahvili verisi."""

    isin: str = Field(..., description="Tahvil ISIN kodu")
    maturity_date: date = Field(..., description="Vade tarihi")
    coupon_rate: Optional[Decimal] = Field(None, description="Kupon oranı (%)")
    yield_rate: Decimal = Field(..., description="Getiri oranı (%)")
    price: Decimal = Field(..., gt=0, description="Fiyat")
    date: date = Field(..., description="Verinin tarihi")


class SukukData(BaseModel):
    """Kira sertifikası (sukuk) verisi."""

    isin: str = Field(..., description="Sukuk ISIN kodu")
    issuer: str = Field(..., description="İhraççı (Hazine veya banka)")
    maturity_date: date = Field(..., description="Vade tarihi")
    yield_rate: Decimal = Field(..., description="Getiri oranı (%)")
    price: Decimal = Field(..., gt=0, description="Fiyat")
    date: date = Field(..., description="Verinin tarihi")


class RepoRate(BaseModel):
    """Repo / ters repo oranı."""

    type: str = Field(..., description="Tür: 'repo' veya 'ters_repo'")
    maturity: str = Field(..., description="Vade: 'overnight', '1w' vb.")
    rate: Decimal = Field(..., description="Oran (%)")
    date: date = Field(..., description="Verinin tarihi")


class EurobondData(BaseModel):
    """Türkiye Eurobond verisi."""

    isin: str = Field(..., description="Eurobond ISIN")
    maturity_date: date = Field(..., description="Vade tarihi")
    currency: str = Field(..., description="Para birimi (USD/EUR)")
    yield_rate: Decimal = Field(..., description="Getiri (%)")
    price: Decimal = Field(..., gt=0, description="Fiyat")
    date: date = Field(..., description="Verinin tarihi")


class NewsItem(BaseModel):
    """Tek bir haber öğesi."""

    title: str = Field(..., min_length=1, description="Haber başlığı")
    url: str = Field(..., description="Haberin URL'si")
    source: str = Field(..., description="Kaynak (örn. 'AA Ekonomi')")
    published: datetime = Field(..., description="Yayınlanma zamanı")
    summary: Optional[str] = Field(None, description="Kısa özet")


class MarketSnapshot(BaseModel):
    """Belirli bir andaki tüm piyasa verisinin anlık görüntüsü.

    Tüm collector'lar çalıştırıldıktan sonra üretilen toplam veri.
    Analiz motoru ve AI advisor bu sınıfı girdi olarak kullanır.
    """

    timestamp: datetime = Field(..., description="Snapshot'ın alındığı an")
    funds: list[FundData] = Field(default_factory=list)
    bonds: list[BondData] = Field(default_factory=list)
    sukuks: list[SukukData] = Field(default_factory=list)
    repo_rates: list[RepoRate] = Field(default_factory=list)
    eurobonds: list[EurobondData] = Field(default_factory=list)
    news: list[NewsItem] = Field(default_factory=list)
    errors: dict[str, str] = Field(
        default_factory=dict,
        description="Veri çekilemeyen kaynaklar ve hata mesajları",
    )
```

- [ ] **Step 4: Testlerin geçtiğini doğrula**

```bash
pytest tests/test_models.py -v
```

Beklenen: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add kizilelma/models.py tests/test_models.py
git commit -m "Veri modelleri: FundData, BondData, SukukData, RepoRate, EurobondData, NewsItem, MarketSnapshot"
```

---

## Task 3: Config Modülü

**Files:**
- Create: `kizilelma/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Failing test yaz**

`tests/test_config.py`:
```python
"""Config modülü testleri."""
import os
import pytest
from kizilelma.config import Config, get_config


def test_config_reads_from_environment(monkeypatch):
    """Config env değişkenlerinden okur."""
    monkeypatch.setenv("TCMB_API_KEY", "test_tcmb")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test_claude")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_bot")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

    config = Config()
    assert config.tcmb_api_key == "test_tcmb"
    assert config.anthropic_api_key == "test_claude"
    assert config.telegram_bot_token == "test_bot"
    assert config.telegram_chat_id == "12345"


def test_config_environment_defaults_to_development(monkeypatch):
    """ENVIRONMENT değeri yoksa development."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("TCMB_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "x")

    config = Config()
    assert config.environment == "development"
```

- [ ] **Step 2: Testin başarısız olduğunu doğrula**

```bash
pytest tests/test_config.py -v
```

Beklenen: `ImportError`

- [ ] **Step 3: `kizilelma/config.py` dosyasını yaz**

```python
"""Uygulama ayarları — env değişkenlerinden okunur."""
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Tüm yapılandırma değerlerini tutan sınıf."""

    def __init__(self) -> None:
        self.tcmb_api_key: str = self._require("TCMB_API_KEY")
        self.anthropic_api_key: str = self._require("ANTHROPIC_API_KEY")
        self.telegram_bot_token: str = self._require("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id: str = self._require("TELEGRAM_CHAT_ID")
        self.environment: str = os.getenv("ENVIRONMENT", "development")

    @staticmethod
    def _require(key: str) -> str:
        """Zorunlu env değişkenini oku, yoksa hata ver."""
        value = os.getenv(key)
        if not value:
            raise RuntimeError(
                f"Eksik ortam değişkeni: {key}. .env dosyasını kontrol et."
            )
        return value


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Singleton config nesnesi döner."""
    return Config()
```

- [ ] **Step 4: Testlerin geçtiğini doğrula**

```bash
pytest tests/test_config.py -v
```

Beklenen: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add kizilelma/config.py tests/test_config.py
git commit -m "Config modülü: env değişkenleri okuma ve doğrulama"
```

---

## Task 4: Base Collector Arayüzü

**Files:**
- Create: `kizilelma/collectors/__init__.py`
- Create: `kizilelma/collectors/base.py`
- Test: `tests/collectors/__init__.py`
- Test: `tests/collectors/test_base.py`

- [ ] **Step 1: Test dosyasını yaz**

`tests/collectors/__init__.py`:
```python
```

`tests/collectors/test_base.py`:
```python
"""Base Collector testleri."""
import pytest
from kizilelma.collectors.base import BaseCollector, CollectorError


class DummyCollector(BaseCollector):
    """Test için sahte collector."""
    name = "dummy"

    async def fetch(self):
        return {"hello": "world"}


@pytest.mark.asyncio
async def test_base_collector_has_name():
    collector = DummyCollector()
    assert collector.name == "dummy"


@pytest.mark.asyncio
async def test_base_collector_fetch_returns_data():
    collector = DummyCollector()
    result = await collector.fetch()
    assert result == {"hello": "world"}


def test_collector_error_can_be_raised():
    with pytest.raises(CollectorError):
        raise CollectorError("test", "API down")
```

- [ ] **Step 2: Testin başarısız olduğunu doğrula**

```bash
pytest tests/collectors/test_base.py -v
```

Beklenen: `ImportError`

- [ ] **Step 3: `kizilelma/collectors/__init__.py` ve `base.py` yaz**

`kizilelma/collectors/__init__.py`:
```python
"""Veri toplayıcı modüller."""
```

`kizilelma/collectors/base.py`:
```python
"""Tüm veri toplayıcılarının ortak arayüzü."""
from abc import ABC, abstractmethod
from typing import Any


class CollectorError(Exception):
    """Veri toplama sırasında oluşan hatalar."""

    def __init__(self, source: str, message: str) -> None:
        self.source = source
        self.message = message
        super().__init__(f"[{source}] {message}")


class BaseCollector(ABC):
    """Tüm collector'ların türetildiği temel sınıf.

    Her collector bir `name` özelliği ve bir `fetch()` async metodu sağlar.
    fetch() metodu standart bir veri tipi döner (collector türüne göre değişir).
    """

    name: str = "base"

    @abstractmethod
    async def fetch(self) -> Any:
        """Veri kaynağından veriyi çek ve döndür."""
        raise NotImplementedError
```

- [ ] **Step 4: Testlerin geçtiğini doğrula**

```bash
pytest tests/collectors/test_base.py -v
```

Beklenen: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add kizilelma/collectors/ tests/collectors/
git commit -m "Base collector arayüzü: BaseCollector ve CollectorError"
```

---

## Task 5: TEFAS Collector (Fonlar + Serbest Fonlar)

**Files:**
- Create: `kizilelma/collectors/tefas.py`
- Create: `tests/fixtures/tefas_response.json`
- Test: `tests/collectors/test_tefas.py`

TEFAS API'si: `https://www.tefas.gov.tr/api/DB/BindHistoryInfo` POST endpoint'i kullanılır. Aynı zamanda `BindHistoryAllocation` da var. v1'de günlük fiyat ve getirileri çekeceğiz.

- [ ] **Step 1: Mock fixture oluştur**

`tests/fixtures/tefas_response.json`:
```json
{
  "data": [
    {
      "FONKODU": "AFA",
      "FONUNVAN": "Ak Portföy Para Piyasası Fonu",
      "FIYAT": 1.234567,
      "TARIH": "23.04.2026",
      "GETIRI1G": 0.15,
      "GETIRI1H": 1.05,
      "GETIRI1A": 4.20,
      "GETIRI3A": 12.50,
      "GETIRI6A": 25.80,
      "GETIRI1Y": 48.50,
      "FONTUR": "Para Piyasası Fonu"
    },
    {
      "FONKODU": "TGE",
      "FONUNVAN": "Test Serbest Fonu (Nitelikli Yatırımcıya)",
      "FIYAT": 5.678901,
      "TARIH": "23.04.2026",
      "GETIRI1G": 0.85,
      "GETIRI1H": 4.20,
      "GETIRI1A": 18.50,
      "GETIRI3A": 55.20,
      "GETIRI6A": 110.40,
      "GETIRI1Y": 280.50,
      "FONTUR": "Serbest Fon"
    }
  ]
}
```

- [ ] **Step 2: Failing test yaz**

`tests/collectors/test_tefas.py`:
```python
"""TEFAS collector testleri."""
import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from kizilelma.collectors.tefas import TefasCollector
from kizilelma.models import FundData


FIXTURE = Path(__file__).parent.parent / "fixtures" / "tefas_response.json"


@pytest.fixture
def tefas_response():
    return json.loads(FIXTURE.read_text())


@respx.mock
@pytest.mark.asyncio
async def test_tefas_fetch_returns_fund_list(tefas_response):
    """TEFAS API'sinden fon listesi çekilebilir."""
    respx.post("https://www.tefas.gov.tr/api/DB/BindHistoryInfo").mock(
        return_value=httpx.Response(200, json=tefas_response)
    )

    collector = TefasCollector()
    funds = await collector.fetch()

    assert len(funds) == 2
    assert all(isinstance(f, FundData) for f in funds)
    assert funds[0].code == "AFA"
    assert funds[0].price == Decimal("1.234567")
    assert funds[0].return_1y == Decimal("48.50")
    assert funds[0].is_qualified_investor is False


@respx.mock
@pytest.mark.asyncio
async def test_tefas_marks_serbest_fund_as_qualified(tefas_response):
    """Serbest fonlar nitelikli yatırımcı bayrağıyla işaretlenir."""
    respx.post("https://www.tefas.gov.tr/api/DB/BindHistoryInfo").mock(
        return_value=httpx.Response(200, json=tefas_response)
    )

    collector = TefasCollector()
    funds = await collector.fetch()

    serbest = next(f for f in funds if f.code == "TGE")
    assert serbest.is_qualified_investor is True
    assert "Serbest" in serbest.category


@respx.mock
@pytest.mark.asyncio
async def test_tefas_raises_on_http_error():
    """HTTP hatası CollectorError olarak fırlatılır."""
    from kizilelma.collectors.base import CollectorError

    respx.post("https://www.tefas.gov.tr/api/DB/BindHistoryInfo").mock(
        return_value=httpx.Response(500)
    )

    collector = TefasCollector()
    with pytest.raises(CollectorError):
        await collector.fetch()
```

- [ ] **Step 3: Testin başarısız olduğunu doğrula**

```bash
pytest tests/collectors/test_tefas.py -v
```

Beklenen: `ImportError`

- [ ] **Step 4: `kizilelma/collectors/tefas.py` yaz**

```python
"""TEFAS (Türkiye Elektronik Fon Alım Satım Platformu) collector.

TEFAS'ın resmi API'si: https://www.tefas.gov.tr
Hem standart hem de serbest fonların verilerini çeker.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

import httpx

from kizilelma.collectors.base import BaseCollector, CollectorError
from kizilelma.models import FundData


TEFAS_URL = "https://www.tefas.gov.tr/api/DB/BindHistoryInfo"


class TefasCollector(BaseCollector):
    """TEFAS fonlarının günlük verilerini çeker."""

    name = "tefas"

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    async def fetch(self) -> list[FundData]:
        """Bugüne ait tüm fonların verisini döndürür."""
        today = date.today()
        # Hafta sonu / tatil ise geriye doğru en yakın iş gününü ara
        target = self._previous_weekday(today)

        payload = {
            "fontip": "YAT",  # Yatırım fonu
            "sfontur": "",
            "fonkod": "",
            "fongrup": "",
            "bastarih": target.strftime("%d.%m.%Y"),
            "bittarih": target.strftime("%d.%m.%Y"),
            "fonturkod": "",
            "fonunvantip": "",
            "strperiod": "1,1,1,1,1,1,1",
            "islemdurum": "1",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(TEFAS_URL, data=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise CollectorError(self.name, f"HTTP hatası: {exc}") from exc
        except ValueError as exc:
            raise CollectorError(self.name, f"JSON parse hatası: {exc}") from exc

        return [self._parse_fund(item) for item in data.get("data", [])]

    @staticmethod
    def _previous_weekday(d: date) -> date:
        """En yakın hafta içi günü döndürür."""
        while d.weekday() >= 5:  # 5=Cumartesi, 6=Pazar
            d -= timedelta(days=1)
        return d

    @staticmethod
    def _parse_fund(item: dict[str, Any]) -> FundData:
        """TEFAS API yanıtındaki tek bir fon kaydını FundData'ya dönüştür."""
        category = item.get("FONTUR", "Bilinmiyor")
        is_qualified = "Serbest" in category or "Nitelikli" in (
            item.get("FONUNVAN") or ""
        )
        return FundData(
            code=item["FONKODU"],
            name=item["FONUNVAN"],
            category=category,
            price=Decimal(str(item["FIYAT"])),
            date=datetime.strptime(item["TARIH"], "%d.%m.%Y").date(),
            return_1d=_safe_decimal(item.get("GETIRI1G")),
            return_1w=_safe_decimal(item.get("GETIRI1H")),
            return_1m=_safe_decimal(item.get("GETIRI1A")),
            return_3m=_safe_decimal(item.get("GETIRI3A")),
            return_6m=_safe_decimal(item.get("GETIRI6A")),
            return_1y=_safe_decimal(item.get("GETIRI1Y")),
            is_qualified_investor=is_qualified,
        )


def _safe_decimal(value: Any) -> Optional[Decimal]:
    """None veya boş değerse None, aksi halde Decimal döner."""
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (ValueError, ArithmeticError):
        return None
```

- [ ] **Step 5: Testlerin geçtiğini doğrula**

```bash
pytest tests/collectors/test_tefas.py -v
```

Beklenen: `3 passed`

- [ ] **Step 6: Commit**

```bash
git add kizilelma/collectors/tefas.py tests/collectors/test_tefas.py tests/fixtures/tefas_response.json
git commit -m "TEFAS collector: fon ve serbest fon verilerini çeker"
```

---

## Task 6: TCMB Collector (EVDS API)

**Files:**
- Create: `kizilelma/collectors/tcmb.py`
- Create: `tests/fixtures/tcmb_response.json`
- Test: `tests/collectors/test_tcmb.py`

TCMB EVDS API'si: `https://evds2.tcmb.gov.tr/service/evds/series=...&type=json` formatında JSON döner. v1'de gecelik repo, haftalık repo ve TCMB politika faizi serilerini çekeceğiz.

- [ ] **Step 1: Mock fixture oluştur**

`tests/fixtures/tcmb_response.json`:
```json
{
  "totalCount": 1,
  "items": [
    {
      "Tarih": "23-04-2026",
      "TP_KTF12": "47.5",
      "TP_APIFON4": "47.0",
      "TP_APIFON6": "48.0"
    }
  ]
}
```

- [ ] **Step 2: Failing test yaz**

`tests/collectors/test_tcmb.py`:
```python
"""TCMB EVDS collector testleri."""
import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from kizilelma.collectors.tcmb import TcmbCollector
from kizilelma.models import RepoRate


FIXTURE = Path(__file__).parent.parent / "fixtures" / "tcmb_response.json"


@pytest.fixture
def tcmb_response():
    return json.loads(FIXTURE.read_text())


@respx.mock
@pytest.mark.asyncio
async def test_tcmb_fetch_returns_repo_rates(tcmb_response, monkeypatch):
    """TCMB EVDS API'sinden repo oranları çekilir."""
    monkeypatch.setenv("TCMB_API_KEY", "test_key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "x")

    respx.get(url__regex=r"https://evds2\.tcmb\.gov\.tr/service/evds.*").mock(
        return_value=httpx.Response(200, json=tcmb_response)
    )

    collector = TcmbCollector(api_key="test_key")
    rates = await collector.fetch()

    assert len(rates) >= 1
    assert all(isinstance(r, RepoRate) for r in rates)
    rate_values = [r.rate for r in rates]
    assert Decimal("47.5") in rate_values


@respx.mock
@pytest.mark.asyncio
async def test_tcmb_raises_on_error(monkeypatch):
    monkeypatch.setenv("TCMB_API_KEY", "test_key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "x")

    from kizilelma.collectors.base import CollectorError
    respx.get(url__regex=r"https://evds2\.tcmb\.gov\.tr/.*").mock(
        return_value=httpx.Response(500)
    )

    collector = TcmbCollector(api_key="test_key")
    with pytest.raises(CollectorError):
        await collector.fetch()
```

- [ ] **Step 3: Testin başarısız olduğunu doğrula**

```bash
pytest tests/collectors/test_tcmb.py -v
```

Beklenen: `ImportError`

- [ ] **Step 4: `kizilelma/collectors/tcmb.py` yaz**

```python
"""TCMB EVDS API collector.

EVDS = Elektronik Veri Dağıtım Sistemi
Resmi API: https://evds2.tcmb.gov.tr
TCMB politika faizi, repo ve ters repo oranlarını çeker.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

import httpx

from kizilelma.collectors.base import BaseCollector, CollectorError
from kizilelma.models import RepoRate


EVDS_BASE_URL = "https://evds2.tcmb.gov.tr/service/evds"

# İzlenecek seriler
# TP_KTF12   = TCMB Politika Faizi (1 hafta repo ihale faizi)
# TP_APIFON4 = Gecelik borçlanma faizi (ters repo)
# TP_APIFON6 = Gecelik borç verme faizi (repo)
SERIES = {
    "TP_KTF12": ("repo", "1w"),
    "TP_APIFON4": ("ters_repo", "overnight"),
    "TP_APIFON6": ("repo", "overnight"),
}


class TcmbCollector(BaseCollector):
    """TCMB EVDS verilerini çeker."""

    name = "tcmb"

    def __init__(self, api_key: str, timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.timeout = timeout

    async def fetch(self) -> list[RepoRate]:
        """Son 7 günün TCMB repo verilerini çekip listele."""
        end = date.today()
        start = end - timedelta(days=7)

        series_str = "-".join(SERIES.keys())
        url = (
            f"{EVDS_BASE_URL}/series={series_str}"
            f"&startDate={start.strftime('%d-%m-%Y')}"
            f"&endDate={end.strftime('%d-%m-%Y')}"
            f"&type=json&aggregationTypes=last"
        )
        headers = {"key": self.api_key}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise CollectorError(self.name, f"HTTP hatası: {exc}") from exc
        except ValueError as exc:
            raise CollectorError(self.name, f"JSON parse hatası: {exc}") from exc

        return self._parse_rates(data)

    @staticmethod
    def _parse_rates(data: dict) -> list[RepoRate]:
        """EVDS yanıtını RepoRate listesine dönüştür."""
        rates: list[RepoRate] = []
        for item in data.get("items", []):
            tarih_str = item.get("Tarih", "")
            try:
                rate_date = datetime.strptime(tarih_str, "%d-%m-%Y").date()
            except ValueError:
                continue

            for series_key, (rate_type, maturity) in SERIES.items():
                value = item.get(series_key)
                if value is None or value == "":
                    continue
                try:
                    rate_value = Decimal(str(value))
                except (ValueError, ArithmeticError):
                    continue
                rates.append(
                    RepoRate(
                        type=rate_type,
                        maturity=maturity,
                        rate=rate_value,
                        date=rate_date,
                    )
                )
        return rates
```

- [ ] **Step 5: Testlerin geçtiğini doğrula**

```bash
pytest tests/collectors/test_tcmb.py -v
```

Beklenen: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add kizilelma/collectors/tcmb.py tests/collectors/test_tcmb.py tests/fixtures/tcmb_response.json
git commit -m "TCMB collector: EVDS API'den repo ve politika faizi verilerini çeker"
```

---

## Task 7: BIST Collector (DİBS + Sukuk)

**Files:**
- Create: `kizilelma/collectors/bist.py`
- Create: `tests/fixtures/bist_dibs.html`
- Test: `tests/collectors/test_bist.py`

BIST'in resmi API'si halka açık değil. v1'de Borsa İstanbul'un public sayfalarından scraping yapılır. Yedek olarak `isyatirim.com.tr`'nin tahvil/sukuk sayfaları kullanılabilir.

- [ ] **Step 1: Mock HTML fixture oluştur**

`tests/fixtures/bist_dibs.html`:
```html
<!DOCTYPE html>
<html>
<body>
<table id="bondTable">
  <thead>
    <tr>
      <th>ISIN</th><th>Vade</th><th>Kupon</th><th>Getiri</th><th>Fiyat</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>TRT191028T18</td>
      <td>19.10.2028</td>
      <td>25.00</td>
      <td>42.50</td>
      <td>92.45</td>
    </tr>
    <tr>
      <td>TRT151226T17</td>
      <td>15.12.2026</td>
      <td>22.50</td>
      <td>45.20</td>
      <td>97.80</td>
    </tr>
  </tbody>
</table>
</body>
</html>
```

- [ ] **Step 2: Failing test yaz**

`tests/collectors/test_bist.py`:
```python
"""BIST collector testleri."""
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from kizilelma.collectors.bist import BistCollector
from kizilelma.models import BondData, SukukData


FIXTURE_DIBS = Path(__file__).parent.parent / "fixtures" / "bist_dibs.html"


@respx.mock
@pytest.mark.asyncio
async def test_bist_fetches_dibs_and_sukuk():
    """BIST'ten DİBS ve sukuk verileri çekilir."""
    html = FIXTURE_DIBS.read_text()
    respx.get(url__regex=r".*bond.*").mock(
        return_value=httpx.Response(200, text=html)
    )
    respx.get(url__regex=r".*sukuk.*").mock(
        return_value=httpx.Response(200, text=html)
    )

    collector = BistCollector()
    bonds, sukuks = await collector.fetch()

    assert len(bonds) >= 2
    assert all(isinstance(b, BondData) for b in bonds)
    assert bonds[0].isin == "TRT191028T18"
    assert bonds[0].yield_rate == Decimal("42.50")


@respx.mock
@pytest.mark.asyncio
async def test_bist_returns_empty_on_failure_not_raises():
    """BIST scraping başarısız olursa boş liste döner (CollectorError fırlatmaz).

    Çünkü BIST scraping kırılgan; tek bir kaynağın çökmesi tüm raporu
    durdurmamalı. Hata loglanır, başka kaynaklara geçilir.
    """
    respx.get(url__regex=r".*").mock(
        return_value=httpx.Response(500)
    )

    collector = BistCollector()
    bonds, sukuks = await collector.fetch()

    assert bonds == []
    assert sukuks == []
```

- [ ] **Step 3: Testin başarısız olduğunu doğrula**

```bash
pytest tests/collectors/test_bist.py -v
```

Beklenen: `ImportError`

- [ ] **Step 4: `kizilelma/collectors/bist.py` yaz**

```python
"""BIST (Borsa İstanbul) collector.

DİBS (Devlet İç Borçlanma Senetleri) ve kira sertifikası (sukuk) verilerini
public web sayfalarından scraping ile çeker.

NOT: Scraping kırılgandır; sayfa yapısı değişirse bu modülün güncellenmesi
gerekir. Bu yüzden hata durumunda boş liste döner, exception fırlatmaz.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from kizilelma.collectors.base import BaseCollector
from kizilelma.models import BondData, SukukData


BOND_URL = "https://www.borsaistanbul.com/tr/sayfa/3037/bond-data"
SUKUK_URL = "https://www.borsaistanbul.com/tr/sayfa/3038/sukuk-data"


class BistCollector(BaseCollector):
    """BIST tahvil ve sukuk verilerini çeker."""

    name = "bist"

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    async def fetch(self) -> tuple[list[BondData], list[SukukData]]:
        """DİBS ve sukuk verilerini paralel çek."""
        bonds = await self._fetch_bonds()
        sukuks = await self._fetch_sukuks()
        return bonds, sukuks

    async def _fetch_bonds(self) -> list[BondData]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(BOND_URL)
                response.raise_for_status()
                return self._parse_bonds(response.text)
        except (httpx.HTTPError, ValueError):
            return []  # Scraping başarısız olursa boş liste

    async def _fetch_sukuks(self) -> list[SukukData]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(SUKUK_URL)
                response.raise_for_status()
                return self._parse_sukuks(response.text)
        except (httpx.HTTPError, ValueError):
            return []

    @staticmethod
    def _parse_bonds(html: str) -> list[BondData]:
        """HTML tablosundan tahvil verilerini ayrıştır."""
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table", {"id": "bondTable"}) or soup.find("table")
        if table is None:
            return []

        bonds: list[BondData] = []
        today = datetime.now().date()
        for row in table.find_all("tr")[1:]:  # başlığı atla
            cells = [c.get_text(strip=True) for c in row.find_all("td")]
            if len(cells) < 5:
                continue
            try:
                bonds.append(
                    BondData(
                        isin=cells[0],
                        maturity_date=datetime.strptime(
                            cells[1], "%d.%m.%Y"
                        ).date(),
                        coupon_rate=Decimal(cells[2]),
                        yield_rate=Decimal(cells[3]),
                        price=Decimal(cells[4]),
                        date=today,
                    )
                )
            except (ValueError, ArithmeticError):
                continue
        return bonds

    @staticmethod
    def _parse_sukuks(html: str) -> list[SukukData]:
        """HTML tablosundan sukuk verilerini ayrıştır."""
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table", {"id": "sukukTable"}) or soup.find("table")
        if table is None:
            return []

        sukuks: list[SukukData] = []
        today = datetime.now().date()
        for row in table.find_all("tr")[1:]:
            cells = [c.get_text(strip=True) for c in row.find_all("td")]
            if len(cells) < 5:
                continue
            try:
                sukuks.append(
                    SukukData(
                        isin=cells[0],
                        issuer="Hazine",  # v1: BIST sayfasından alınamıyor, varsayılan
                        maturity_date=datetime.strptime(
                            cells[1], "%d.%m.%Y"
                        ).date(),
                        yield_rate=Decimal(cells[3]),
                        price=Decimal(cells[4]),
                        date=today,
                    )
                )
            except (ValueError, ArithmeticError):
                continue
        return sukuks
```

- [ ] **Step 5: Testlerin geçtiğini doğrula**

```bash
pytest tests/collectors/test_bist.py -v
```

Beklenen: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add kizilelma/collectors/bist.py tests/collectors/test_bist.py tests/fixtures/bist_dibs.html
git commit -m "BIST collector: DİBS ve sukuk verilerini scraping ile çeker (hata toleranslı)"
```

---

## Task 8: Eurobond Collector

**Files:**
- Create: `kizilelma/collectors/eurobond.py`
- Create: `tests/fixtures/eurobond_response.json`
- Test: `tests/collectors/test_eurobond.py`

Eurobond verileri için Investing.com scraping veya `yfinance` (Yahoo Finance) kullanılır. v1'de basit bir mock üzerinden çalışıyoruz; gerçek entegrasyon için `İş Yatırım`'ın eurobond sayfası en güvenilir kaynak. Bu task'ta mock üzerinden çalışan iskelet kuruyoruz, gerçek entegrasyon Kademe 4'te (deploy öncesi) sağlanacak.

- [ ] **Step 1: Mock fixture oluştur**

`tests/fixtures/eurobond_response.json`:
```json
{
  "bonds": [
    {
      "isin": "US900123CB40",
      "maturity": "2034-03-25",
      "currency": "USD",
      "yield": "7.85",
      "price": "94.20"
    },
    {
      "isin": "XS2655241317",
      "maturity": "2030-09-15",
      "currency": "EUR",
      "yield": "6.20",
      "price": "97.80"
    }
  ]
}
```

- [ ] **Step 2: Failing test yaz**

`tests/collectors/test_eurobond.py`:
```python
"""Eurobond collector testleri."""
import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from kizilelma.collectors.eurobond import EurobondCollector
from kizilelma.models import EurobondData


FIXTURE = Path(__file__).parent.parent / "fixtures" / "eurobond_response.json"


@respx.mock
@pytest.mark.asyncio
async def test_eurobond_fetches_data():
    """Eurobond verisi çekilebilir."""
    data = json.loads(FIXTURE.read_text())
    respx.get(url__regex=r".*eurobond.*").mock(
        return_value=httpx.Response(200, json=data)
    )

    collector = EurobondCollector()
    bonds = await collector.fetch()

    assert len(bonds) == 2
    assert all(isinstance(b, EurobondData) for b in bonds)
    assert bonds[0].currency == "USD"
    assert bonds[0].yield_rate == Decimal("7.85")


@respx.mock
@pytest.mark.asyncio
async def test_eurobond_returns_empty_on_failure():
    """Hata durumunda boş liste döner."""
    respx.get(url__regex=r".*").mock(
        return_value=httpx.Response(500)
    )
    collector = EurobondCollector()
    bonds = await collector.fetch()
    assert bonds == []
```

- [ ] **Step 3: Testin başarısız olduğunu doğrula**

```bash
pytest tests/collectors/test_eurobond.py -v
```

Beklenen: `ImportError`

- [ ] **Step 4: `kizilelma/collectors/eurobond.py` yaz**

```python
"""Eurobond collector.

v1 IMPLEMENTATION NOTU:
Türkiye Eurobond verisi için resmi/ücretsiz API yok. Olası kaynaklar:
- İş Yatırım (https://www.isyatirim.com.tr/.../eurobond)
- Investing.com (scraping, kırılgan)
- Yahoo Finance (yfinance kütüphanesi)

Bu modül şu an basit bir HTTP GET ile JSON döndüren bir kaynaktan beslenecek
şekilde yazıldı. Kademe 4'te gerçek entegrasyon yapılacak.
Hata toleranslı: scraping başarısız olursa boş liste döner.
"""
from datetime import datetime
from decimal import Decimal

import httpx

from kizilelma.collectors.base import BaseCollector
from kizilelma.models import EurobondData


# Geçici endpoint — gerçek entegrasyon Kademe 4'te
EUROBOND_URL = "https://api.example.com/eurobond"


class EurobondCollector(BaseCollector):
    """Türkiye Eurobond verilerini çeker."""

    name = "eurobond"

    def __init__(self, url: str = EUROBOND_URL, timeout: float = 30.0) -> None:
        self.url = url
        self.timeout = timeout

    async def fetch(self) -> list[EurobondData]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.url)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            return []

        today = datetime.now().date()
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

- [ ] **Step 5: Testlerin geçtiğini doğrula**

```bash
pytest tests/collectors/test_eurobond.py -v
```

Beklenen: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add kizilelma/collectors/eurobond.py tests/collectors/test_eurobond.py tests/fixtures/eurobond_response.json
git commit -m "Eurobond collector: iskelet implementasyon (gerçek entegrasyon Kademe 4'te)"
```

---

## Task 9: News Collector (RSS Haberler)

**Files:**
- Create: `kizilelma/collectors/news.py`
- Create: `tests/fixtures/news_feed.xml`
- Test: `tests/collectors/test_news.py`

- [ ] **Step 1: Mock RSS fixture oluştur**

`tests/fixtures/news_feed.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>AA Ekonomi</title>
  <link>https://www.aa.com.tr</link>
  <description>Ekonomi Haberleri</description>
  <item>
    <title>TCMB faiz kararını açıkladı: %47.5</title>
    <link>https://www.aa.com.tr/tr/ekonomi/tcmb-faiz</link>
    <pubDate>Thu, 23 Apr 2026 09:00:00 +0300</pubDate>
    <description>Türkiye Cumhuriyet Merkez Bankası politika faizini değiştirmedi.</description>
  </item>
  <item>
    <title>Borsa İstanbul rekor seviyede kapandı</title>
    <link>https://www.aa.com.tr/tr/ekonomi/borsa-rekor</link>
    <pubDate>Thu, 23 Apr 2026 08:30:00 +0300</pubDate>
    <description>BIST 100 endeksi yüzde 1.5 yükselişle günü tamamladı.</description>
  </item>
</channel>
</rss>
```

- [ ] **Step 2: Failing test yaz**

`tests/collectors/test_news.py`:
```python
"""News collector testleri."""
from pathlib import Path

import httpx
import pytest
import respx

from kizilelma.collectors.news import NewsCollector
from kizilelma.models import NewsItem


FIXTURE = Path(__file__).parent.parent / "fixtures" / "news_feed.xml"


@respx.mock
@pytest.mark.asyncio
async def test_news_fetches_from_rss():
    """RSS feed'inden haberler çekilir."""
    rss_content = FIXTURE.read_text()
    respx.get(url__regex=r".*aa\.com\.tr.*").mock(
        return_value=httpx.Response(200, text=rss_content)
    )

    collector = NewsCollector(feeds=["https://www.aa.com.tr/rss/ekonomi"])
    news = await collector.fetch()

    assert len(news) >= 2
    assert all(isinstance(n, NewsItem) for n in news)
    assert any("TCMB" in n.title for n in news)


@respx.mock
@pytest.mark.asyncio
async def test_news_handles_failed_feed_gracefully():
    """Bir feed başarısız olursa diğerleri çalışır."""
    respx.get(url__regex=r".*broken.*").mock(
        return_value=httpx.Response(500)
    )
    respx.get(url__regex=r".*working.*").mock(
        return_value=httpx.Response(200, text=FIXTURE.read_text())
    )

    collector = NewsCollector(
        feeds=["https://broken.example.com/rss", "https://working.example.com/rss"]
    )
    news = await collector.fetch()

    # Çalışan feed'den en az 2 haber gelmeli
    assert len(news) >= 2
```

- [ ] **Step 3: Testin başarısız olduğunu doğrula**

```bash
pytest tests/collectors/test_news.py -v
```

Beklenen: `ImportError`

- [ ] **Step 4: `kizilelma/collectors/news.py` yaz**

```python
"""Ekonomi haberleri RSS collector.

Birden fazla RSS feed'inden haberleri çeker, birleştirir ve sıralar.
Bir feed başarısız olursa diğerleri çalışmaya devam eder (hata toleranslı).
"""
import asyncio
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser
import httpx

from kizilelma.collectors.base import BaseCollector
from kizilelma.models import NewsItem


# v1 varsayılan RSS feed listesi
DEFAULT_FEEDS = [
    "https://www.aa.com.tr/tr/rss/default?cat=ekonomi",
    "https://www.bloomberght.com/rss",
    "https://www.sozcu.com.tr/feed",
]


class NewsCollector(BaseCollector):
    """Birden fazla ekonomi RSS feed'inden haber çeker."""

    name = "news"

    def __init__(
        self,
        feeds: Optional[list[str]] = None,
        timeout: float = 15.0,
        max_per_feed: int = 10,
    ) -> None:
        self.feeds = feeds or DEFAULT_FEEDS
        self.timeout = timeout
        self.max_per_feed = max_per_feed

    async def fetch(self) -> list[NewsItem]:
        """Tüm feed'leri paralel çek, sonuçları birleştir."""
        tasks = [self._fetch_one(feed) for feed in self.feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_news: list[NewsItem] = []
        for result in results:
            if isinstance(result, Exception):
                continue  # Hata varsa o feed'i atla
            all_news.extend(result)

        # En yeni haberler önce gelsin
        all_news.sort(key=lambda n: n.published, reverse=True)
        return all_news

    async def _fetch_one(self, feed_url: str) -> list[NewsItem]:
        """Tek bir RSS feed'inden haberleri çek."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(feed_url)
                response.raise_for_status()
                content = response.text
        except httpx.HTTPError:
            return []

        parsed = feedparser.parse(content)
        news: list[NewsItem] = []
        feed_title = parsed.feed.get("title", feed_url)

        for entry in parsed.entries[: self.max_per_feed]:
            published = self._parse_date(entry)
            if published is None:
                continue
            try:
                news.append(
                    NewsItem(
                        title=entry.get("title", "Başlıksız"),
                        url=entry.get("link", ""),
                        source=feed_title,
                        published=published,
                        summary=entry.get("summary"),
                    )
                )
            except (ValueError, TypeError):
                continue
        return news

    @staticmethod
    def _parse_date(entry: dict) -> Optional[datetime]:
        """RSS entry'sinden tarih parse et."""
        for field in ("published", "updated", "pubDate"):
            value = entry.get(field)
            if not value:
                continue
            try:
                dt = parsedate_to_datetime(value)
                # tzinfo'yu kaldırarak naive datetime'a çevir (Pydantic uyumu)
                return dt.replace(tzinfo=None)
            except (TypeError, ValueError):
                continue
        return None
```

- [ ] **Step 5: Testlerin geçtiğini doğrula**

```bash
pytest tests/collectors/test_news.py -v
```

Beklenen: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add kizilelma/collectors/news.py tests/collectors/test_news.py tests/fixtures/news_feed.xml
git commit -m "News collector: çoklu RSS feed'den ekonomi haberleri çeker (paralel + hata toleranslı)"
```

---

## Task 10: Tüm Testleri Çalıştır ve Kademe 1 Bitiş Doğrulaması

- [ ] **Step 1: Tüm test paketini çalıştır**

```bash
pytest -v
```

Beklenen: Tüm testler geçer (yaklaşık 15+ test).

- [ ] **Step 2: Coverage kontrol (opsiyonel ama önerilen)**

```bash
pip install pytest-cov
pytest --cov=kizilelma --cov-report=term-missing
```

Beklenen: Collector'lar için %80+ coverage.

- [ ] **Step 3: Manuel duman testi (opsiyonel — gerçek API'lere bağlı)**

`scripts/smoke_test.py` dosyası oluştur:

```python
"""Manuel duman testi: gerçek API'leri çağır ve sonuçları yazdır.

KULLANIM:
    python scripts/smoke_test.py
"""
import asyncio
from kizilelma.collectors.tefas import TefasCollector
from kizilelma.collectors.news import NewsCollector


async def main():
    print("=== TEFAS testi ===")
    tefas = TefasCollector()
    funds = await tefas.fetch()
    print(f"  {len(funds)} fon çekildi")
    if funds:
        print(f"  Örnek: {funds[0].code} - {funds[0].name} - {funds[0].price}")

    print("\n=== Haberler testi ===")
    news = NewsCollector()
    items = await news.fetch()
    print(f"  {len(items)} haber çekildi")
    if items:
        print(f"  Örnek: {items[0].title}")


if __name__ == "__main__":
    asyncio.run(main())
```

Çalıştır:
```bash
mkdir -p scripts
# (yukarıdaki dosyayı yaz)
python scripts/smoke_test.py
```

- [ ] **Step 4: Final commit**

```bash
git add scripts/smoke_test.py
git commit -m "Kademe 1 tamamlandı: tüm collector'lar çalışır + smoke test scripti"
```

---

## Kademe 1 Bitirme Kontrol Listesi

- [ ] Tüm 9 task tamamlandı
- [ ] `pytest -v` ile tüm testler geçer
- [ ] Her collector tek başına `fetch()` çağrısıyla veri döndürür
- [ ] Hatalar collector'a göre uygun şekilde yönetilir (CollectorError veya boş liste)
- [ ] Tüm değişiklikler git'e commit edildi
- [ ] **Kademe 2'ye geçmeye hazır:** Analiz motoru ve AI yorumcu
