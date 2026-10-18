"""Config et client LLM : aucun appel réseau, `send` est remplacé."""

from typing import Any
from urllib.parse import urlsplit

import pytest

from inventory.llm_client import chat
from inventory.llm_config import LlmConfig, LlmConfigError, load_config


def test_default_endpoint_is_local_ollama() -> None:
    config = load_config()
    assert config.base_url == "http://127.0.0.1:11434/v1"
    assert config.chat_url == "http://127.0.0.1:11434/v1/chat/completions"


def test_allowed_endpoints_are_loopback_only() -> None:
    config = load_config()
    for url in config.allowed_endpoints:
        assert urlsplit(url).hostname in {"127.0.0.1", "localhost", "::1"}, url


def test_endpoint_outside_the_allow_list_is_refused() -> None:
    with pytest.raises(LlmConfigError, match="allowed_endpoints"):
        LlmConfig("https://api.exemple.test/v1", "m", 5, ("http://127.0.0.1:11434/v1",))


def test_chat_builds_the_request_and_returns_the_message() -> None:
    seen: dict[str, Any] = {}

    def fake_send(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        seen.update(url=url, payload=payload, timeout=timeout)
        return {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

    config = load_config()
    message = chat(config, [{"role": "user", "content": "salut"}], send=fake_send)
    assert message["content"] == "ok"
    assert seen["url"] == config.chat_url
    assert seen["payload"]["model"] == config.model
    assert "tools" not in seen["payload"]


def test_post_json_uses_httpx_without_network() -> None:
    httpx = pytest.importorskip("httpx")
    from inventory.llm_client import post_json

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    real_post = httpx.post

    def post(url: str, **kwargs: Any) -> httpx.Response:
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            return client.post(url, **kwargs)

    httpx.post = post
    try:
        assert post_json("http://127.0.0.1:11434/v1/chat/completions", {}, 1.0) == {"choices": []}
    finally:
        httpx.post = real_post
