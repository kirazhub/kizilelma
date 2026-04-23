# Kızılelma — Kademe 2: Analiz Motoru ve AI Yorumcu

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kademe 1'de toplanan ham veriyi alıp finansal metrikler (getiri, risk, Sharpe oranı, sıralama) hesaplayan analiz motoru ve hesaplanmış metrikleri okuyup Türkçe doğal dilde 3 profilli yorum üreten AI advisor modülünü inşa et.

**Architecture:** İki bağımsız modül. **Analyzers** sadece sayılarla çalışır (saf fonksiyonlar, AI veya HTTP yok). **AI advisor** Anthropic Claude API'sine bağlanır, hazır metrikleri okur ve her enstrüman + her profil için yorum üretir. AI çağrısı başarısız olursa metrikler yine de geçer.

**Tech Stack:** Python 3.11+, `numpy`/`statistics` (volatilite hesaplama), `anthropic` (Claude API), `pytest` + `respx` (mock).

---

## Dosya Yapısı

Bu kademede oluşturulacak/değiştirilecek dosyalar:

```
kizilelma/
├── analyzers/
│   ├── __init__.py
│   ├── returns.py          # Getiri hesaplamaları
│   ├── risk.py             # Volatilite, Sharpe oranı
│   └── ranker.py           # En iyi N listesi (her kategori için)
└── ai_advisor/
    ├── __init__.py
    ├── prompts.py          # Türkçe prompt şablonları
    └── advisor.py          # Claude API entegrasyonu
tests/
├── analyzers/
│   ├── __init__.py
│   ├── test_returns.py
│   ├── test_risk.py
│   └── test_ranker.py
└── ai_advisor/
    ├── __init__.py
    ├── test_prompts.py
    └── test_advisor.py
```

---

## Task 1: Returns Analyzer (Getiri Hesaplamaları)

**Files:**
- Create: `kizilelma/analyzers/__init__.py`
- Create: `kizilelma/analyzers/returns.py`
- Test: `tests/analyzers/__init__.py`
- Test: `tests/analyzers/test_returns.py`

- [ ] **Step 1: Failing test yaz**

`tests/analyzers/__init__.py`:
```python
```

`tests/analyzers/test_returns.py`:
```python
"""Returns analyzer testleri."""
from datetime import date
from decimal import Decimal

import pytest

from kizilelma.models import FundData
from kizilelma.analyzers.returns import (
    annualized_return,
    classify_by_return_band,
    inflation_adjusted_return,
)


def test_annualized_return_from_monthly():
    """Aylık getiriden yıllık eşdeğeri hesaplanır."""
    # %4 aylık → yıllıkta yaklaşık %60 (bileşik)
    annual = annualized_return(monthly_return_pct=Decimal("4"))
    assert Decimal("59") < annual < Decimal("61")


def test_inflation_adjusted_return_positive():
    """Enflasyon üstü reel getiri doğru hesaplanır."""
    # %50 nominal, %40 enflasyon → reel ≈ %7.14
    real = inflation_adjusted_return(
        nominal_return_pct=Decimal("50"),
        inflation_pct=Decimal("40"),
    )
    assert Decimal("7") < real < Decimal("8")


def test_inflation_adjusted_return_negative():
    """Enflasyon altı kaldıysa reel getiri negatif olur."""
    real = inflation_adjusted_return(
        nominal_return_pct=Decimal("30"),
        inflation_pct=Decimal("50"),
    )
    assert real < 0


def test_classify_by_return_band():
    """Yıllık getiriye göre bant sınıflandırması."""
    assert classify_by_return_band(Decimal("100")) == "çok_yüksek"
    assert classify_by_return_band(Decimal("60")) == "yüksek"
    assert classify_by_return_band(Decimal("40")) == "orta"
    assert classify_by_return_band(Decimal("15")) == "düşük"
    assert classify_by_return_band(Decimal("-5")) == "negatif"
```

- [ ] **Step 2: Testin başarısız olduğunu doğrula**

```bash
pytest tests/analyzers/test_returns.py -v
```

Beklenen: `ImportError`

- [ ] **Step 3: `kizilelma/analyzers/__init__.py` ve `returns.py` yaz**

