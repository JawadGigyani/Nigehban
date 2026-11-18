"""LLM access through LangChain.

Every provider (Groq, Gemini, OpenAI, or any OpenAI-compatible server) is a
LangChain `ChatOpenAI` model pointed at that provider's endpoint. The primary
provider is tried first; on errors or rate limits LangChain falls back to the
next one. Structured output is validated against a pydantic model and retried
when it does not match.

The LLM never decides risk levels. Callers use it to extract, explain,
translate and draft. The graph and agent code (M8) uses `LLMService.chat`
and `LLMService.structured(...)` as ordinary LangChain runnables.
"""

from __future__ import annotations

import copy
import json
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, TypeVar

import httpx
from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError

from backend.app.config import Settings
from backend.app.config.settings import JsonMode, LLMProvider

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_PARSE_ERRORS = (ValidationError, OutputParserException, json.JSONDecodeError, ValueError)


class LLMError(RuntimeError):
    pass


class LLMConfigError(LLMError):
    pass


class LLMRateLimitedError(LLMError):
    """Every configured slot is rate limited or cooling down."""


def to_strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Adapt a pydantic JSON schema to strict structured-output rules.

    Strict mode needs every property in `required` and
    `additionalProperties: false` on every object. Optional fields keep their
    `anyOf [..., null]` form, so "required" still allows null. Defaults are
    removed because strict mode does not accept them.
    """

    schema = copy.deepcopy(schema)

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            node.pop("default", None)
            if node.get("type") == "object" and "properties" in node:
                node["required"] = list(node["properties"].keys())
                node["additionalProperties"] = False
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(schema)
    return schema


@dataclass(frozen=True)
class ModelSlot:
    """One configured chat model and how to ask it for JSON."""

    provider: LLMProvider
    model: BaseChatModel
    json_mode: JsonMode
    label: str = ""  # e.g. "groq#2:openai/gpt-oss-20b"; never contains the key


def build_chat_model(
    *,
    api_key: str,
    model: str,
    base_url: str | None,
    temperature: float = 0.0,
    timeout_s: float = 60.0,
    max_retries: int = 3,
    http_client: httpx.Client | None = None,
    reasoning_effort: str | None = None,
) -> ChatOpenAI:
    kwargs: dict[str, Any] = dict(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        timeout=timeout_s,
        max_retries=max_retries,  # retries 429 and 5xx with backoff
    )
    if http_client is not None:
        kwargs["http_client"] = http_client
    if reasoning_effort:
        kwargs["reasoning_effort"] = reasoning_effort
    return ChatOpenAI(**kwargs)


def _messages(system: str, user: str) -> list[BaseMessage]:
    return [SystemMessage(content=system), HumanMessage(content=user)]


def _is_rate_limit(exc: BaseException) -> bool:
    if getattr(exc, "status_code", None) == 429:
        return True
    return "RateLimit" in type(exc).__name__ or "429" in str(exc)[:200]


def _is_daily_limit(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(k in text for k in ("per day", "tokens per day", "requests per day", "tpd", "rpd",
                                    "daily", "quota"))


class LLMService:
    """Calls the configured models in order, skipping any that are cooling down.

    Each slot is one (provider, API key, model). When a slot is rate limited it
    is paused (short cooldown for per-minute limits, long for daily limits) and
    the next slot is tried, so extra keys add capacity without wasted calls.
    """

    def __init__(
        self,
        slots: Sequence[ModelSlot],
        *,
        validation_retries: int = 2,
        cooldown_s: float = 120.0,
        daily_cooldown_s: float = 3600.0,
        clock=time.monotonic,
    ) -> None:
        if not slots:
            raise LLMConfigError("At least one LLM provider must be configured.")
        self.slots = tuple(slots)
        self.validation_retries = validation_retries
        self.cooldown_s = cooldown_s
        self.daily_cooldown_s = daily_cooldown_s
        self._clock = clock
        self._paused_until: dict[int, float] = {}

    # ---- Slot rotation -----------------------------------------------------------

    def available_slots(self) -> list[int]:
        now = self._clock()
        return [i for i in range(len(self.slots)) if self._paused_until.get(i, 0.0) <= now]

    def _pause(self, index: int, exc: BaseException) -> None:
        seconds = self.daily_cooldown_s if _is_daily_limit(exc) else self.cooldown_s
        self._paused_until[index] = self._clock() + seconds
        logger.warning("LLM slot %s rate limited; paused %.0f s", self.slots[index].label, seconds)

    def _call_rotating(self, call):
        """Run `call(slot)` on each available slot until one succeeds."""

        last: BaseException | None = None
        for index in self.available_slots():
            slot = self.slots[index]
            try:
                return call(slot)
            except _PARSE_ERRORS as exc:
                last = exc  # this model could not produce valid output; try the next
            except Exception as exc:  # noqa: BLE001  (provider errors vary by SDK)
                last = exc
                if _is_rate_limit(exc):
                    self._pause(index, exc)
                else:
                    logger.warning("LLM slot %s failed: %s", slot.label, type(exc).__name__)
        if last is None:
            raise LLMRateLimitedError("All LLM slots are cooling down after rate limits.")
        if isinstance(last, _PARSE_ERRORS):
            raise LLMError(f"Structured output failed validation: {last}") from last
        if _is_rate_limit(last):
            raise LLMRateLimitedError(f"All LLM slots are rate limited: {type(last).__name__}") from last
        raise LLMError(f"All LLM slots failed: {type(last).__name__}: {last}") from last

    @classmethod
    def from_settings(
        cls, settings: Settings, *, http_client: httpx.Client | None = None
    ) -> LLMService:
        slots: list[ModelSlot] = []
        order = [settings.llm_provider] + [
            p for p in settings.llm_fallback_providers if p is not settings.llm_provider
        ]
        for provider in order:
            keys = settings.api_keys_for(provider)
            if not keys:
                if provider is settings.llm_provider:
                    raise LLMConfigError(
                        f"No API key for the primary LLM provider '{provider.value}'. "
                        "Set NIGEHBAN_LLM_API_KEY or the provider's key."
                    )
                logger.info("Skipping LLM fallback '%s': no API key.", provider.value)
                continue
            json_mode = (
                settings.llm_json_mode if provider is settings.llm_provider else JsonMode.JSON_SCHEMA
            )
            # Groq rate limits are per model, so an extra Groq model adds free capacity.
            model_names = [settings.model_for(provider)]
            if provider is LLMProvider.GROQ:
                model_names += [m for m in settings.groq_extra_models if m not in model_names]
            for key_number, key in enumerate(keys, start=1):
                for model_name in model_names:
                    # Reasoning models on Groq (gpt-oss) spend tokens on hidden reasoning;
                    # "low" keeps extraction calls inside the free per-minute token limit.
                    effort = (
                        settings.llm_reasoning_effort
                        if provider is LLMProvider.GROQ and "gpt-oss" in model_name
                        else None
                    )
                    model = build_chat_model(
                        api_key=key.get_secret_value(),
                        model=model_name,
                        base_url=settings.base_url_for(provider),
                        timeout_s=settings.llm_timeout_s,
                        max_retries=settings.llm_max_retries,
                        http_client=http_client,
                        reasoning_effort=effort,
                    )
                    label = f"{provider.value}#{key_number}:{model_name}"  # never the key itself
                    slots.append(ModelSlot(provider, model, json_mode, label))
        return cls(
            slots,
            validation_retries=settings.llm_validation_retries,
            cooldown_s=settings.llm_cooldown_s,
            daily_cooldown_s=settings.llm_daily_cooldown_s,
        )

    @property
    def providers(self) -> tuple[LLMProvider, ...]:
        return tuple(slot.provider for slot in self.slots)

    # ---- Runnables (for LangGraph and chains) -------------------------------

    @property
    def chat(self) -> Runnable:
        """Chat model with fallbacks; accepts a list of messages."""

        primary, *rest = [slot.model for slot in self.slots]
        return primary.with_fallbacks(rest) if rest else primary

    def structured(self, output_model: type[T]) -> Runnable:
        """Runnable: {"system": str, "user": str} -> validated `output_model`."""

        chains = [self._structured_chain(slot, output_model) for slot in self.slots]
        primary, *rest = chains
        return primary.with_fallbacks(rest) if rest else primary

    def _structured_chain(self, slot: ModelSlot, output_model: type[T]) -> Runnable:
        schema = output_model.model_json_schema()
        validate = RunnableLambda(lambda data: output_model.model_validate(data))

        if slot.json_mode is JsonMode.JSON_SCHEMA:
            strict_schema = to_strict_schema(schema)
            strict_schema.setdefault("title", output_model.__name__)
            model_part = slot.model.with_structured_output(
                strict_schema, method="json_schema", strict=True
            )
            build = RunnableLambda(lambda x: _messages(x["system"], x["user"]))
        else:
            hint = (
                "\n\nReply with one JSON object only, matching this JSON schema:\n"
                + json.dumps(schema, ensure_ascii=False)
            )
            model_part = (
                slot.model.bind(response_format={"type": "json_object"})
                | StrOutputParser()
                | RunnableLambda(json.loads)
            )
            build = RunnableLambda(lambda x: _messages(x["system"] + hint, x["user"]))

        chain = build | model_part | validate
        return chain.with_retry(
            retry_if_exception_type=_PARSE_ERRORS,
            stop_after_attempt=self.validation_retries + 1,
            wait_exponential_jitter=False,
        )

    # ---- Convenience calls ----------------------------------------------------

    def complete_text(self, system: str, user: str) -> str:
        def call(slot: ModelSlot) -> str:
            message = slot.model.invoke(_messages(system, user))
            content = message.content if isinstance(message.content, str) else str(message.content)
            if not content.strip():
                raise ValueError("The model returned an empty response.")
            return content

        return self._call_rotating(call)

    def complete_structured(self, system: str, user: str, output_model: type[T]) -> T:
        payload = {"system": system, "user": user}
        return self._call_rotating(
            lambda slot: self._structured_chain(slot, output_model).invoke(payload)
        )
