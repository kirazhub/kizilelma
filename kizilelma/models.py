"""Kızılelma veri modelleri.

Tüm collector'lar bu modelleri kullanarak standart formatta veri döner.
"""
import datetime as dt
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class FundData(BaseModel):
    """Tek bir yatırım fonunun günlük verisi."""

    code: str = Field(..., description="Fon kodu (örn. AFA, TGE)")
    name: str = Field(..., description="Fonun tam adı")
    category: str = Field(..., description="Fon kategorisi")
    price: Decimal = Field(..., gt=0, description="Birim pay fiyatı (TL)")
    date: dt.date = Field(..., description="Fiyatın geçerli olduğu tarih")
    return_1d: Optional[Decimal] = Field(None, description="Günlük getiri (%)")
    return_1w: Optional[Decimal] = Field(None, description="Haftalık getiri (%)")
    return_1m: Optional[Decimal] = Field(None, description="Aylık getiri (%)")
    return_3m: Optional[Decimal] = Field(None, description="3 aylık getiri (%)")
    return_6m: Optional[Decimal] = Field(None, description="6 aylık getiri (%)")
    return_1y: Optional[Decimal] = Field(None, description="1 yıllık getiri (%)")
    is_qualified_investor: bool = Field(
        False, description="Nitelikli yatırımcı (serbest) fonu mu?"
    )
    asset_tags: list[str] = Field(
        default_factory=list,
        description=(
            "Fonun sektör/varlık/tema etiketleri. Fon adı ve kategorisinden "
            "türetilir (örn. ['Hisse', 'Teknoloji', 'BIST30'])."
        ),
    )


class BondData(BaseModel):
    """DİBS / devlet tahvili verisi."""

    isin: str = Field(..., description="Tahvil ISIN kodu")
    maturity_date: dt.date = Field(..., description="Vade tarihi")
    coupon_rate: Optional[Decimal] = Field(None, description="Kupon oranı (%)")
    yield_rate: Decimal = Field(..., description="Getiri oranı (%)")
    price: Decimal = Field(..., gt=0, description="Fiyat")
    date: dt.date = Field(..., description="Verinin tarihi")


class SukukData(BaseModel):
    """Kira sertifikası (sukuk) verisi."""

    isin: str = Field(..., description="Sukuk ISIN kodu")
    issuer: str = Field(..., description="İhraççı (Hazine veya banka)")
    maturity_date: dt.date = Field(..., description="Vade tarihi")
    yield_rate: Decimal = Field(..., description="Getiri oranı (%)")
    price: Decimal = Field(..., gt=0, description="Fiyat")
    date: dt.date = Field(..., description="Verinin tarihi")


class RepoRate(BaseModel):
    """Repo / ters repo oranı."""

    type: str = Field(..., description="Tür: 'repo' veya 'ters_repo'")
    maturity: str = Field(..., description="Vade: 'overnight', '1w' vb.")
    rate: Decimal = Field(..., description="Oran (%)")
    date: dt.date = Field(..., description="Verinin tarihi")


class EurobondData(BaseModel):
    """Türkiye Eurobond verisi."""

    isin: str = Field(..., description="Eurobond ISIN")
    maturity_date: dt.date = Field(..., description="Vade tarihi")
    currency: str = Field(..., description="Para birimi (USD/EUR)")
    yield_rate: Decimal = Field(..., description="Getiri (%)")
    price: Decimal = Field(..., gt=0, description="Fiyat")
    date: dt.date = Field(..., description="Verinin tarihi")


class NewsItem(BaseModel):
    """Tek bir haber öğesi."""

    title: str = Field(..., min_length=1, description="Haber başlığı")
    url: str = Field(..., description="Haberin URL'si")
    source: str = Field(..., description="Kaynak (örn. 'AA Ekonomi')")
    published: dt.datetime = Field(..., description="Yayınlanma zamanı")
    summary: Optional[str] = Field(None, description="Kısa özet")


class MacroData(BaseModel):
    """Makro ekonomik veri (kur, endeks, emtia).

    Tek bir makro göstergenin günlük değeri. AI'ın 'piyasa nasıl?' sorularına
    cevap verirken bağlam olarak kullandığı temel veri.
    """

    symbol: str = Field(..., description="Sembol (örn. USDTRY, GOLD_GR, BIST100)")
    name: str = Field(..., description="Görüntü adı (Türkçe)")
    value: Decimal = Field(..., description="Güncel değer")
    currency: str = Field("TRY", description="Para birimi (TRY/USD)")
    change_pct: Optional[Decimal] = Field(None, description="Günlük değişim %")
    category: str = Field(..., description="Tür: 'currency', 'commodity', 'index'")
    date: dt.date = Field(..., description="Tarih")


class MarketSnapshot(BaseModel):
    """Belirli bir andaki tüm piyasa verisinin anlık görüntüsü.

    Tüm collector'lar çalıştırıldıktan sonra üretilen toplam veri.
    Analiz motoru ve AI advisor bu sınıfı girdi olarak kullanır.
    """

    timestamp: dt.datetime = Field(..., description="Snapshot'ın alındığı an")
    funds: list[FundData] = Field(default_factory=list)
    bonds: list[BondData] = Field(default_factory=list)
    sukuks: list[SukukData] = Field(default_factory=list)
    repo_rates: list[RepoRate] = Field(default_factory=list)
    eurobonds: list[EurobondData] = Field(default_factory=list)
    news: list[NewsItem] = Field(default_factory=list)
    macro_data: list[MacroData] = Field(
        default_factory=list,
        description="Döviz kurları, altın, BIST, emtia gibi makro veriler",
    )
    errors: dict[str, str] = Field(
        default_factory=dict,
        description="Veri çekilemeyen kaynaklar ve hata mesajları",
    )
