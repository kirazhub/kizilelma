"""TEFAS collector testleri.

Not: ``TefasCollector`` artık TEFAS resmi API'sini KULLANMIYOR. GitHub Actions
runner IP'leri TEFAS WAF tarafından "Request Rejected" ile bloklandığı için
public ve runner-dostu bir ayna olan **fonrehberi.com** kaynak alındı.

Fonrehberi iki katmanlıdır:
1. Ana liste (``https://www.fonrehberi.com/``) — fon kodu, adı, kategori,
   günlük/aylık/6 aylık/yıllık getiriler.
2. Fon başına detay sayfası (``<CODE>-fonu-kazanci-nedir.html``) — fiyat (TL).

Bu testler her iki katmanı da ``respx`` ile mock'lar; gerçek ağa gitmez.
"""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from kizilelma.collectors.base import CollectorError
from kizilelma.collectors.tefas import TefasCollector
from kizilelma.models import FundData

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
LIST_HTML = (FIXTURES / "fonrehberi_list.html").read_text(encoding="utf-8")
DETAIL_AFA = (FIXTURES / "fonrehberi_detail_afa.html").read_text(encoding="utf-8")
DETAIL_TGE = (FIXTURES / "fonrehberi_detail_tge.html").read_text(encoding="utf-8")
DETAIL_YHS = (FIXTURES / "fonrehberi_detail_yhs.html").read_text(encoding="utf-8")


def _mock_all_ok() -> None:
    """Ana liste + 3 detay sayfasını başarıyla mock'lar."""
    respx.get("https://www.fonrehberi.com/").mock(
        return_value=httpx.Response(200, text=LIST_HTML)
    )
    respx.get(
        "https://www.fonrehberi.com/AFA-fonu-kazanci-nedir.html"
    ).mock(return_value=httpx.Response(200, text=DETAIL_AFA))
    respx.get(
        "https://www.fonrehberi.com/TGE-fonu-kazanci-nedir.html"
    ).mock(return_value=httpx.Response(200, text=DETAIL_TGE))
    respx.get(
        "https://www.fonrehberi.com/YHS-fonu-kazanci-nedir.html"
    ).mock(return_value=httpx.Response(200, text=DETAIL_YHS))


@respx.mock
@pytest.mark.asyncio
async def test_tefas_fetch_returns_fund_list() -> None:
    """Fonrehberi listesinden fon listesi çekilip FundData nesnelerine dönüşür."""
    _mock_all_ok()

    collector = TefasCollector(max_retries=1, retry_delay_range=(0.0, 0.0))
    funds = await collector.fetch()

    # 3 fonun tamamı başarıyla parse edilmeli
    assert len(funds) == 3
    assert all(isinstance(f, FundData) for f in funds)

    codes = {f.code for f in funds}
    assert codes == {"AFA", "TGE", "YHS"}

    afa = next(f for f in funds if f.code == "AFA")
    # Fiyat detay sayfasından gelir
    assert float(afa.price) == pytest.approx(1.234567, rel=1e-6)
    # Kategori listede "Para Piyasası Fonu"
    assert "Para Piyas" in afa.category or "Para Piy" in afa.category
    assert afa.is_qualified_investor is False
    # Getiriler listeden
    assert afa.return_1d is not None
    assert float(afa.return_1d) == pytest.approx(0.15, rel=1e-3)
    assert float(afa.return_1m) == pytest.approx(4.20, rel=1e-3)
    assert float(afa.return_1y) == pytest.approx(48.50, rel=1e-3)
    # Yeni: asset_tags dolu dönmeli (Para Piyasası fonu)
    assert len(afa.asset_tags) > 0
    assert "Para Piyasası" in afa.asset_tags


@respx.mock
@pytest.mark.asyncio
async def test_tefas_marks_serbest_fund_as_qualified() -> None:
    """Adında 'Serbest' veya 'Nitelikli' geçen fonlar qualified işaretlenir."""
    _mock_all_ok()

    collector = TefasCollector(max_retries=1, retry_delay_range=(0.0, 0.0))
    funds = await collector.fetch()

    tge = next(f for f in funds if f.code == "TGE")
    assert tge.is_qualified_investor is True
    # Kategori "Serbest" içermeli (zaten kaynakta öyle)
    assert "Serbest" in tge.category

    # Normal fonlar qualified DEĞİL
    afa = next(f for f in funds if f.code == "AFA")
    assert afa.is_qualified_investor is False


@respx.mock
@pytest.mark.asyncio
async def test_tefas_raises_when_listing_fails() -> None:
    """Ana liste sürekli HTTP 500 dönerse CollectorError fırlatılır."""
    respx.get("https://www.fonrehberi.com/").mock(
        return_value=httpx.Response(500, text="server error")
    )

    collector = TefasCollector(max_retries=2, retry_delay_range=(0.0, 0.0))

    with pytest.raises(CollectorError) as excinfo:
        await collector.fetch()

    assert "tefas" in str(excinfo.value).lower()


