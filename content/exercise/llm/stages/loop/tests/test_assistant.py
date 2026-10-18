"""Assistant, stade 4 : le modèle est joué par une file de réponses prévues."""

from typing import Any

from inventory.assistant import MAX_STEPS, ask, run_tool
from inventory.llm_config import load_config
from inventory.stock import Stock


def _tool_call(name: str, arguments: str = "{}") -> dict[str, Any]:
    call = {"id": "c1", "type": "function", "function": {"name": name, "arguments": arguments}}
    return {"role": "assistant", "content": None, "tool_calls": [call]}


def _stock() -> Stock:
    stock = Stock()
    stock.add("vis", 2, threshold=5)
    stock.add("colle", 1, threshold=3)
    return stock


def test_the_loop_chains_several_tool_calls() -> None:
    queue = [
        _tool_call("list_below_threshold"),
        _tool_call("get_quantity", '{"name": "vis"}'),
        {"role": "assistant", "content": "Il faut recommander la colle et les vis."},
    ]

    def fake_send(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        return {"choices": [{"message": queue.pop(0)}]}

    answer = ask("Que faut-il commander ?", load_config(), _stock(), fake_send)
    assert answer == "Il faut recommander la colle et les vis."
    assert not queue


def test_the_loop_stops_after_max_steps() -> None:
    calls = 0

    def fake_send(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {"choices": [{"message": _tool_call("list_below_threshold")}]}

    assert "pas pu conclure" in ask("Boucle ?", load_config(), _stock(), fake_send)
    assert calls == MAX_STEPS


def test_a_tool_error_goes_back_to_the_model() -> None:
    assert "n'existe pas" in run_tool(_stock(), "get_quantity", {"name": "clou"})
    assert "inconnu" in run_tool(_stock(), "supprimer_tout", {})
    assert run_tool(_stock(), "list_below_threshold", {}) == "colle, vis"
