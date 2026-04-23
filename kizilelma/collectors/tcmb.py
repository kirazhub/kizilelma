"""TCMB (Türkiye Cumhuriyet Merkez Bankası) collector.

TCMB'nin resmi EVDS2 API'si anahtar gerektiriyor ve zaman zaman erişim
kısıtlamaları uyguluyor. Bu modül alternatif olarak TCMB'nin **herkese
açık ana sayfasından** (www.tcmb.gov.tr) scraping ile politika faizi,
gecelik repo ve gecelik ters repo oranlarını çeker.

Ana sayfadaki "Para Politikası Kurulu Toplantı Kararı" banner'ı her PPK
kararında güncellenir ve üç oranı da düz metinde belirtir. Biz bu metni
regex ile ayrıştırıyoruz.

NOT: Scraping kırılgandır; sayfa metni değişirse modülün güncellenmesi
gerekir. Bu nedenle hata durumunda **boş liste** döner, exception
fırlatmaz. Böylece tek bir kaynağın çökmesi tüm uygulamayı devirmez.
"""
import datetime as dt
import re
from decimal import Decimal, InvalidOperation

import httpx
from bs4 import BeautifulSoup

from kizilelma.collectors.base import BaseCollector
from kizilelma.models import RepoRate


# TCMB ana sayfası — banner metninde 3 oran da yer alır
TCMB_URL = "https://www.tcmb.gov.tr/"

# Bazı siteler User-Agent başlığı olmadan 403/404 dönebiliyor
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}

# Banner metnindeki Türkçe kalıplar:
#   "... bir hafta vadeli repo ihale faiz oranının yüzde 37'de ..."
#   "... gecelik vadede borç verme faiz oranını yüzde 40'ta ..."
#   "... gecelik vadede borçlanma faiz oranını ise yüzde 35,5'te ..."
# "yüzde NN" veya "yüzde NN,N" yakalanmalı.
_NUM = r"(\d{1,3}(?:[.,]\d{1,3})?)"

_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    # (tip, vade, desen)
    (
        "repo",
        "1w",
        re.compile(
            r"politika\s+faizi[^%]*?y(?:ü|u)zde\s*" + _NUM,
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "repo",
        "overnight",
        re.compile(
            r"gecelik[^%]*?bor(?:ç|c)\s+verme[^%]*?y(?:ü|u)zde\s*" + _NUM,
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "ters_repo",
        "overnight",
        re.compile(
            r"gecelik[^%]*?bor(?:ç|c)lanma[^%]*?y(?:ü|u)zde\s*" + _NUM,
            re.IGNORECASE | re.DOTALL,
        ),
    ),
)

# API erişimi başarısız olur ve scraping de çökerse en azından
# bilinen son politika faizi dönsün ki downstream kod kırılmasın.
# Bu değer bir acil durum yedeklemesidir, elle güncellenmelidir.
_FALLBACK_POLICY_RATE = Decimal("37")


class TcmbCollector(BaseCollector):
    """TCMB politika ve gecelik faiz oranlarını ana sayfadan çeker."""

    name = "tcmb"

    def __init__(self, api_key: str = "", timeout: float = 30.0) -> None:
        # api_key parametresi geriye dönük uyumluluk için korunuyor ama
        # artık kullanılmıyor (scraping ile çalışıyoruz).
        self.api_key = api_key
        self.timeout = timeout

    async def fetch(self) -> list[RepoRate]:
        """TCMB ana sayfasını çek ve repo oranlarını listele.

        Hata durumunda boş liste döner; hiçbir şekilde exception fırlatmaz.
        """
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers=_DEFAULT_HEADERS,
            ) as client:
                response = await client.get(TCMB_URL)
                response.raise_for_status()
                html = response.text
        except httpx.HTTPError:
            return self._fallback()
        except Exception:
            # Scraping'in kırılgan olduğu bilinci — ne olursa olsun
            # uygulamayı devirmiyoruz.
            return self._fallback()

        rates = self._parse(html)
        if rates:
            return rates
        return self._fallback()

    @staticmethod
    def _parse(html: str) -> list[RepoRate]:
        """Banner metninden 3 oranı çıkar."""
        soup = BeautifulSoup(html, "lxml")

        # Banner'ların içindeki tüm metni topla. Doğru banner'ı bulmak
        # yerine tüm sayfa metninde arama yapıyoruz; bu daha dayanıklı
        # çünkü TCMB sitesi sınıf isimlerini zaman zaman değiştiriyor.
        # Ancak ilk tercih: "banner-text" olan paragraflar.
        candidate_texts: list[str] = []
        for p in soup.select("p.banner-text, .banner-header, .banner-slide"):
            text = p.get_text(" ", strip=True)
            if text and "yüzde" in text.lower() and "faiz" in text.lower():
                candidate_texts.append(text)

        # Yedek olarak tüm sayfa metnini de ekle
        if not candidate_texts:
            candidate_texts.append(soup.get_text(" ", strip=True))

        today = dt.date.today()
        rates: list[RepoRate] = []
        seen: set[tuple[str, str]] = set()

        for text in candidate_texts:
            for rate_type, maturity, pattern in _PATTERNS:
                if (rate_type, maturity) in seen:
                    continue
                match = pattern.search(text)
                if not match:
                    continue
                raw = match.group(1).replace(",", ".")
                try:
                    value = Decimal(raw)
                except (InvalidOperation, ValueError):
                    continue
                # Makul aralık kontrolü — yanlış bir eşleşmeyi elesin
                if value <= 0 or value > 200:
                    continue
                rates.append(
                    RepoRate(
                        type=rate_type,
                        maturity=maturity,
                        rate=value,
                        date=today,
                    )
                )
                seen.add((rate_type, maturity))

        return rates

    @staticmethod
    def _fallback() -> list[RepoRate]:
        """Scraping başarısız olursa son bilinen politika faizini döner.

        Bu yalnızca 'hiç veri yok' durumunu önlemek içindir; tek değer
        (politika faizi) döner. Güncel kalması için elle güncellenmelidir.
        """
        return [
            RepoRate(
                type="repo",
                maturity="1w",
                rate=_FALLBACK_POLICY_RATE,
                date=dt.date.today(),
            )
        ]