`kizilelma/analyzers/__init__.py`:
```python
"""Finansal analiz modülleri."""
```

`kizilelma/analyzers/returns.py`:
```python
"""Getiri hesaplamaları.

Saf matematiksel fonksiyonlar — HTTP veya AI çağrısı yok, hızlı ve test edilebilir.
"""
from decimal import Decimal


def annualized_return(monthly_return_pct: Decimal) -> Decimal:
    """Aylık getiriden yıllık bileşik getiri hesapla.

    Formül: (1 + r/100)^12 - 1

    Args:
        monthly_return_pct: Aylık getiri yüzde olarak (örn. 4 = %4)

    Returns:
        Yıllık bileşik getiri yüzde olarak
    """
    monthly_factor = Decimal(1) + monthly_return_pct / Decimal(100)
    annual_factor = monthly_factor ** 12
    return (annual_factor - Decimal(1)) * Decimal(100)


def inflation_adjusted_return(
    nominal_return_pct: Decimal,
    inflation_pct: Decimal,
) -> Decimal:
    """Reel getiri hesapla (Fisher denklemi).

    Formül: ((1 + nominal) / (1 + enflasyon) - 1) * 100

    Args:
        nominal_return_pct: Nominal getiri %
        inflation_pct: Enflasyon %

    Returns:
        Reel (enflasyondan arındırılmış) getiri %
    """
    nominal_factor = Decimal(1) + nominal_return_pct / Decimal(100)
    inflation_factor = Decimal(1) + inflation_pct / Decimal(100)
    return (nominal_factor / inflation_factor - Decimal(1)) * Decimal(100)


def classify_by_return_band(annual_return_pct: Decimal) -> str:
    """Yıllık getiriyi bantlara ayır.

    Bantlar:
        - çok_yüksek: > 80%
        - yüksek:     50-80%
        - orta:       30-50%
        - düşük:      0-30%
        - negatif:    < 0%
    """
    if annual_return_pct < 0:
        return "negatif"
    if annual_return_pct < 30:
        return "düşük"
    if annual_return_pct < 50:
        return "orta"
    if annual_return_pct < 80:
        return "yüksek"
    return "çok_yüksek"
```

- [ ] **Step 4: Testlerin geçtiğini doğrula**

```bash
pytest tests/analyzers/test_returns.py -v
```

Beklenen: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add kizilelma/analyzers/__init__.py kizilelma/analyzers/returns.py tests/analyzers/
git commit -m "Returns analyzer: yıllık getiri, reel getiri, bant sınıflandırma"
```

---

## Task 2: Risk Analyzer (Volatilite + Sharpe)

**Files:**
- Create: `kizilelma/analyzers/risk.py`
- Test: `tests/analyzers/test_risk.py`

- [ ] **Step 1: Failing test yaz**

`tests/analyzers/test_risk.py`:
```python
"""Risk analyzer testleri."""
from decimal import Decimal

import pytest

from kizilelma.analyzers.risk import (
    estimate_risk_score,
    sharpe_ratio,
    risk_level_label,
)


def test_estimate_risk_score_from_returns():
    """Getiri büyüklüğüne göre risk skoru tahmin edilir.

    Yüksek getiri → yüksek risk varsayımı (basit heuristik).
    Daha sonra geçmiş veri biriktiğinde gerçek volatilite ile değiştirilecek.
    """
    score_high = estimate_risk_score(annual_return_pct=Decimal("150"))
    score_low = estimate_risk_score(annual_return_pct=Decimal("30"))
    assert score_high > score_low
    assert 0 <= score_low <= 100
    assert 0 <= score_high <= 100


def test_sharpe_ratio_positive_when_above_risk_free():
    """Risksiz orandan yüksek getiride Sharpe pozitif olur."""
    sharpe = sharpe_ratio(
        annual_return_pct=Decimal("60"),
        risk_free_rate_pct=Decimal("47.5"),
        volatility_pct=Decimal("10"),
    )
    assert sharpe > 0


def test_sharpe_ratio_negative_when_below_risk_free():
    """Risksiz orandan düşük getiride Sharpe negatif olur."""
    sharpe = sharpe_ratio(
        annual_return_pct=Decimal("30"),
        risk_free_rate_pct=Decimal("47.5"),
        volatility_pct=Decimal("10"),
    )
    assert sharpe < 0