@respx.mock
@pytest.mark.asyncio
async def test_tefas_missing_detail_page_skips_fund() -> None:
    """Bir fonun detay sayfası erişilemezse o fon atlanır, diğerleri gelir.

    Toplama iş akışı tek bir bozuk detay sayfası yüzünden kırılmamalıdır.
    """
    respx.get("https://www.fonrehberi.com/").mock(
        return_value=httpx.Response(200, text=LIST_HTML)
    )
    respx.get(
        "https://www.fonrehberi.com/AFA-fonu-kazanci-nedir.html"
    ).mock(return_value=httpx.Response(200, text=DETAIL_AFA))
    # TGE detay sayfası 404
    respx.get(
        "https://www.fonrehberi.com/TGE-fonu-kazanci-nedir.html"
    ).mock(return_value=httpx.Response(404))
    respx.get(
        "https://www.fonrehberi.com/YHS-fonu-kazanci-nedir.html"
    ).mock(return_value=httpx.Response(200, text=DETAIL_YHS))

    collector = TefasCollector(max_retries=1, retry_delay_range=(0.0, 0.0))
    funds = await collector.fetch()

    codes = {f.code for f in funds}
    # TGE atlanmalı, AFA ve YHS gelmeli
    assert "AFA" in codes
    assert "YHS" in codes
    assert "TGE" not in codes
    assert len(funds) == 2


@respx.mock
@pytest.mark.asyncio
async def test_tefas_retries_listing_before_giving_up() -> None:
    """Ana liste HTTP 500 dönerse ``max_retries`` kadar tekrar denenir."""
    route = respx.get("https://www.fonrehberi.com/").mock(
        return_value=httpx.Response(500)
    )

    collector = TefasCollector(max_retries=3, retry_delay_range=(0.0, 0.0))

    with pytest.raises(CollectorError):
        await collector.fetch()

    assert route.call_count == 3


# ---------------------------------------------------------------- #
# Sektör/varlık etiketi çıkarımı (_extract_asset_tags)
# ---------------------------------------------------------------- #
#
# Neden ayrı testler? Etiket üretimi saf bir fonksiyon; ağ gerektirmez.
# HTML fixture'larını şişirmek yerine doğrudan fonksiyonu çağırıyoruz.

def test_extract_asset_tags_hisse_teknoloji() -> None:
    """Teknoloji hisse fonunda hem 'Hisse' hem 'Teknoloji' etiketi olmalı."""
    from kizilelma.collectors.tefas import _extract_asset_tags

    tags = _extract_asset_tags(
        "AK PORTFÖY TEKNOLOJİ HİSSE SENEDİ FONU",
        "Hisse Senedi Fonu",
    )
    assert "Teknoloji" in tags
    assert "Hisse" in tags


def test_extract_asset_tags_para_piyasasi() -> None:
    """Para piyasası fonu 'Para Piyasası' etiketini almalı."""
    from kizilelma.collectors.tefas import _extract_asset_tags

    tags = _extract_asset_tags(
        "İŞ PORTFÖY PARA PİYASASI FONU",
        "Para Piyasası Fonu",
    )
    assert "Para Piyasası" in tags


def test_extract_asset_tags_altin_katilim() -> None:
    """Katılım altın fonunda 'Altın' ve 'Faizsiz' birlikte olmalı."""
    from kizilelma.collectors.tefas import _extract_asset_tags

    tags = _extract_asset_tags(
        "ZİRAAT PORTFÖY KATILIM ALTIN FONU",
        "Kıymetli Madenler Şemsiye Fonu",
    )
    assert "Altın" in tags
    assert "Faizsiz" in tags
    assert "Kıymetli Maden" in tags


def test_extract_asset_tags_bist30() -> None:
    """BIST 30 endeks fonu 'BIST30' + 'Endeks' + 'Hisse' etiketleri almalı."""
    from kizilelma.collectors.tefas import _extract_asset_tags

    tags = _extract_asset_tags(
        "GARANTİ PORTFÖY BIST 30 ENDEKS HİSSE SENEDİ FONU",
        "Endeks Fonu",
    )
    assert "BIST30" in tags
    assert "Endeks" in tags
    assert "Hisse" in tags


def test_extract_asset_tags_max_six() -> None:
    """Etiket sayısı 6'yı aşmamalı; öncelik sırayla uygulanır."""
    from kizilelma.collectors.tefas import _extract_asset_tags

    # Bilerek çok sayıda tetikleyici kelime içeren bir ad
    tags = _extract_asset_tags(
        "MEGA KATILIM TEKNOLOJİ BANKA SANAYİ HİSSE ALTIN DÖVİZ SERBEST FONU",
        "Karma Serbest Fonu",
    )
    assert len(tags) <= 6


def test_extract_asset_tags_no_keywords_fallback_to_category() -> None:
    """Hiçbir anahtar kelime tutmazsa kategoriden fallback etiket üretmeli."""
    from kizilelma.collectors.tefas import _extract_asset_tags

    tags = _extract_asset_tags(
        "XYZ PORTFÖY ÖZEL FON",  # tetikleyici kelime yok
        "Değişken Fon",
    )
    # En azından bir etiket üretilmiş olmalı (Değişken tema'sı eşleşir)
    assert len(tags) >= 1


def test_extract_asset_tags_tahvil_eurobond() -> None:
    """Eurobond tahvil fonu doğru etiketleri almalı."""
    from kizilelma.collectors.tefas import _extract_asset_tags

    tags = _extract_asset_tags(
        "AK PORTFÖY EUROBOND BORÇLANMA ARAÇLARI FONU",
        "Borçlanma Araçları Fonu",
    )
    assert "Eurobond" in tags
    assert "Tahvil" in tags


def test_extract_asset_tags_deduplicates() -> None:
    """Aynı etiket iki kez üretilmemeli."""
    from kizilelma.collectors.tefas import _extract_asset_tags

    tags = _extract_asset_tags(
        "HİSSE HİSSELİ HİSSE SENEDİ FONU",
        "Hisse Senedi Fonu",
    )
    assert tags.count("Hisse") == 1
