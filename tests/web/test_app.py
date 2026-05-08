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
    _cache._source = None
    yield
    _cache._data = None
    _cache._fetched_at = None
    _cache._source = None


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
    """Collect işlemi patlar VE DB boşsa → 503 + error mesajı dönmeli."""

    async def fake_collect():
        raise RuntimeError("TEFAS düştü")

    import kizilelma.scheduler.daily_job as daily_job
    import kizilelma.storage.db as db_mod
    import kizilelma.web.app as web_app

    monkeypatch.setattr(daily_job, "collect_all_data", fake_collect)
    # DB fallback de None dönsün → gerçek 503
    monkeypatch.setattr(web_app, "get_latest_full_snapshot", lambda: None, raising=False)
    # get_latest_full_snapshot web.app içinde runtime import ediliyor;
    # storage.db modülündeki de yamalayalım ki fallback yolu None döndürsün
    monkeypatch.setattr(db_mod, "get_latest_full_snapshot", lambda engine=None: None)

    client = TestClient(app)
    r = client.get("/api/snapshot")
    assert r.status_code == 503
    assert "error" in r.json()


def test_snapshot_falls_back_to_db_on_live_error(monkeypatch):
    """Canlı veri çekilemezse DB'deki en son snapshot döndürülür."""

    async def fake_collect():
        raise RuntimeError("Network error")

    fake_db_snap = {
        "timestamp": "2026-04-22T10:00:00",
        "snapshot_id": 99,
        "is_historical": True,
        "funds": [
            {
                "code": "AFA",
                "name": "Test Fon",
                "category": "Hisse",
                "price": "1.0",
                "date": "2026-04-22",
                "return_1d": None,
                "return_1w": None,
                "return_1m": "5.0",
                "return_3m": None,
                "return_6m": None,
                "return_1y": "50.0",
                "is_qualified_investor": False,
                "asset_tags": [],
            }
        ],
        "repo_rates": [],
        "bonds": [],
        "sukuks": [],
        "eurobonds": [],
        "news": [],
        "errors": {},
    }

    import kizilelma.scheduler.daily_job as daily_job
    import kizilelma.storage.db as db_mod

    monkeypatch.setattr(daily_job, "collect_all_data", fake_collect)
    monkeypatch.setattr(
        db_mod, "get_latest_full_snapshot", lambda engine=None: fake_db_snap
    )

    client = TestClient(app)
    r = client.get("/api/snapshot")

    assert r.status_code == 200
    payload = r.json()
    assert payload["source"] == "db"
    assert payload["data"]["is_historical"] is True
    assert len(payload["data"]["funds"]) == 1
    assert payload["data"]["funds"][0]["code"] == "AFA"
    assert "Network error" in (payload.get("live_error") or "")


def test_snapshot_live_source_marks_not_historical(monkeypatch, mock_snapshot):
    """Canlı başarılıysa source='live' ve is_historical=False olmalı."""

    async def fake_collect():
        return mock_snapshot

    import kizilelma.scheduler.daily_job as daily_job
    monkeypatch.setattr(daily_job, "collect_all_data", fake_collect)

    client = TestClient(app)
    r = client.get("/api/snapshot")
    assert r.status_code == 200
    payload = r.json()
    assert payload["source"] == "live"
    assert payload["data"]["is_historical"] is False
    assert payload["live_error"] is None


def test_get_latest_full_snapshot_returns_none_when_empty(tmp_path, monkeypatch):
    """DB boşken get_latest_full_snapshot None dönmeli."""
    from kizilelma.storage.db import (
        get_engine,
        get_latest_full_snapshot,
        init_db,
    )

    # İzole test DB'si
    db_file = tmp_path / "test_empty.db"
    monkeypatch.setenv("KIZILELMA_DB", str(db_file))
    engine = get_engine(str(db_file))
    init_db(engine)

    result = get_latest_full_snapshot(engine)
    assert result is None


def test_get_latest_full_snapshot_returns_last_record(tmp_path, monkeypatch, mock_snapshot):
    """DB'de kayıt varsa en sonuncuyu dict olarak dönmeli."""
    from kizilelma.storage.db import (
        get_engine,
        get_latest_full_snapshot,
        init_db,
        save_snapshot,
    )

    db_file = tmp_path / "test_full.db"
    engine = get_engine(str(db_file))
    init_db(engine)
    save_snapshot(mock_snapshot, engine)

    result = get_latest_full_snapshot(engine)
    assert result is not None
    assert result["is_historical"] is True
    assert len(result["funds"]) == 2
    assert result["funds"][0]["code"] in ("TGE", "AFA")
    assert len(result["repo_rates"]) == 1
    # Bonds/sukuks/eurobonds/news boş olmalı (DB'de ayrı tablo yok)
    assert result["bonds"] == []
    assert result["news"] == []