def test_sharpe_zero_when_zero_volatility():
    """Volatilite sıfır ise Sharpe tanımsız → 0 dönülür."""
    sharpe = sharpe_ratio(
        annual_return_pct=Decimal("60"),
        risk_free_rate_pct=Decimal("47.5"),
        volatility_pct=Decimal("0"),
    )
    assert sharpe == 0


def test_risk_level_labels():
    """Risk skoruna göre etiket dönüşümü."""
    assert risk_level_label(10) == "çok düşük"
    assert risk_level_label(35) == "düşük"
    assert risk_level_label(55) == "orta"
    assert risk_level_label(75) == "yüksek"
    assert risk_level_label(95) == "çok yüksek"
```

- [ ] **Step 2: Testin başarısız olduğunu doğrula**

```bash
pytest tests/analyzers/test_risk.py -v
```

Beklenen: `ImportError`

- [ ] **Step 3: `kizilelma/analyzers/risk.py` yaz**

```python
"""Risk hesaplamaları: volatilite, Sharpe oranı, risk skoru.

NOT: v1'de geçmiş veri biriktirilmediğinden gerçek volatilite hesaplanamaz.
Bunun yerine getiri büyüklüğüne göre basit bir heuristic kullanıyoruz.
v3'te geçmiş veri biriktirildiğinde gerçek standart sapma hesaplanacak.
"""
from decimal import Decimal


def estimate_risk_score(annual_return_pct: Decimal) -> int:
    """Yıllık getiriden risk skoru tahmini (0-100).

    Heuristic: Yüksek getiri = yüksek risk (genel kural).
    İlerideki versiyonlarda gerçek volatilite ile değiştirilecek.

    Args:
        annual_return_pct: Yıllık getiri yüzdesi

    Returns:
        0 (en düşük risk) - 100 (en yüksek risk) arası tam sayı
    """
    abs_ret = abs(annual_return_pct)
    if abs_ret < Decimal("20"):
        return 10
    if abs_ret < Decimal("40"):
        return 25
    if abs_ret < Decimal("60"):
        return 45
    if abs_ret < Decimal("100"):
        return 70
    return 90


def sharpe_ratio(
    annual_return_pct: Decimal,
    risk_free_rate_pct: Decimal,
    volatility_pct: Decimal,
) -> Decimal:
    """Sharpe oranı: risk başına düşen ekstra getiri.

    Formül: (Getiri - Risksiz Oran) / Volatilite

    Args:
        annual_return_pct: Yatırımın yıllık getirisi
        risk_free_rate_pct: Risksiz oran (TCMB politika faizi vb.)
        volatility_pct: Yıllık volatilite (standart sapma)

    Returns:
        Sharpe oranı. Pozitif ise risksiz orandan iyi performans.
    """
    if volatility_pct == 0:
        return Decimal(0)
    return (annual_return_pct - risk_free_rate_pct) / volatility_pct


def risk_level_label(risk_score: int) -> str:
    """Risk skorunu Türkçe etikete çevir."""
    if risk_score < 20:
        return "çok düşük"
    if risk_score < 40:
        return "düşük"
    if risk_score < 60:
        return "orta"
    if risk_score < 80:
        return "yüksek"
    return "çok yüksek"
```

- [ ] **Step 4: Testlerin geçtiğini doğrula**

```bash
pytest tests/analyzers/test_risk.py -v
```

Beklenen: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add kizilelma/analyzers/risk.py tests/analyzers/test_risk.py
git commit -m "Risk analyzer: risk skoru tahmini, Sharpe oranı, risk etiketleri"
```

---

## Task 3: Ranker (En İyi N Listesi)

**Files:**
- Create: `kizilelma/analyzers/ranker.py`
- Test: `tests/analyzers/test_ranker.py`

- [ ] **Step 1: Failing test yaz**

