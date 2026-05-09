"""Retriever testleri."""
import pytest
from kizilelma.agent.retriever import retrieve_context, format_context_for_prompt


def test_retrieve_context_returns_dict():
    """retrieve_context her zaman dict döner."""
    result = retrieve_context("ANK fonu nasıl?")
    assert isinstance(result, dict)
    assert "funds" in result
    assert "repo_rates" in result


def test_format_context_returns_string():
    """format_context_for_prompt string döner."""
    context = {
        "funds": [],
        "repo_rates": [],
        "bonds": [],
        "sukuks": [],
        "eurobonds": [],
        "latest_snapshot": None,
    }
    text = format_context_for_prompt(context)
    assert isinstance(text, str)
