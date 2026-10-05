import pytest

from backend.security import _buckets


@pytest.fixture(autouse=True)
def clear_limits():
    _buckets.clear()
    yield
    _buckets.clear()
