"""Application settings, loaded from environment variables and `.env`.

Every variable uses the `NIGEHBAN_` prefix, for example `NIGEHBAN_LLM_API_KEY`.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
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
        "gemini-2.5-flash",
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

    # LLM
    llm_provider: LLMProvider = LLMProvider.GROQ
    llm_api_key: SecretStr | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_json_mode: JsonMode = JsonMode.JSON_SCHEMA
    llm_timeout_s: float = Field(default=60.0, gt=0)
    llm_max_retries: int = Field(default=3, ge=0)
    llm_validation_retries: int = Field(default=2, ge=0)

    # Privacy: contact details are encrypted at rest and looked up by keyed hash.
    contact_encryption_key: SecretStr | None = None
    contact_hash_key: SecretStr | None = None

    # Authority board
    board_password: SecretStr | None = None

    # Alert policy (tuned in M5; configurable)
    alert_false_alarm_target_per_season: float = Field(default=2.5, ge=0)

    # PDMA scraper
    pdma_base_url: str = "https://rms.pdma.gov.pk/ViewDSR.aspx"
    pdma_request_interval_s: float = Field(default=2.0, ge=1.0)
    pdma_user_agent: str = "nigehban-research/0.1 (non-commercial flood research)"

    @property
    def resolved_llm_base_url(self) -> str | None:
        return self.llm_base_url or PROVIDER_DEFAULTS[self.llm_provider][0]

    @property
    def resolved_llm_model(self) -> str:
        model = self.llm_model or PROVIDER_DEFAULTS[self.llm_provider][1]
        if not model:
            raise ValueError("NIGEHBAN_LLM_MODEL must be set for the custom provider.")
        return model

    @property
    def raw_pdma_dir(self) -> Path:
        return self.data_dir / "raw" / "pdma_dsr"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
