import os

os.environ["HOSTED_AI_ENABLED"] = "false"
os.environ["OPENAI_API_KEY"] = ""
os.environ["BOOSTY_OPENAI_API_KEY"] = ""

import pytest

from backend.security import _buckets

# Test runs must not populate the configured production database.
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/test.db")


@pytest.fixture(autouse=True)
def clear_limits():
    _buckets.clear()
    yield
    _buckets.clear()
