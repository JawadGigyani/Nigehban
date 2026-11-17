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


def build_chat_model(
    *,
    api_key: str,
    model: str,
    base_url: str | None,
    temperature: float = 0.0,
    timeout_s: float = 60.0,
    max_retries: int = 3,
    http_client: httpx.Client | None = None,
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
    return ChatOpenAI(**kwargs)


def _messages(system: str, user: str) -> list[BaseMessage]:
    return [SystemMessage(content=system), HumanMessage(content=user)]


class LLMService:
    def __init__(self, slots: Sequence[ModelSlot], *, validation_retries: int = 2) -> None:
        if not slots:
            raise LLMConfigError("At least one LLM provider must be configured.")
        self.slots = tuple(slots)
        self.validation_retries = validation_retries

    @classmethod
    def from_settings(
        cls, settings: Settings, *, http_client: httpx.Client | None = None
    ) -> LLMService:
        slots: list[ModelSlot] = []
        order = [settings.llm_provider] + [
            p for p in settings.llm_fallback_providers if p is not settings.llm_provider
        ]
        for provider in order:
            key = settings.api_key_for(provider)
            if key is None:
                if provider is settings.llm_provider:
                    raise LLMConfigError(
                        f"No API key for the primary LLM provider '{provider.value}'. "
                        "Set NIGEHBAN_LLM_API_KEY or the provider's key."
                    )
                logger.info("Skipping LLM fallback '%s': no API key.", provider.value)
                continue
            model = build_chat_model(
                api_key=key.get_secret_value(),
                model=settings.model_for(provider),
                base_url=settings.base_url_for(provider),
                timeout_s=settings.llm_timeout_s,
                max_retries=settings.llm_max_retries,
                http_client=http_client,
            )
            json_mode = (
                settings.llm_json_mode if provider is settings.llm_provider else JsonMode.JSON_SCHEMA
            )
            slots.append(ModelSlot(provider, model, json_mode))
        return cls(slots, validation_retries=settings.llm_validation_retries)

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
        message = self.chat.invoke(_messages(system, user))
        content = message.content if isinstance(message.content, str) else str(message.content)
        if not content.strip():
            raise LLMError("The model returned an empty response.")
        return content

    def complete_structured(self, system: str, user: str, output_model: type[T]) -> T:
        try:
            return self.structured(output_model).invoke({"system": system, "user": user})
        except _PARSE_ERRORS as exc:
            raise LLMError(f"Structured output failed validation: {exc}") from exc
