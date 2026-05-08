"""Web uygulaması için smoke testleri.

Bu testler:
    - Ana HTML sayfasının döndürüldüğünü doğrular
    - /api/status endpoint'inin çalıştığını doğrular
    - /api/snapshot endpoint'inin cache + mock veriyle çalıştığını doğrular
    - /api/history endpoint'inin DB'siz de çakılmadığını doğrular

Gerçek TEFAS çağrısı yapılmaz — `collect_all_data` fonksiyonu mock'lanır.
"""
import datetime as dt
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from kizilelma.models import FundData, MarketSnapshot, RepoRate
from kizilelma.web import app as web_app_module
from kizilelma.web.app import app, _cache


@pytest.fixture(autouse=True)
def reset_cache():
    """Her testten önce cache'i sıfırla."""
    _cache._data = None
    _cache._fetched_at = None
    yield
    _cache._data = None
    _cache._fetched_at = None


@pytest.fixture
def mock_snapshot():
    """Test için minimum MarketSnapshot üretir."""
    return MarketSnapshot(
        timestamp=dt.datetime(2025, 5, 9, 10, 0, 0),
        funds=[
            FundData(
                code="TGE",
                name="Test Para Piyasası Fonu",
                category="Para Piyasası",
                price=Decimal("2.1234"),
                date=dt.date(2025, 5, 9),
                return_1d=Decimal("0.15"),
                return_1m=Decimal("3.5"),
                return_1y=Decimal("45.2"),
            ),
            FundData(
                code="AFA",
                name="Test Hisse Fonu",
                category="Değişken Fon",
                price=Decimal("12.3456"),
                date=dt.date(2025, 5, 9),
                return_1d=Decimal("-0.5"),
                return_1m=Decimal("-2.1"),
                return_1y=Decimal("63.8"),
            ),
        ],
        repo_rates=[
            RepoRate(
                type="politika",
                maturity="overnight",
                rate=Decimal("37.00"),
                date=dt.date(2025, 5, 9),
            ),
        ],
    )


def test_home_returns_html():
    """Ana sayfa 200 dönmeli ve KIZILELMA içermeli."""
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "KIZILELMA" in r.text.upper()
    assert "TERMINAL" in r.text.upper()


def test_static_css_served():
    """CSS dosyası /static/style.css üzerinden erişilebilir olmalı."""
    client = TestClient(app)
    r = client.get("/static/style.css")
    assert r.status_code == 200
    assert "--bg-primary" in r.text  # renk değişkenimiz var mı


def test_static_js_served():
    """JS dosyası servis ediliyor olmalı."""
    client = TestClient(app)
    r = client.get("/static/app.js")
    assert r.status_code == 200
    assert "loadSnapshot" in r.text


def test_status_endpoint():
    """Sistem sağlık kontrolü LIVE dönmeli."""
    client = TestClient(app)
    r = client.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "LIVE"
    assert "istanbul_time" in data
    assert "server_time" in data
    assert "cache_fresh" in data


def test_snapshot_endpoint_uses_mock(monkeypatch, mock_snapshot):
    """Snapshot endpoint mock veriyle doğru yapıda cevap vermeli."""

    async def fake_collect():
        return mock_snapshot

    # collect_all_data fonksiyonunu mock'la
    import kizilelma.scheduler.daily_job as daily_job
    monkeypatch.setattr(daily_job, "collect_all_data", fake_collect)

    client = TestClient(app)
    r = client.get("/api/snapshot")
    assert r.status_code == 200
    payload = r.json()
    assert "data" in payload
    assert "cached" in payload
    assert payload["cached"] is False  # İlk çağrı taze olmalı
    assert len(payload["data"]["funds"]) == 2
    assert payload["data"]["funds"][0]["code"] == "TGE"


def test_snapshot_endpoint_caches_second_call(monkeypatch, mock_snapshot):
    """İkinci çağrı cache'den dönmeli."""
    call_count = {"n": 0}

    async def fake_collect():
        call_count["n"] += 1
        return mock_snapshot

    import kizilelma.scheduler.daily_job as daily_job
    monkeypatch.setattr(daily_job, "collect_all_data", fake_collect)

    client = TestClient(app)

    r1 = client.get("/api/snapshot")
    r2 = client.get("/api/snapshot")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["cached"] is False
    assert r2.json()["cached"] is True
    assert call_count["n"] == 1  # Sadece tek çağrı yapılmış olmalı


def test_history_endpoint_handles_no_db(monkeypatch):
    """DB yoksa bile endpoint boş liste döndürmeli (hata vermemeli)."""

    def fake_get_recent(*args, **kwargs):
        raise RuntimeError("db yok")

    import kizilelma.storage.db as db_mod
    monkeypatch.setattr(db_mod, "get_recent_snapshots", fake_get_recent)

    client = TestClient(app)
    r = client.get("/api/history")
    assert r.status_code == 200
    assert r.json() == []


def test_snapshot_endpoint_returns_503_on_failure(monkeypatch):
    """Collect işlemi patlarsa 503 + error mesajı dönmeli."""

    async def fake_collect():
        raise RuntimeError("TEFAS düştü")

    import kizilelma.scheduler.daily_job as daily_job
    monkeypatch.setattr(daily_job, "collect_all_data", fake_collect)

    client = TestClient(app)
    r = client.get("/api/snapshot")
    assert r.status_code == 503
    assert "error" in r.json()
