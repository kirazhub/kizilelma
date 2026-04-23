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
