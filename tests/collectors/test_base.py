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
