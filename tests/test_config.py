"""Config modülü testleri."""
import os
import pytest
from kizilelma.config import Config, get_config


def test_config_reads_from_environment(monkeypatch):
    """Config env değişkenlerinden okur."""
    monkeypatch.setenv("TCMB_API_KEY", "test_tcmb")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test_claude")

    config = Config()
    assert config.tcmb_api_key == "test_tcmb"
    assert config.anthropic_api_key == "test_claude"


def test_config_environment_defaults_to_development(monkeypatch):
    """ENVIRONMENT değeri yoksa development."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("TCMB_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")

    config = Config()
    assert config.environment == "development"
