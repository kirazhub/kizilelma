"""Tag çıkarımı (kizilelma.collectors.tags) testleri.

Bu testler ``extract_tags`` public API'sini sınar; çekirdek (mevcut
``_extract_asset_tags``) zaten ``tests/collectors/test_tefas.py`` tarafından
test edildiği için burada onu tekrarlamıyoruz, sadece wrapper'ın eklediği
davranışlara odaklanıyoruz.
"""
from kizilelma.collectors.tags import (
    extract_tags,
    extract_primary_sector,
    get_tag_summary,
)


def test_extract_banka_tag():
    """Bankacılık fonunda 'Banka' ve 'Hisse' etiketleri olmalı."""
    tags = extract_tags("AKBANK BANKACILIK HİSSE SENEDİ FONU")
    assert "Banka" in tags
    assert "Hisse" in tags


def test_extract_teknoloji_tag():
    """Teknoloji sektör fonu 'Teknoloji' etiketini almalı."""
    tags = extract_tags("GARANTİ TEKNOLOJİ SEKTÖR FONU")
    assert "Teknoloji" in tags


def test_extract_altin_tag():
    """Altın fonu 'Altın' etiketini almalı."""
    tags = extract_tags("İŞ ALTIN YATIRIM FONU")
    assert "Altın" in tags


def test_extract_para_piyasasi_from_category():
    """Ad'da değil sadece kategoride 'Para Piyasası' olsa da yakalamalı."""
    tags = extract_tags("Generic Fund Name", category="Para Piyasası Fonu")
    assert "Para Piyasası" in tags


def test_default_yurtici():
    """Yurtdışı/global bilgisi yoksa Yurtiçi default eklenir."""
    tags = extract_tags("AK PORTFÖY HİSSE SENEDİ FONU")
    assert "Yurtiçi" in tags


def test_yurtdisi_detection():
    """Global/dünya/yabancı geçen fonlar Yurtdışı işaretlenir, Yurtiçi DEĞİL."""
    tags = extract_tags("TUNDRA YABANCI HİSSE FONU")
    assert "Global" in tags  # 'YABANCI' → Global
    assert "Yurtiçi" not in tags  # default eklenmemeli


def test_bist30_detection():
    """BIST 30 endeks fonu doğru etiketleri almalı."""
    tags = extract_tags("GARANTİ BIST 30 ENDEKS FONU")
    assert "BIST30" in tags
    assert "Endeks" in tags


def test_extract_primary_sector_banka():
    """Bankacılık fonunun birincil sektörü 'Banka' olmalı."""
    sector = extract_primary_sector("AKBANK BANKACILIK HİSSE SENEDİ FONU")
    assert sector == "Banka"


def test_extract_primary_sector_yok_genel():
    """Hiçbir sektör eşleşmezse 'Genel' dönmeli."""
    sector = extract_primary_sector("XYZ PORTFÖY PARA PİYASASI FONU")
    assert sector == "Genel"


def test_get_tag_summary_groups():
    """get_tag_summary etiketleri ailesine göre doğru grupluyor."""
    tags = extract_tags("GARANTİ BIST 30 ENDEKS BANKA HİSSE SENEDİ FONU")
    summary = get_tag_summary(tags)
    # Banka sektörde
    assert "Banka" in summary["sectors"]
    # Hisse varlıkta
    assert "Hisse" in summary["assets"]
    # BIST30 + Endeks tema'da
    assert "BIST30" in summary["themes"]
    # Yurtiçi default coğrafya'da
    assert "Yurtiçi" in summary["geography"]
