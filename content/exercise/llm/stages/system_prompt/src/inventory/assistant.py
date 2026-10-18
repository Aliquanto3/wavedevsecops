"""Assistant du stock, stade 2 : un prompt système cadre le modèle."""

from __future__ import annotations

from inventory.llm_client import Send, chat
from inventory.llm_config import LlmConfig
from inventory.stock import Stock

SYSTEM_PROMPT = (
    "Vous êtes l'assistant du stock d'un petit atelier. "
    "Répondez en français, en une ou deux phrases, sans inventer de chiffres."
)


def ask(
    question: str,
    config: LlmConfig,
    stock: Stock | None = None,
    send: Send | None = None,
) -> str:
    """Pose `question` au modèle, cadré par le prompt système, et rend sa réponse."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    message = chat(config, messages, send=send)
    return message.get("content") or ""
