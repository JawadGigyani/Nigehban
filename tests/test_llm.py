import json
import os

import httpx
import pytest
from pydantic import BaseModel, ConfigDict

from backend.app.config.settings import JsonMode, LLMProvider, Settings
from backend.app.llm import (
    LLMConfigError,
    LLMError,
    LLMService,
    ModelSlot,
    build_chat_model,
    to_strict_schema,
)


class Extract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    district: str
    deaths: int | None = None


def _chat_response(content: str) -> dict:
    return {
        "id": "x", "object": "chat.completion", "created": 0, "model": "m",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


class FakeServer:
    """Answers chat-completion calls from a queue; a status int means an error reply."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests: list[dict] = []

    def client(self) -> httpx.Client:
        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(json.loads(request.content))
            reply = self.replies.pop(0)
            if isinstance(reply, int):
                return httpx.Response(reply, json={"error": {"message": "fail"}})
            return httpx.Response(200, json=_chat_response(reply))

        return httpx.Client(transport=httpx.MockTransport(handler))


def _slot(server: FakeServer, provider=LLMProvider.GROQ, mode=JsonMode.JSON_SCHEMA) -> ModelSlot:
    model = build_chat_model(api_key="test", model="m", base_url="http://llm.test/v1",
                             max_retries=0, http_client=server.client())
    return ModelSlot(provider, model, mode)


def test_strict_schema_requires_all_fields_and_no_extras():
    schema = to_strict_schema(Extract.model_json_schema())
    assert schema["required"] == ["district", "deaths"]
    assert schema["additionalProperties"] is False
    assert "default" not in json.dumps(schema)


def test_structured_output_json_schema_mode():
    server = FakeServer(['{"district": "Buner", "deaths": 3}'])
    out = LLMService([_slot(server)]).complete_structured("s", "u", Extract)
    assert out == Extract(district="Buner", deaths=3)
    fmt = server.requests[0]["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["schema"]["additionalProperties"] is False


def test_structured_output_retries_invalid_then_succeeds():
    server = FakeServer(['{"district": 5}', '{"district": "Swat", "deaths": null}'])
    out = LLMService([_slot(server)]).complete_structured("s", "u", Extract)
    assert out.district == "Swat"
    assert len(server.requests) == 2


def test_structured_output_gives_up_after_retries():
    server = FakeServer(["not json"] * 3)
    with pytest.raises(LLMError):
        LLMService([_slot(server)], validation_retries=2).complete_structured("s", "u", Extract)
    assert len(server.requests) == 3


def test_json_object_mode_puts_schema_in_prompt():
    server = FakeServer(['{"district": "Dir"}'])
    service = LLMService([_slot(server, mode=JsonMode.JSON_OBJECT)])
    assert service.complete_structured("sys", "u", Extract).district == "Dir"
    assert server.requests[0]["response_format"] == {"type": "json_object"}
    assert "JSON schema" in server.requests[0]["messages"][0]["content"]


def test_falls_back_to_next_provider_on_error():
    primary = FakeServer([429])
    backup = FakeServer(['{"district": "Shangla"}'])
    service = LLMService([_slot(primary), _slot(backup, LLMProvider.GEMINI)], validation_retries=0)
    assert service.complete_structured("s", "u", Extract).district == "Shangla"
    assert len(primary.requests) == 1 and len(backup.requests) == 1


def test_text_completion_and_fallback():
    primary = FakeServer([500])
    backup = FakeServer(["hello"])
    service = LLMService([_slot(primary), _slot(backup, LLMProvider.GEMINI)])
    assert service.complete_text("s", "u") == "hello"


def test_from_settings_builds_primary_and_fallback(monkeypatch):
    monkeypatch.setenv("NIGEHBAN_LLM_PROVIDER", "groq")
    monkeypatch.setenv("NIGEHBAN_LLM_API_KEY", "groq-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")  # unprefixed name works
    s = Settings(_env_file=None)
    assert s.api_key_for(LLMProvider.GEMINI).get_secret_value() == "gemini-key"
    service = LLMService.from_settings(s)
    assert service.providers == (LLMProvider.GROQ, LLMProvider.GROQ, LLMProvider.GEMINI, LLMProvider.GEMINI)
    groq, groq_extra, gemini, gemini_lite = (slot.model for slot in service.slots)
    assert groq.model_name == "openai/gpt-oss-120b"
    assert groq_extra.model_name == "openai/gpt-oss-20b"  # separate free quota
    assert groq.reasoning_effort == "low"
    assert "googleapis.com" in str(gemini.openai_api_base)


def test_from_settings_skips_fallback_without_key(monkeypatch):
    monkeypatch.setenv("NIGEHBAN_LLM_API_KEY", "groq-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("NIGEHBAN_GEMINI_API_KEY", raising=False)
    service = LLMService.from_settings(Settings(_env_file=None, groq_extra_models=[]))
    assert service.providers == (LLMProvider.GROQ,)


def test_from_settings_requires_primary_key(monkeypatch):
    for name in ["NIGEHBAN_LLM_API_KEY", "GROQ_API_KEY", "NIGEHBAN_GROQ_API_KEY"]:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(LLMConfigError):
        LLMService.from_settings(Settings(_env_file=None))


LIVE = pytest.mark.skipif(os.getenv("NIGEHBAN_RUN_LIVE") != "1", reason="set NIGEHBAN_RUN_LIVE=1")


def _live_service(provider: LLMProvider) -> LLMService:
    from backend.app.config import get_settings

    settings = get_settings()
    key = settings.api_key_for(provider)
    if key is None:
        pytest.skip(f"no key for {provider.value}")
    model = build_chat_model(api_key=key.get_secret_value(), model=settings.model_for(provider),
                             base_url=settings.base_url_for(provider))
    return LLMService([ModelSlot(provider, model, JsonMode.JSON_SCHEMA)])


@pytest.mark.live
@LIVE
@pytest.mark.parametrize("provider", [LLMProvider.GROQ, LLMProvider.GEMINI])
def test_live_structured_smoke(provider):
    out = _live_service(provider).complete_structured(
        "Extract fields from the report text.",
        "On 15-08-2025 a flash flood in district Buner killed 3 people.",
        Extract,
    )
    assert out.district.lower() == "buner"
    assert out.deaths == 3


@pytest.mark.live
@LIVE
@pytest.mark.parametrize("provider", [LLMProvider.GROQ, LLMProvider.GEMINI])
def test_live_urdu_text(provider):
    text = _live_service(provider).complete_text(
        "Reply in Urdu (Nastaliq script) in one short sentence.",
        "Tell people to move to higher ground because flash flood risk is high.",
    )
    assert any("؀" <= ch <= "ۿ" for ch in text)  # Arabic-script characters


def test_rate_limited_slot_is_paused_and_skipped():
    now = {"t": 0.0}
    first = FakeServer([429])
    second = FakeServer(['{"district": "Swat"}', '{"district": "Dir"}'])
    service = LLMService([_slot(first), _slot(second)], validation_retries=0,
                         cooldown_s=120, clock=lambda: now["t"])
    assert service.complete_structured("s", "u", Extract).district == "Swat"
    assert service.available_slots() == [1]  # first slot cooling down
    assert service.complete_structured("s", "u", Extract).district == "Dir"
    assert len(first.requests) == 1  # not called again while paused
    now["t"] = 121.0
    assert service.available_slots() == [0, 1]  # back after the cooldown


def test_all_slots_limited_raises_rate_limited_error():
    from backend.app.llm import LLMRateLimitedError

    service = LLMService([_slot(FakeServer([429]))], validation_retries=0)
    with pytest.raises(LLMRateLimitedError):
        service.complete_structured("s", "u", Extract)
    with pytest.raises(LLMRateLimitedError):  # now paused: fails fast, no request
        service.complete_structured("s", "u", Extract)


def test_extra_keys_build_more_slots_without_leaking_keys(monkeypatch):
    monkeypatch.setenv("NIGEHBAN_LLM_API_KEY", "gsk_main")
    monkeypatch.setenv("NIGEHBAN_GROQ_API_KEYS", "gsk_two, gsk_three,gsk_main,")
    monkeypatch.setenv("GEMINI_API_KEY", "gem_main")
    monkeypatch.setenv("NIGEHBAN_GEMINI_API_KEYS", "gem_two")
    s = Settings(_env_file=None)
    assert [k.get_secret_value() for k in s.api_keys_for(LLMProvider.GROQ)] == ["gsk_main", "gsk_two", "gsk_three"]
    service = LLMService.from_settings(s)
    labels = [slot.label for slot in service.slots]
    assert labels == [
        "groq#1:openai/gpt-oss-120b", "groq#1:openai/gpt-oss-20b",
        "groq#2:openai/gpt-oss-120b", "groq#2:openai/gpt-oss-20b",
        "groq#3:openai/gpt-oss-120b", "groq#3:openai/gpt-oss-20b",
        "gemini#1:gemini-3.5-flash", "gemini#1:gemini-3.5-flash-lite",
        "gemini#2:gemini-3.5-flash", "gemini#2:gemini-3.5-flash-lite",
    ]
    assert not any("gsk_" in label or "gem_" in label for label in labels)


def test_prefer_moves_a_provider_first():
    calls = []

    class Model:
        def __init__(self, name):
            self.name = name

    slots = [ModelSlot(LLMProvider.GROQ, Model("groq"), JsonMode.JSON_SCHEMA, "groq#1"),
             ModelSlot(LLMProvider.GEMINI, Model("gemini"), JsonMode.JSON_SCHEMA, "gemini#1")]
    service = LLMService(slots)
    assert service._call_rotating(lambda slot: slot.label) == "groq#1"
    assert service._call_rotating(lambda slot: slot.label, prefer=LLMProvider.GEMINI) == "gemini#1"
