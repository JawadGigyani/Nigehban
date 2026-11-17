import pytest

from backend.app.config import region
from backend.app.config.settings import LLMProvider, Settings


def test_env_prefix_and_provider_defaults(monkeypatch):
    monkeypatch.setenv("NIGEHBAN_LLM_PROVIDER", "groq")
    monkeypatch.delenv("NIGEHBAN_LLM_MODEL", raising=False)
    monkeypatch.delenv("NIGEHBAN_LLM_BASE_URL", raising=False)
    s = Settings(_env_file=None)
    assert s.llm_provider is LLMProvider.GROQ
    assert s.resolved_llm_base_url == "https://api.groq.com/openai/v1"
    assert s.resolved_llm_model == "openai/gpt-oss-120b"


def test_overrides(monkeypatch):
    monkeypatch.setenv("NIGEHBAN_LLM_PROVIDER", "custom")
    monkeypatch.setenv("NIGEHBAN_LLM_BASE_URL", "http://localhost:1234/v1")
    monkeypatch.setenv("NIGEHBAN_LLM_MODEL", "local-model")
    s = Settings(_env_file=None)
    assert s.resolved_llm_base_url == "http://localhost:1234/v1"
    assert s.resolved_llm_model == "local-model"


def test_custom_provider_requires_model(monkeypatch):
    monkeypatch.setenv("NIGEHBAN_LLM_PROVIDER", "custom")
    monkeypatch.delenv("NIGEHBAN_LLM_MODEL", raising=False)
    with pytest.raises(ValueError):
        _ = Settings(_env_file=None).resolved_llm_model


def test_pdma_interval_cannot_be_below_one_second(monkeypatch):
    monkeypatch.setenv("NIGEHBAN_PDMA_REQUEST_INTERVAL_S", "0.2")
    with pytest.raises(ValueError):
        Settings(_env_file=None)


def test_region_candidates_and_ardc():
    slugs = [d.slug for d in region.CANDIDATE_DISTRICTS]
    assert len(slugs) == len(set(slugs))
    assert region.district_by_slug("bajaur").is_ardc
    assert not region.district_by_slug("swat").is_ardc
    assert region.district_by_slug("upper_chitral").cod_name == "Chitral Upper"
    assert region.active_districts() == region.CANDIDATE_DISTRICTS  # pilot not chosen yet


def test_bbox_covers_known_places():
    box = region.CANDIDATE_BBOX
    for lat, lon in [(34.77, 72.36), (34.50, 72.48), (35.50, 72.58), (34.73, 71.52), (34.33, 73.20)]:
        assert box.contains(lat, lon)  # Mingora, Buner, Kalam, Khar, Mansehra
    assert not box.contains(34.01, 71.58)  # Peshawar


def test_make_tehsil_id():
    assert region.make_tehsil_id("buner", "daggar") == "buner__daggar"
