"""Ekonomi haberleri RSS collector.

Birden fazla RSS feed'inden haberleri çeker, birleştirir ve sıralar.
Bir feed başarısız olursa diğerleri çalışmaya devam eder (hata toleranslı).
"""
import asyncio
import datetime as dt
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
    def _parse_date(entry) -> Optional[dt.datetime]:
        """RSS entry'sinden tarih parse et."""
        for field in ("published", "updated", "pubDate"):
            value = entry.get(field)
            if not value:
                continue
            try:
                d = parsedate_to_datetime(value)
                # tzinfo'yu kaldırarak naive datetime'a çevir (Pydantic uyumu)
                return d.replace(tzinfo=None)
            except (TypeError, ValueError):
                continue
        return None
