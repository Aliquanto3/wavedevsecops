"""Assistant, stade 2 : l'appel réseau est remplacé par `fake_send`."""

from typing import Any

from inventory.assistant import SYSTEM_PROMPT, ask
from inventory.llm_config import load_config


def test_the_system_prompt_comes_first() -> None:
    sent: list[dict[str, Any]] = []

    def fake_send(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        sent.append(payload)
        return {"choices": [{"message": {"role": "assistant", "content": "Bonjour !"}}]}

    assert ask("Salut ?", load_config(), send=fake_send) == "Bonjour !"
    assert sent[0]["messages"] == [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Salut ?"},
    ]
