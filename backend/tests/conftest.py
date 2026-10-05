import os

import pytest

from backend.security import _buckets

# Test runs must not populate the configured production database.
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/test.db")


@pytest.fixture(autouse=True)
def clear_limits():
    _buckets.clear()
    yield
    _buckets.clear()
