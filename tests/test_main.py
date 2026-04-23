"""Main CLI testleri."""
from unittest.mock import AsyncMock, patch

import pytest

from kizilelma.main import async_main_run_now


@pytest.mark.asyncio
async def test_async_main_run_now_calls_daily_job():
    """run-now komutu daily_job'u tetikler."""
    async def fake_job():
        return {"status": "success", "sent_messages": 8}

    with patch("kizilelma.main.run_daily_job", side_effect=fake_job):
        result = await async_main_run_now()

    assert result["status"] == "success"
    assert result["sent_messages"] == 8
