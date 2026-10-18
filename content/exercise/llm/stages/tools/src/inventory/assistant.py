"""Assistant du stock, stade 3 : le modèle peut demander un outil (une seule fois)."""

from __future__ import annotations

import json
from typing import Any

from inventory.llm_client import Send, chat
from inventory.llm_config import LlmConfig
from inventory.stock import Stock, StockError

SYSTEM_PROMPT = (
    "Vous êtes l'assistant du stock d'un petit atelier. "
    "Répondez en français, en une ou deux phrases, sans inventer de chiffres : "
    "utilisez les outils pour lire le stock."
)

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_quantity",
            "description": "Quantité en stock d'un article.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_below_threshold",
            "description": "Articles dont la quantité est sous le seuil d'alerte.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def run_tool(stock: Stock, name: str, arguments: dict[str, Any]) -> str:
    """Exécute l'outil demandé par le modèle ; l'erreur est rendue au modèle, pas levée."""
    try:
        if name == "get_quantity":
            return str(stock.quantity(arguments["name"]))
        if name == "list_below_threshold":
            return ", ".join(stock.below_threshold()) or "aucun"
    except (StockError, KeyError) as error:
        return f"Erreur : {error}"
    return f"Erreur : outil inconnu « {name} »."


def ask(
    question: str,
    config: LlmConfig,
    stock: Stock | None = None,
    send: Send | None = None,
) -> str:
    """Pose `question` ; si le modèle demande des outils, les exécute, puis redemande."""
    stock = stock if stock is not None else Stock()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    message = chat(config, messages, TOOLS, send)
    if message.get("tool_calls"):
        messages.append(message)
        for call in message["tool_calls"]:
            arguments = json.loads(call["function"].get("arguments") or "{}")
            result = run_tool(stock, call["function"]["name"], arguments)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
        message = chat(config, messages, TOOLS, send)
    return message.get("content") or ""