`tests/analyzers/test_ranker.py`:
```python
"""Ranker testleri."""
from datetime import date
from decimal import Decimal

import pytest

from kizilelma.models import FundData
from kizilelma.analyzers.ranker import (
    top_funds_by_return,
    top_funds_by_category,
    filter_qualified,
)


def _make_fund(code: str, return_1m: Decimal, category: str = "Hisse",
               qualified: bool = False) -> FundData:
    return FundData(
        code=code,
        name=f"Fon {code}",
        category=category,
        price=Decimal("1.0"),
        date=date.today(),
        return_1m=return_1m,
        return_1y=return_1m * 12,
        is_qualified_investor=qualified,
    )


def test_top_funds_by_return_orders_by_metric():
    """Belirtilen metriğe göre azalan sıralama yapar."""
    funds = [
        _make_fund("A", Decimal("3")),
        _make_fund("B", Decimal("5")),
        _make_fund("C", Decimal("1")),
    ]
    top = top_funds_by_return(funds, metric="return_1m", limit=3)
    assert [f.code for f in top] == ["B", "A", "C"]


def test_top_funds_by_return_respects_limit():
    """Limit kadar fon döner."""
    funds = [_make_fund(f"F{i}", Decimal(str(i))) for i in range(10)]
    top = top_funds_by_return(funds, metric="return_1m", limit=3)
    assert len(top) == 3


def test_top_funds_by_category_groups_correctly():
    """Kategoriye göre gruplama yapar, her kategori için top N."""
    funds = [
        _make_fund("A1", Decimal("5"), category="Hisse"),
        _make_fund("A2", Decimal("3"), category="Hisse"),
        _make_fund("B1", Decimal("4"), category="Tahvil"),
        _make_fund("B2", Decimal("2"), category="Tahvil"),
    ]
    grouped = top_funds_by_category(funds, metric="return_1m", limit=1)
    assert "Hisse" in grouped
    assert "Tahvil" in grouped
    assert grouped["Hisse"][0].code == "A1"
    assert grouped["Tahvil"][0].code == "B1"


def test_filter_qualified_separates_serbest_funds():
    """Serbest fonlar (nitelikli yatırımcı) ayrı bir listede toplanır."""
    funds = [
        _make_fund("A", Decimal("5"), qualified=False),
        _make_fund("B", Decimal("10"), qualified=True),
    ]
    standart, serbest = filter_qualified(funds)
    assert len(standart) == 1
    assert len(serbest) == 1
    assert serbest[0].code == "B"


def test_top_funds_handles_none_metric_safely():
    """Metric None olan fonlar listede sona düşer (skip değil)."""
    funds = [
        _make_fund("A", Decimal("5")),
        FundData(
            code="X",
            name="No data",
            category="Hisse",
            price=Decimal("1"),
            date=date.today(),
            return_1m=None,
        ),
    ]
    top = top_funds_by_return(funds, metric="return_1m", limit=10)
    assert top[0].code == "A"
    # None'lar listede kalır ama sona düşer
```

- [ ] **Step 2: Testin başarısız olduğunu doğrula**

```bash
pytest tests/analyzers/test_ranker.py -v
```

Beklenen: `ImportError`

- [ ] **Step 3: `kizilelma/analyzers/ranker.py` yaz**

```python
"""Sıralama ve filtreleme yardımcıları."""
from collections import defaultdict
from decimal import Decimal
from typing import Literal

from kizilelma.models import FundData


ReturnMetric = Literal[
    "return_1d", "return_1w", "return_1m", "return_3m", "return_6m", "return_1y"
]


def top_funds_by_return(
    funds: list[FundData],
    metric: ReturnMetric = "return_1m",
    limit: int = 10,
) -> list[FundData]:
    """Belirtilen getiri metriğine göre en iyi N fonu döner.

    None değerli fonlar listenin sonuna düşer.
    """
    def sort_key(fund: FundData) -> tuple[int, Decimal]:
        value = getattr(fund, metric)
        if value is None:
            return (1, Decimal(0))  # None'lar sonda
        return (0, -value)  # değerli olanlar başta, büyükten küçüğe

    sorted_funds = sorted(funds, key=sort_key)
    return sorted_funds[:limit]


def top_funds_by_category(
    funds: list[FundData],
    metric: ReturnMetric = "return_1m",
    limit: int = 5,
) -> dict[str, list[FundData]]:
    """Her kategori için ayrı en iyi N listesi.

    Returns:
        {kategori_adı: [top fonlar]}
    """
    by_category: dict[str, list[FundData]] = defaultdict(list)
    for fund in funds:
        by_category[fund.category].append(fund)

    result: dict[str, list[FundData]] = {}
    for category, items in by_category.items():
        result[category] = top_funds_by_return(items, metric=metric, limit=limit)
    return result


def filter_qualified(
    funds: list[FundData],
) -> tuple[list[FundData], list[FundData]]:
    """Standart fonlar ve serbest fonları ayır.

    Returns:
        (standart_fonlar, serbest_fonlar) tuple'ı
    """
    standart: list[FundData] = []
    serbest: list[FundData] = []
    for fund in funds:
        if fund.is_qualified_investor:
            serbest.append(fund)
        else:
            standart.append(fund)
    return standart, serbest
```

