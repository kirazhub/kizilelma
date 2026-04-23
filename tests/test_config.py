"""Config modülü testleri."""
import os
import pytest
from kizilelma.config import Config, get_config


def test_config_reads_from_environment(monkeypatch):
    """Config env değişkenlerinden okur."""
    monkeypatch.setenv("TCMB_API_KEY", "test_tcmb")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test_claude")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_bot")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

    config = Config()
    assert config.tcmb_api_key == "test_tcmb"
    assert config.anthropic_api_key == "test_claude"
    assert config.telegram_bot_token == "test_bot"
    assert config.telegram_chat_id == "12345"


def test_config_environment_defaults_to_development(monkeypatch):
    """ENVIRONMENT değeri yoksa development."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("TCMB_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "x")

    config = Config()
    assert config.environment == "development"
