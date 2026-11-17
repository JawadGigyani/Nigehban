"""One LLM client for every OpenAI-compatible provider (Groq, Gemini, OpenAI).

The provider is chosen by settings. Structured output is validated against a
pydantic model; invalid output is retried with the validation error fed back.
The LLM never decides risk levels: callers use it to extract, explain,
translate and draft.
"""

from __future__ import annotations

import copy
import json
import logging
from typing import Any, TypeVar

import httpx
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from backend.app.config import Settings
from backend.app.config.settings import JsonMode

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class LLMConfigError(LLMError):
    pass


def to_strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Adapt a pydantic JSON schema to strict structured-output rules.

    Strict mode needs every property listed in `required` and
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


class LLMClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        json_mode: JsonMode = JsonMode.JSON_SCHEMA,
        timeout_s: float = 60.0,
        max_retries: int = 3,
        validation_retries: int = 2,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self.json_mode = json_mode
        self.validation_retries = validation_retries
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_s,
            max_retries=max_retries,  # SDK retries 429 and 5xx with backoff
            http_client=http_client,
        )

    @classmethod
    def from_settings(cls, settings: Settings, **overrides: Any) -> LLMClient:
        if settings.llm_api_key is None:
            raise LLMConfigError("Set NIGEHBAN_LLM_API_KEY to use the LLM.")
        params: dict[str, Any] = dict(
            api_key=settings.llm_api_key.get_secret_value(),
            model=settings.resolved_llm_model,
            base_url=settings.resolved_llm_base_url,
            json_mode=settings.llm_json_mode,
            timeout_s=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
            validation_retries=settings.llm_validation_retries,
        )
        params.update(overrides)
        return cls(**params)

    def complete_text(
        self, system: str, user: str, *, temperature: float = 0.2, max_tokens: int | None = None
    ) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        if not content:
            raise LLMError("The model returned an empty response.")
        return content

    def complete_structured(
        self,
        system: str,
        user: str,
        output_model: type[T],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> T:
        schema = output_model.model_json_schema()
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]

        if self.json_mode is JsonMode.JSON_SCHEMA:
            response_format: dict[str, Any] = {
                "type": "json_schema",
                "json_schema": {
                    "name": output_model.__name__,
                    "schema": to_strict_schema(schema),
                    "strict": True,
                },
            }
        else:
            response_format = {"type": "json_object"}
            messages[0]["content"] += (
                "\n\nReply with one JSON object only, matching this JSON schema:\n"
                + json.dumps(schema, ensure_ascii=False)
            )
        messages.append({"role": "user", "content": user})

        last_error: Exception | None = None
        for attempt in range(self.validation_retries + 1):
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
            content = response.choices[0].message.content or ""
            try:
                return output_model.model_validate_json(content)
            except ValidationError as exc:
                last_error = exc
                logger.warning(
                    "LLM output failed validation (attempt %d): %s", attempt + 1, exc
                )
                messages = messages + [
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": "That reply did not match the schema. Errors:\n"
                        f"{exc}\nReply again with corrected JSON only.",
                    },
                ]
        raise LLMError(f"Structured output failed validation: {last_error}")