- [ ] **Step 4: Testlerin geçtiğini doğrula**

```bash
pytest tests/analyzers/test_ranker.py -v
```

Beklenen: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add kizilelma/analyzers/ranker.py tests/analyzers/test_ranker.py
git commit -m "Ranker: top N fon listesi, kategori bazlı gruplama, serbest fon ayrımı"
```

---

## Task 4: AI Advisor — Prompt Şablonları

**Files:**
- Create: `kizilelma/ai_advisor/__init__.py`
- Create: `kizilelma/ai_advisor/prompts.py`
- Test: `tests/ai_advisor/__init__.py`
- Test: `tests/ai_advisor/test_prompts.py`

- [ ] **Step 1: Failing test yaz**

`tests/ai_advisor/__init__.py`:
```python
```

`tests/ai_advisor/test_prompts.py`:
```python
"""Prompt şablonu testleri."""
from datetime import date, datetime
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
            price=Decimal("1.234"), date=date.today(),
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
        timestamp=datetime.now(),
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
```

- [ ] **Step 2: Testin başarısız olduğunu doğrula**

```bash
pytest tests/ai_advisor/test_prompts.py -v
```

Beklenen: `ImportError`

- [ ] **Step 3: `kizilelma/ai_advisor/__init__.py` ve `prompts.py` yaz**

`kizilelma/ai_advisor/__init__.py`:
```python
"""AI yorum üretici modüller."""
```

`kizilelma/ai_advisor/prompts.py`:
```python
"""Türkçe AI prompt şablonları.

Tüm prompt'lar Claude Sonnet için tasarlandı. 3 profilli (muhafazakâr/dengeli/agresif)
yorum üretimi için yapılandırılmıştır.
"""
from typing import Any

from kizilelma.models import FundData, MarketSnapshot


SYSTEM_PROMPT = """Sen "Kızılelma" adında, Türkiye finansal piyasaları konusunda
uzman bir yatırım danışman ajanısın. Görevin her sabah 10:00'da kullanıcıya
güncel piyasa verilerini değerlendirip, üç farklı yatırımcı profili için
(muhafazakâr, dengeli, agresif) öneri üretmek.

Kuralların:
1. **Türkçe ve sade dil kullan.** Teknik terim kullanırsan parantez içinde açıkla.
2. **3 profilli yaklaşım:** Her bölümün sonunda muhafazakâr/dengeli/agresif için
   ayrı kısa öneri ver.
3. **Veriye sadık kal.** Veride olmayan rakamı uydurma. Belirsizlik varsa "veri yetersiz" de.
4. **Yasal uyarı:** Verdiğin bilgi yatırım tavsiyesi DEĞİLDİR, sadece bilgilendirme
   amaçlıdır. Bunu her bölümün sonunda hatırlatma şart değil ama unutturma.
5. **Madde işaretleri kullan**, düz paragraf yerine. Telegram mesajında okunmalı.
6. **Kısa ve öz yaz.** Her bölüm en fazla 8-10 satır olsun.
"""


