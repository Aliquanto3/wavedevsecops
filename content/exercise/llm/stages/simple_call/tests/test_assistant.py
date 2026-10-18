"""Assistant, stade 1 : l'appel réseau est remplacé par `fake_send`."""

from typing import Any

from inventory.assistant import ask
from inventory.llm_config import load_config


def test_ask_returns_the_model_answer() -> None:
    sent: list[dict[str, Any]] = []

    def fake_send(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        sent.append(payload)
        return {"choices": [{"message": {"role": "assistant", "content": "Bonjour !"}}]}

    assert ask("Salut ?", load_config(), send=fake_send) == "Bonjour !"
    assert sent[0]["messages"] == [{"role": "user", "content": "Salut ?"}]


def test_empty_answer_gives_an_empty_text() -> None:
    def fake_send(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        return {"choices": [{"message": {"role": "assistant", "content": None}}]}

    assert ask("Salut ?", load_config(), send=fake_send) == ""
