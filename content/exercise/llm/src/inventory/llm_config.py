"""Lecture de `llm.toml` : l'endpoint visé et la liste des endpoints autorisés."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "llm.toml"


class LlmConfigError(ValueError):
    """`llm.toml` est incomplet, ou vise un endpoint qu'il n'autorise pas."""


def _normalize(url: str) -> str:
    return url.strip().rstrip("/")


@dataclass(frozen=True)
class LlmConfig:
    base_url: str
    model: str
    timeout_seconds: float
    allowed_endpoints: tuple[str, ...]

    def __post_init__(self) -> None:
        allowed = {_normalize(url) for url in self.allowed_endpoints}
        if _normalize(self.base_url) not in allowed:
            raise LlmConfigError(
                f"L'endpoint « {self.base_url} » n'est pas dans allowed_endpoints de llm.toml."
            )

    @property
    def chat_url(self) -> str:
        return f"{_normalize(self.base_url)}/chat/completions"


def load_config(path: Path = DEFAULT_PATH) -> LlmConfig:
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    try:
        return LlmConfig(
            base_url=data["base_url"],
            model=data["model"],
            timeout_seconds=float(data.get("timeout_seconds", 60)),
            allowed_endpoints=tuple(data["allowed_endpoints"]),
        )
    except KeyError as missing:
        raise LlmConfigError(f"llm.toml : la clé {missing} est absente.") from None