def build_fund_section_prompt(top_funds: list[FundData]) -> str:
    """TEFAS fonları için yorum prompt'ı oluştur."""
    fund_lines = []
    for f in top_funds[:10]:
        ret_1m = f.return_1m if f.return_1m is not None else "?"
        ret_1y = f.return_1y if f.return_1y is not None else "?"
        fund_lines.append(
            f"- {f.code} | {f.name} | Kategori: {f.category} | "
            f"1A: %{ret_1m} | 1Y: %{ret_1y}"
        )
    funds_text = "\n".join(fund_lines) if fund_lines else "Veri alınamadı."

    return f"""Aşağıda bugünün en yüksek getirili TEFAS fonları listelenmiştir:

{funds_text}

Bu verilere bakarak şu yapıda bir Türkçe rapor yaz:

📊 *TEFAS FONLARI - GÜNÜN ÖNE ÇIKANLARI*

[2-3 satırda günün TEFAS özeti]

🛡️ *Muhafazakâr için:* [1-2 satır öneri]
⚖️ *Dengeli için:* [1-2 satır öneri]
🚀 *Agresif için:* [1-2 satır öneri]
"""


def build_serbest_fund_prompt(top_funds: list[FundData]) -> str:
    """Serbest fonlar için yorum prompt'ı."""
    fund_lines = []
    for f in top_funds[:5]:
        ret_1y = f.return_1y if f.return_1y is not None else "?"
        fund_lines.append(f"- {f.code} | {f.name} | 1Y: %{ret_1y}")
    funds_text = "\n".join(fund_lines) if fund_lines else "Veri alınamadı."

    return f"""Bugünün en yüksek getirili serbest fonları (sadece nitelikli yatırımcılara açık):

{funds_text}

Bu fonlar yüksek minimum yatırım gerektirir (genelde 1M TL+ portföy).
Kısa bir Türkçe değerlendirme yaz:

💎 *SERBEST FONLAR*

[3-4 satırda özet ve dikkat çekici fonlar]

⚠️ *Not:* Serbest fonlara yatırım için nitelikli yatırımcı statüsü gerekir.
"""


def build_repo_section_prompt(repo_rates: list) -> str:
    """Repo / TCMB faiz prompt'ı."""
    rate_lines = []
    for r in repo_rates[:5]:
        rate_lines.append(f"- {r.type} ({r.maturity}): %{r.rate} ({r.date})")
    rates_text = "\n".join(rate_lines) if rate_lines else "Veri alınamadı."

    return f"""TCMB ve repo oranları:

{rates_text}

Kısa bir Türkçe yorum yaz:

🔄 *REPO / TCMB FAİZİ*

[2-3 satırda mevcut durum ve trend yorumu]
[Risksiz getiri arayanlar için ne anlama geldiği]
"""


def build_news_section_prompt(news_items: list) -> str:
    """Haberler için özet prompt'ı."""
    if not news_items:
        return "Bugün ekonomi haberi alınamadı."

    news_lines = []
    for n in news_items[:8]:
        news_lines.append(f"- {n.published.strftime('%H:%M')} | {n.source}: {n.title}")
    news_text = "\n".join(news_lines)

    return f"""Bugünün ekonomi haberleri:

{news_text}

Bu haberlerden piyasayı etkileyebilecek olanları seç ve Türkçe özetle:

📰 *EKONOMİ HABERLERİ*

[En önemli 3-5 haberi madde madde özetle]
[Piyasa etkisi konusunda kısa bir değerlendirme]
"""


