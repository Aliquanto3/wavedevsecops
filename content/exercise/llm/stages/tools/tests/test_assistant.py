"""Assistant, stade 3 : le modèle est joué par une file de réponses prévues."""

from typing import Any

from inventory.assistant import TOOLS, ask, run_tool
from inventory.llm_config import load_config
from inventory.stock import Stock


def _tool_call(name: str, arguments: str = "{}") -> dict[str, Any]:
    call = {"id": "c1", "type": "function", "function": {"name": name, "arguments": arguments}}
    return {"role": "assistant", "content": None, "tool_calls": [call]}


def _scripted(*messages: dict[str, Any]):
    queue = list(messages)
    sent: list[dict[str, Any]] = []

    def fake_send(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        sent.append({**payload, "messages": list(payload["messages"])})
        return {"choices": [{"message": queue.pop(0)}]}

    return fake_send, sent


def _stock() -> Stock:
    stock = Stock()
    stock.add("vis", 2, threshold=5)
    return stock


def test_the_tools_are_offered_to_the_model() -> None:
    send, sent = _scripted({"role": "assistant", "content": "Bonjour"})
    assert ask("Salut ?", load_config(), _stock(), send) == "Bonjour"
    assert sent[0]["tools"] == TOOLS


def test_a_tool_call_is_run_then_answered() -> None:
    send, sent = _scripted(
        _tool_call("get_quantity", '{"name": "vis"}'),
        {"role": "assistant", "content": "Il reste 2 vis."},
    )
    assert ask("Combien de vis ?", load_config(), _stock(), send) == "Il reste 2 vis."
    assert sent[1]["messages"][-1] == {"role": "tool", "tool_call_id": "c1", "content": "2"}


def test_a_tool_error_goes_back_to_the_model() -> None:
    assert "n'existe pas" in run_tool(_stock(), "get_quantity", {"name": "clou"})
    assert "inconnu" in run_tool(_stock(), "supprimer_tout", {})
    assert run_tool(_stock(), "list_below_threshold", {}) == "vis"
