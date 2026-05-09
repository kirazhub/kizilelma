"""Yeni chat modülü için minimal testler.

Bu testler şunları doğrular:
    - get_context her zaman doğru anahtarlarla bir dict döner (DB boş olsa bile)
    - build_prompt boş context ile bile çalışır
    - ChatRequest modeli geçerli payload'ları kabul eder
"""
from kizilelma.agent.chat import (
    ChatRequest,
    build_prompt,
    get_context,
)


def test_get_context_returns_dict():
    """Boş veya dolu DB fark etmez — anahtarlar her zaman olmalı."""
    ctx = get_context("test")
    assert isinstance(ctx, dict)
    assert "macro_data" in ctx
    assert "funds" in ctx
    assert "repo_rates" in ctx
    assert "latest_snapshot" in ctx


def test_build_prompt_with_empty_context():
    """Boş context bile çalışmalı — crash olmasın."""
    ctx = {
        "macro_data": [],
        "funds": [],
        "repo_rates": [],
        "latest_snapshot": None,
    }
    system, msgs = build_prompt(ctx, "merhaba", [])
    assert isinstance(system, str)
    assert "Kızıl Elma" in system
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert "merhaba" in msgs[0]["content"]


def test_build_prompt_with_history():
    """Geçmiş mesajlar prompt'a eklenmeli."""
    ctx = {
        "macro_data": [],
        "funds": [],
        "repo_rates": [],
        "latest_snapshot": None,
    }
    history = [
        {"role": "user", "content": "selam"},
        {"role": "assistant", "content": "merhaba!"},
    ]
    _, msgs = build_prompt(ctx, "ne haber", history)
    # 2 geçmiş + 1 yeni = 3
    assert len(msgs) == 3
    assert msgs[0]["content"] == "selam"
    assert msgs[1]["content"] == "merhaba!"


def test_chat_request_validates():
    """ChatRequest pydantic modeli — minimal payload kabul etmeli."""
    req = ChatRequest(message="test")
    assert req.message == "test"
    assert req.history == []

    req2 = ChatRequest(message="x", history=[{"role": "user", "content": "y"}])
    assert len(req2.history) == 1


def test_build_prompt_includes_macro_data():
    """Makro veriler prompt'a yazılmalı ki AI 'verim yok' demesin."""
    ctx = {
        "macro_data": [
            {
                "symbol": "USDTRY",
                "name": "Dolar/TL",
                "value": 45.35,
                "currency": "TRY",
                "category": "fx",
                "date": "2026-05-09",
            }
        ],
        "funds": [],
        "repo_rates": [],
        "latest_snapshot": "2026-05-09T10:00:00",
    }
    _, msgs = build_prompt(ctx, "Dolar ne?", [])
    user_text = msgs[-1]["content"]
    assert "Dolar/TL" in user_text
    assert "45" in user_text  # değer prompt'a yazılmış olmalı
