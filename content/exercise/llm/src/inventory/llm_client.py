"""Client d'une API compatible OpenAI (`/v1/chat/completions`), avec `httpx`.

Le seul appel réseau du projet est `post_json`. Les tests le remplacent par une fonction
`send` : ils ne touchent jamais au réseau.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from inventory.llm_config import LlmConfig

Send = Callable[[str, dict[str, Any], float], dict[str, Any]]
"""`send(url, payload, timeout) -> réponse JSON`."""


def post_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    import httpx  # importé ici : les tests qui remplacent `send` n'en ont pas besoin

    response = httpx.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def chat(
    config: LlmConfig,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    send: Send | None = None,
) -> dict[str, Any]:
    """Envoie la conversation et rend le message de réponse du modèle."""
    payload: dict[str, Any] = {"model": config.model, "messages": messages}
    if tools:
        payload["tools"] = tools
    reply = (send or post_json)(config.chat_url, payload, config.timeout_seconds)
    return reply["choices"][0]["message"]
