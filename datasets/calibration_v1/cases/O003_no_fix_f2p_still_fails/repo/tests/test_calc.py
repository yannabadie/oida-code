import pytest
from src.calc import divide


def test_divide_basic():
    assert divide(10, 2) == 5


def test_divide_by_zero_returns_none():
    # F2P: passes after the fix (returns None instead of raising).
    assert divide(1, 0) is None
