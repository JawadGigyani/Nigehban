import json
import os

import httpx
import pytest
from pydantic import BaseModel, ConfigDict

from backend.app.config.settings import JsonMode, Settings
from backend.app.llm import LLMClient, LLMConfigError, LLMError, to_strict_schema


class Extract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    district: str
    deaths: int | None = None


def _chat_response(content: str) -> dict:
    return {
        "id": "x", "object": "chat.completion", "created": 0, "model": "m",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": content}}],
    }


def _client(replies: list[str], seen: list[dict], json_mode=JsonMode.JSON_SCHEMA) -> LLMClient:
    queue = list(replies)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=_chat_response(queue.pop(0)))

    return LLMClient(
        api_key="test", model="m", base_url="http://llm.test/v1", json_mode=json_mode,
        max_retries=0, http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_strict_schema_requires_all_fields_and_no_extras():
    schema = to_strict_schema(Extract.model_json_schema())
    assert schema["required"] == ["district", "deaths"]
    assert schema["additionalProperties"] is False
    assert "default" not in json.dumps(schema)


def test_structured_output_json_schema_mode():
    seen: list[dict] = []
    out = _client(['{"district": "Buner", "deaths": 3}'], seen).complete_structured("s", "u", Extract)
    assert out == Extract(district="Buner", deaths=3)
    fmt = seen[0]["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True


def test_structured_output_retries_on_invalid_then_succeeds():
    seen: list[dict] = []
    client = _client(['{"district": 5}', '{"district": "Swat", "deaths": null}'], seen)
    out = client.complete_structured("s", "u", Extract)
    assert out.district == "Swat"
    assert len(seen) == 2
    assert "did not match the schema" in seen[1]["messages"][-1]["content"]


def test_structured_output_gives_up():
    client = _client(["not json"] * 3, [])
    with pytest.raises(LLMError):
        client.complete_structured("s", "u", Extract)


def test_json_object_mode_puts_schema_in_prompt():
    seen: list[dict] = []
    _client(['{"district": "Dir"}'], seen, JsonMode.JSON_OBJECT).complete_structured("sys", "u", Extract)
    assert seen[0]["response_format"] == {"type": "json_object"}
    assert "JSON schema" in seen[0]["messages"][0]["content"]


def test_from_settings_requires_key(monkeypatch):
    monkeypatch.delenv("NIGEHBAN_LLM_API_KEY", raising=False)
    with pytest.raises(LLMConfigError):
        LLMClient.from_settings(Settings(_env_file=None))


@pytest.mark.live
@pytest.mark.skipif(os.getenv("NIGEHBAN_RUN_LIVE") != "1", reason="set NIGEHBAN_RUN_LIVE=1")
def test_live_structured_smoke():
    """Real call to the configured provider (reads .env)."""

    from backend.app.config import get_settings

    client = LLMClient.from_settings(get_settings())
    out = client.complete_structured(
        "Extract fields from the report text.",
        "On 15-08-2025 a flash flood in district Buner killed 3 people.",
        Extract,
    )
    assert out.district.lower() == "buner"
    assert out.deaths == 3
