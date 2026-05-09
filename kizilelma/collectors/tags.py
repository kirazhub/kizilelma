"""Fon adından sektör/varlık/coğrafya/tema etiketleri çıkaran modül.

Bu modül, ``kizilelma/collectors/tefas.py`` içindeki saf ``_extract_asset_tags``
fonksiyonunu **public bir API** olarak sunar ve üzerine eklemeler yapar.

Neden ayrı modül?
    Etiketleme mantığı sadece TEFAS collector tarafından değil, ``retriever.py``
    (eski DB kayıtları için runtime'da etiket üretmek) ve raporlayıcılar tarafından
    da kullanılıyor. Tek bir public yer olması iki kopya kod yazılmasını önler.

Public API:
    extract_tags(name, category)     → list[str]   En sık kullanılan
    extract_primary_sector(name, category) → str   Birincil sektör (UI badge)
    get_tag_summary(tags)            → dict        Etiketleri gruplara böl

Etiket aileleri:
    - Sektör   → Banka, Teknoloji, Sağlık, Enerji, ...
    - Varlık   → Hisse, Tahvil, Para Piyasası, Altın, Eurobond, Sukuk, ...
    - Coğrafya → Yurtiçi, Yurtdışı, ABD, Avrupa, Asya, ...
    - Tema     → BIST 30, BIST 100, Endeks, Faizsiz, ESG, Emeklilik, ...
"""
from __future__ import annotations

# Mevcut, batarya-test edilmiş çekirdek fonksiyonu re-export et.
# tefas.py 'deki Türkçe normalizasyon (ç→C, ş→S, ...) ve eşleme tabloları
# burada tekrarlanmıyor — tek kaynak prensibi (DRY).
from kizilelma.collectors.tefas import (
    _extract_asset_tags as _core_extract,
    _SECTOR_MAP,
    _ASSET_MAP,
    _GEO_MAP,
    _THEME_MAP,
)

__all__ = [
    "extract_tags",
    "extract_primary_sector",
    "get_tag_summary",
]


# ----------------------------------------------------------------- #
# Türetilmiş tag kümeleri (gruplandırma için)
# ----------------------------------------------------------------- #
# Çekirdek fonksiyon BIST30 / BIST100 etiketlerini de üretir; bunlar
# THEME ailesine yazılır (görsel olarak da öyle gösteriliyor).
_SECTOR_TAGS = {tag for _, tag in _SECTOR_MAP}
_ASSET_TAGS = {tag for _, tag in _ASSET_MAP}
_GEO_TAGS = {tag for _, tag in _GEO_MAP} | {"Yurtiçi", "Yurtdışı"}
_THEME_TAGS = {tag for _, tag in _THEME_MAP} | {"BIST30", "BIST100"}


# Birincil sektör seçilirken kullanılacak öncelik sırası.
# Daha "spesifik" olan üstte → tek kelimede fonu tanımlayan etiket.
_SECTOR_PRIORITY: tuple[str, ...] = (
    "Banka",
    "Teknoloji",
    "Sağlık",
    "Enerji",
    "Otomotiv",
    "Gayrimenkul",
    "Gıda",
    "Metal",
    "Kimya",
    "Tekstil",
    "Savunma",
    "Telekom",
    "Ulaştırma",
    "Sanayi",
    "Turizm",
)


def extract_tags(name: str, category: str = "") -> list[str]:
    """Fon adı ve kategorisinden akıllı etiketler üretir.

    Args:
        name: Fonun tam adı (örn. "Akbank Bankacılık Hisse Senedi Fonu").
        category: Fon kategorisi (varsa). Boş bırakılabilir.

    Returns:
        Etiket listesi. Çekirdek fonksiyon en spesifikten en geneline
        sıralanmış ve maks. 6 etiket döndürür. Bu wrapper ek olarak:
            - Hiçbir coğrafya etiketi yoksa "Yurtiçi" ekler (TR fonu varsayımı).
            - Sıralı listede tekrarları korumaz.
    """
    # Çekirdek (sıralı, max 6, dedupe edilmiş) etiketleri al
    core = _core_extract(name or "", category or "")

    # Coğrafya hiç işaretlenmediyse default "Yurtiçi" ekle.
    # _GEO_TAGS, "Yurtdışı"yı da içerir; biri bile varsa eklemiyoruz.
    if not any(t in _GEO_TAGS for t in core):
        # 6 limiti zaten core'da uygulandı; +1 yer açmak için son etiketi
        # düşürmüyoruz, sadece "Yurtiçi"yı ekleyip listeyi tekrar 6'a sıkıyoruz.
        core = (core + ["Yurtiçi"])[:6]

    return core


def extract_primary_sector(name: str, category: str = "") -> str:
    """Birincil (öne çıkan) sektör etiketini döndürür.

    Args:
        name: Fon adı.
        category: Kategori (opsiyonel).

    Returns:
        En spesifik sektör etiketi (örn. "Banka"). Hiç sektör tutmadıysa
        "Genel".
    """
    tags = extract_tags(name, category)
    for sector in _SECTOR_PRIORITY:
        if sector in tags:
            return sector
    return "Genel"


def get_tag_summary(tags: list[str]) -> dict[str, list[str]]:
    """Bir etiket listesini ailesine göre gruplar.

    Args:
        tags: ``extract_tags()`` çıktısı veya benzer liste.

    Returns:
        ``{"sectors": [...], "assets": [...], "geography": [...], "themes": [...]}``
        Her bir liste, ``tags`` içindeki sırayı korur.
    """
    sectors: list[str] = []
    assets: list[str] = []
    geography: list[str] = []
    themes: list[str] = []

    for t in tags:
        if t in _SECTOR_TAGS:
            sectors.append(t)
        elif t in _ASSET_TAGS:
            assets.append(t)
        elif t in _GEO_TAGS:
            geography.append(t)
        elif t in _THEME_TAGS:
            themes.append(t)
        # Tanınmayan etiket (kategori fallback'i gibi) sessizce atlanır

    return {
        "sectors": sectors,
        "assets": assets,
        "geography": geography,
        "themes": themes,
    }
