import os

import pytest

# Tests never read the developer's real .env values for these.
os.environ.setdefault("NIGEHBAN_ENVIRONMENT", "testing")


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from backend.app.config.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
