# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""The Ollama client must fail politely when Ollama is not there (no model is used here)."""
import pytest

from core import llm


def test_status_without_ollama(monkeypatch):
    monkeypatch.setattr(llm, "OLLAMA_URL", "http://localhost:9")    # nothing listens there
    ok, message = llm.status()
    assert not ok and "still work by hand" in message


def test_chat_without_ollama(monkeypatch):
    monkeypatch.setattr(llm, "OLLAMA_URL", "http://localhost:9")
    with pytest.raises(llm.LLMError):
        llm.chat("system", "skip truck 3", {})
