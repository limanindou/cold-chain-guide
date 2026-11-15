from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from shared import rules

T0 = datetime(2026, 11, 15, 2, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("temp,expected", [(2, True), (5, True), (8, True), (1.99, False), (8.01, False), (-3, False)])
def test_both_bounds_inclusive(temp, expected):
    assert rules.in_range(temp, 2, 8) is expected


@pytest.mark.parametrize("temp,expected", [(-40, True), (-25, True), (-24.9, False), (4, False)])
def test_max_only_plasma(temp, expected):
    assert rules.in_range(temp, None, -25) is expected


@pytest.mark.parametrize("temp,expected", [(30, True), (15, True), (14.5, False)])
def test_min_only(temp, expected):
    assert rules.in_range(temp, 15, None) is expected


def test_no_bounds_is_always_in_range():
    assert rules.in_range(99, None, None)


def test_accepts_decimal_and_strings_from_dynamodb():
    assert rules.in_range(Decimal("5.5"), Decimal("2"), Decimal("8"))
    assert not rules.in_range("9", "2", "8")


def test_direction():
    assert rules.excursion_direction(9, 2, 8) == "HIGH"
    assert rules.excursion_direction(1, 2, 8) == "LOW"
    assert rules.excursion_direction(5, 2, 8) is None
    assert rules.excursion_direction(-20, None, -25) == "HIGH"


def test_describe_range():
    assert rules.describe_range(2, 8) == "2 to 8 °C"
    assert rules.describe_range(None, -25) == "≤ -25 °C"
    assert rules.describe_range(15, None) == "≥ 15 °C"


def test_out_of_range_seconds_sums_out_intervals():
    readings = [(T0 + timedelta(seconds=s), t) for s, t in [(0, 5), (10, 9), (20, 10), (30, 7), (40, 9)]]
    # out 10->20 and 20->30 = 20 s; the last reading (9) is out and holds until end (+5 s)
    assert rules.out_of_range_seconds(readings, 2, 8, end=T0 + timedelta(seconds=45)) == 25
    assert rules.out_of_range_seconds(readings, 2, 8) == 20


def test_out_of_range_seconds_empty():
    assert rules.out_of_range_seconds([], 2, 8) == 0


def test_min_max():
    assert rules.min_max([3, 9.5, -1]) == (-1, 9.5)
    assert rules.min_max([]) == (None, None)
