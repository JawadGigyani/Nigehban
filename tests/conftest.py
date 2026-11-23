import os

import pytest

# Tests never read the developer's real .env values for these.
os.environ.setdefault("NIGEHBAN_ENVIRONMENT", "testing")


def pytest_collection_modifyitems(config, items):
    """Tests marked `live` call real services (Open-Meteo, LLMs); they run only when asked.

    CI and fresh clones run offline; opt in with NIGEHBAN_RUN_LIVE=1.
    """

    if os.getenv("NIGEHBAN_RUN_LIVE") == "1":
        return
    skip = pytest.mark.skip(reason="live external service (set NIGEHBAN_RUN_LIVE=1)")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from backend.app.config.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
