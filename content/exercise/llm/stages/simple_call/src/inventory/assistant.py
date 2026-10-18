"""Assistant du stock, stade 1 : un appel simple au modèle."""

from __future__ import annotations

from inventory.llm_client import Send, chat
from inventory.llm_config import LlmConfig
from inventory.stock import Stock


def ask(
    question: str,
    config: LlmConfig,
    stock: Stock | None = None,
    send: Send | None = None,
) -> str:
    """Pose `question` au modèle et rend sa réponse."""
    message = chat(config, [{"role": "user", "content": question}], send=send)
    return message.get("content") or ""
