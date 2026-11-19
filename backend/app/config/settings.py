"""Application settings, loaded from environment variables and `.env`.

Every variable uses the `NIGEHBAN_` prefix, for example `NIGEHBAN_LLM_API_KEY`.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_project_root(source_file: Path) -> Path:
    for directory in source_file.resolve().parents:
        if (directory / "pyproject.toml").is_file():
            return directory
    raise RuntimeError("Unable to locate the project root from the settings module.")


PROJECT_ROOT = _find_project_root(Path(__file__))


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class LLMProvider(str, Enum):
    GROQ = "groq"
    GEMINI = "gemini"
    OPENAI = "openai"
    CUSTOM = "custom"


class JsonMode(str, Enum):
    """How the LLM adapter asks for structured output.

    `json_schema` sends the schema to the provider (strict where supported).
    `json_object` only asks for valid JSON and puts the schema in the prompt;
    use it for models without schema support.
    """

    JSON_SCHEMA = "json_schema"
    JSON_OBJECT = "json_object"


# OpenAI-compatible endpoints and a sensible default model per provider.
PROVIDER_DEFAULTS: dict[LLMProvider, tuple[str | None, str]] = {
    LLMProvider.GROQ: ("https://api.groq.com/openai/v1", "openai/gpt-oss-120b"),
    LLMProvider.GEMINI: (
        "https://generativelanguage.googleapis.com/v1beta/openai/",
        "gemini-3.5-flash-lite",
    ),
    LLMProvider.OPENAI: (None, "gpt-4.1-mini"),
    LLMProvider.CUSTOM: (None, ""),
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="NIGEHBAN_",
        extra="ignore",
    )

    app_name: str = "Nigehban"
    version: str = "0.1.0"
    environment: Environment = Environment.DEVELOPMENT
    log_level: str = "INFO"
    cors_allow_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    # Paths
    data_dir: Path = PROJECT_ROOT / "data"

    # Database: SQLite locally, Postgres (Supabase) when deployed.
    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'data' / 'nigehban.db').as_posix()}"

    # LLM (LangChain). The primary provider is tried first; on errors or rate
    # limits the fallback providers are tried in order.
    llm_provider: LLMProvider = LLMProvider.GROQ
    llm_fallback_providers: list[LLMProvider] = Field(default=[LLMProvider.GEMINI])
    llm_api_key: SecretStr | None = None  # key for the primary provider
    llm_base_url: str | None = None  # primary provider only
    llm_model: str | None = None  # primary provider only
    llm_json_mode: JsonMode = JsonMode.JSON_SCHEMA
    llm_timeout_s: float = Field(default=60.0, gt=0)
    llm_max_retries: int = Field(default=3, ge=0)
    llm_validation_retries: int = Field(default=2, ge=0)
    llm_reasoning_effort: str | None = "low"  # for reasoning models (Groq gpt-oss)

    # Provider keys. The standard unprefixed names also work.
    groq_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("NIGEHBAN_GROQ_API_KEY", "GROQ_API_KEY")
    )
    gemini_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("NIGEHBAN_GEMINI_API_KEY", "GEMINI_API_KEY"),
    )
    gemini_model: str | None = None
    # Extra Groq models tried after the primary one (each has its own free quota).
    groq_extra_models: list[str] = Field(default=["openai/gpt-oss-20b"])
    openai_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("NIGEHBAN_OPENAI_API_KEY", "OPENAI_API_KEY")
    )
    # More keys per provider, comma-separated, used after the main key when it is
    # rate limited. Example: NIGEHBAN_GROQ_API_KEYS=gsk_aaa,gsk_bbb
    groq_api_keys: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("NIGEHBAN_GROQ_API_KEYS", "GROQ_API_KEYS")
    )
    gemini_api_keys: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("NIGEHBAN_GEMINI_API_KEYS", "GEMINI_API_KEYS")
    )
    openai_api_keys: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("NIGEHBAN_OPENAI_API_KEYS", "OPENAI_API_KEYS")
    )
    # How long a rate-limited key/model is skipped before it is tried again.
    llm_cooldown_s: float = Field(default=120.0, ge=0)
    llm_daily_cooldown_s: float = Field(default=3600.0, ge=0)

    # Privacy: contact details are encrypted at rest and looked up by keyed hash.
    contact_encryption_key: SecretStr | None = None
    contact_hash_key: SecretStr | None = None

    # Authority board
    board_password: SecretStr | None = None

    # Alert policy (tuned in M5; configurable)
    alert_false_alarm_target_per_season: float = Field(default=2.5, ge=0)
    # River flag: a tehsil is flagged when a river point serving it is forecast at or
    # above this return period (years) of GloFAS discharge. Tuned in M7.
    river_flag_return_period: int = Field(default=5, ge=2, le=20)
    # Alert rules: alert at this level or above, for lead days up to alert_max_lead.
    alert_min_level: str = "high"
    alert_max_lead_days: int = Field(default=2, ge=0, le=3)
    # Protects POST /internal/run-cycle (required in production; the cron job sends it).
    internal_token: SecretStr | None = None
    # Web push (VAPID). Generate with: python -m backend.app.alerts.channels --vapid
    vapid_public_key: str | None = None
    vapid_private_key: SecretStr | None = None
    vapid_subject: str = "mailto:alerts@nigehban.invalid"
    # Telegram: private development channel only (Telegram is blocked in Pakistan).
    telegram_bot_token: SecretStr | None = None
    # OpenRouteService (free key) for routes to safety; without it the built-in OSM router is used.
    ors_api_key: SecretStr | None = None

    # Urdu voice alerts (ElevenLabs). Only eleven_v3 / eleven_v4 support Urdu.
    elevenlabs_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("NIGEHBAN_ELEVENLABS_API_KEY", "ELEVENLABS_API_KEY"))
    elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"  # a premade multilingual voice (free tier can use premade voices)
    elevenlabs_model: str = "eleven_v3"
    voice_max_chars: int = Field(default=600, ge=50, le=5000)

    # SMS through the free open-source "SMS Gateway for Android" app (a phone + SIM sends the SMS).
    # Cloud mode: https://api.sms-gate.app/3rdparty/v1 ; local mode: http://<phone-ip>:8080
    sms_gateway_url: str = "https://api.sms-gate.app/3rdparty/v1"
    sms_gateway_username: str | None = None
    sms_gateway_password: SecretStr | None = None

    # WhatsApp Cloud API (Meta). Free only for a test number and up to 5 verified recipients.
    whatsapp_token: SecretStr | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_template: str | None = None  # approved template with one body parameter; else plain text

    # Rate limits for public endpoints (requests per minute per client IP).
    rate_limit_chat_per_min: int = 8
    rate_limit_default_per_min: int = 60
    rate_limit_chat_per_day_global: int = 1500  # protects the free LLM quota

    # PDMA scraper
    pdma_base_url: str = "https://rms.pdma.gov.pk/ViewDSR.aspx"
    pdma_request_interval_s: float = Field(default=2.0, ge=1.0)
    pdma_user_agent: str = "nigehban-research/0.1 (non-commercial flood research)"

    @property
    def resolved_llm_base_url(self) -> str | None:
        return self.base_url_for(self.llm_provider)

    @property
    def resolved_llm_model(self) -> str:
        return self.model_for(self.llm_provider)

    def base_url_for(self, provider: LLMProvider) -> str | None:
        if provider is self.llm_provider and self.llm_base_url:
            return self.llm_base_url
        return PROVIDER_DEFAULTS[provider][0]

    def model_for(self, provider: LLMProvider) -> str:
        if provider is self.llm_provider and self.llm_model:
            return self.llm_model
        if provider is LLMProvider.GEMINI and self.gemini_model:
            return self.gemini_model
        model = PROVIDER_DEFAULTS[provider][1]
        if not model:
            raise ValueError("NIGEHBAN_LLM_MODEL must be set for the custom provider.")
        return model

    def api_key_for(self, provider: LLMProvider) -> SecretStr | None:
        specific = {
            LLMProvider.GROQ: self.groq_api_key,
            LLMProvider.GEMINI: self.gemini_api_key,
            LLMProvider.OPENAI: self.openai_api_key,
            LLMProvider.CUSTOM: None,
        }[provider]
        if specific is not None:
            return specific
        return self.llm_api_key if provider is self.llm_provider else None

    def api_keys_for(self, provider: LLMProvider) -> list[SecretStr]:
        """Main key first, then the extra keys; duplicates and blanks removed."""

        extra = {
            LLMProvider.GROQ: self.groq_api_keys,
            LLMProvider.GEMINI: self.gemini_api_keys,
            LLMProvider.OPENAI: self.openai_api_keys,
            LLMProvider.CUSTOM: None,
        }[provider]
        values: list[str] = []
        main = self.api_key_for(provider)
        if main is not None:
            values.append(main.get_secret_value().strip())
        if extra is not None:
            values += [k.strip() for k in extra.get_secret_value().split(",")]
        unique = list(dict.fromkeys(v for v in values if v))
        return [SecretStr(v) for v in unique]

    @property
    def raw_pdma_dir(self) -> Path:
        return self.data_dir / "raw" / "pdma_dsr"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