def build_summary_prompt(
    snapshot: MarketSnapshot,
    top_picks: dict[str, Any],
) -> str:
    """Tüm rapor için son özet/karşılaştırma prompt'ı."""
    return f"""Bugünün ({snapshot.timestamp.strftime('%d.%m.%Y')}) tüm piyasa
verileri toplandı:

- TEFAS fon sayısı: {len(snapshot.funds)}
- DİBS sayısı: {len(snapshot.bonds)}
- Sukuk sayısı: {len(snapshot.sukuks)}
- Repo oranı kayıtları: {len(snapshot.repo_rates)}
- Eurobond sayısı: {len(snapshot.eurobonds)}
- Haber sayısı: {len(snapshot.news)}

Tüm bu verileri değerlendirerek 3 profil için NİHAİ KARŞILAŞTIRMA ÖZETİ yaz:

🎯 *GÜNÜN ÖZETİ - 3 PROFİLLİ KARŞILAŞTIRMA*

🛡️ *MUHAFAZAKÂR PROFİL İÇİN*
[3-4 satır: bugün muhafazakâr yatırımcının ne yapması mantıklı, hangi enstrüman/fon öne çıkıyor]

⚖️ *DENGELİ PROFİL İÇİN*
[3-4 satır: dengeli yatırımcı için günün önerisi]

🚀 *AGRESİF PROFİL İÇİN*
[3-4 satır: agresif yatırımcı için yüksek getiri fırsatları]

⚠️ *Yasal Uyarı:* Bu rapor yatırım tavsiyesi değildir, bilgilendirme amaçlıdır.
Yatırım kararları kendi sorumluluğunuzdadır.
"""
```

- [ ] **Step 4: Testlerin geçtiğini doğrula**

```bash
pytest tests/ai_advisor/test_prompts.py -v
```

Beklenen: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add kizilelma/ai_advisor/__init__.py kizilelma/ai_advisor/prompts.py tests/ai_advisor/
git commit -m "AI advisor prompts: 3 profilli Türkçe prompt şablonları (fonlar, serbest, repo, haberler, özet)"
```

---

## Task 5: AI Advisor — Claude API Entegrasyonu

**Files:**
- Create: `kizilelma/ai_advisor/advisor.py`
- Test: `tests/ai_advisor/test_advisor.py`
- Modify: `pyproject.toml` (anthropic kütüphanesi ekle)

- [ ] **Step 1: Anthropic kütüphanesini ekle**

`pyproject.toml`'a `dependencies` listesine ekle:
```toml
    "anthropic>=0.25.0",
```

Yükle:
```bash
pip install -e ".[dev]"
```

- [ ] **Step 2: Failing test yaz**

`tests/ai_advisor/test_advisor.py`:
```python
"""AI Advisor testleri."""
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kizilelma.models import FundData, MarketSnapshot
from kizilelma.ai_advisor.advisor import AIAdvisor, AdvisorReport


@pytest.fixture
def sample_snapshot():
    return MarketSnapshot(
        timestamp=datetime(2026, 4, 23, 10, 0),
        funds=[
            FundData(
                code="AFA", name="Test", category="Para Piyasası",
                price=Decimal("1.0"), date=date.today(),
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
    # Bölümler boş veya hata mesajı içerir
```

- [ ] **Step 3: Testin başarısız olduğunu doğrula**

```bash
pytest tests/ai_advisor/test_advisor.py -v
```

Beklenen: `ImportError`

- [ ] **Step 4: `kizilelma/ai_advisor/advisor.py` yaz**

```python
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
        # En yüksek getiriliden 5 tane
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
```

- [ ] **Step 5: Testlerin geçtiğini doğrula**

```bash
pytest tests/ai_advisor/test_advisor.py -v
```

Beklenen: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add kizilelma/ai_advisor/advisor.py tests/ai_advisor/test_advisor.py pyproject.toml
git commit -m "AI Advisor: Claude API entegrasyonu, 8 bölümlü rapor üretimi (paralel + hata toleranslı)"
```

---

## Task 6: Tüm Kademe 2 Testlerini Çalıştır

- [ ] **Step 1: Tüm testleri çalıştır**

```bash
pytest -v
```

Beklenen: Kademe 1 + Kademe 2 testlerinin hepsi geçer (~30+ test).

- [ ] **Step 2: Final commit**

```bash
git commit --allow-empty -m "Kademe 2 tamamlandı: analiz motoru + AI advisor çalışır durumda"
```

---

## Kademe 2 Bitirme Kontrol Listesi

- [ ] Returns analyzer (yıllık getiri, reel getiri, bant)
- [ ] Risk analyzer (risk skoru, Sharpe, etiketler)
- [ ] Ranker (top N, kategori bazlı, serbest ayrımı)
- [ ] AI prompt şablonları (5 ayrı bölüm)
- [ ] AI advisor (Claude API entegrasyonu, paralel çağrı, hata toleransı)
- [ ] AdvisorReport veri sınıfı (8 bölümlük yapı)
- [ ] Tüm testler yeşil
- [ ] **Kademe 3'e geçmeye hazır:** Telegram bot ve zamanlayıcı
