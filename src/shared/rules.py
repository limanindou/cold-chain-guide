"""Temperature rule evaluation. Pure functions, no AWS dependencies (unit-tested)."""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional, Sequence, Tuple


def _num(value) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def in_range(temp, min_c, max_c) -> bool:
    """True when `temp` is inside the safe range.

    Either bound may be None: a profile can be max-only (plasma freezer, <= -25 °C),
    min-only, or both. Bounds are inclusive.
    """
    t = float(temp)
    lo, hi = _num(min_c), _num(max_c)
    if lo is not None and t < lo:
        return False
    if hi is not None and t > hi:
        return False
    return True


def excursion_direction(temp, min_c, max_c) -> Optional[str]:
    """'HIGH' if too warm, 'LOW' if too cold, None if in range."""
    t = float(temp)
    lo, hi = _num(min_c), _num(max_c)
    if hi is not None and t > hi:
        return "HIGH"
    if lo is not None and t < lo:
        return "LOW"
    return None


def describe_range(min_c, max_c) -> str:
    lo, hi = _num(min_c), _num(max_c)
    if lo is not None and hi is not None:
        return f"{lo:g} to {hi:g} °C"
    if hi is not None:
        return f"≤ {hi:g} °C"
    if lo is not None:
        return f"≥ {lo:g} °C"
    return "any temperature"


def out_of_range_seconds(
    readings: Sequence[Tuple[datetime, float]],
    min_c,
    max_c,
    end: Optional[datetime] = None,
) -> float:
    """Total seconds spent out of range.

    `readings` is a time-ordered list of (timestamp, tempC). Each reading is assumed to
    hold until the next one; the last reading holds until `end` (if given).
    """
    total = 0.0
    for i, (ts, temp) in enumerate(readings):
        if in_range(temp, min_c, max_c):
            continue
        if i + 1 < len(readings):
            nxt = readings[i + 1][0]
        elif end is not None:
            nxt = end
        else:
            continue
        total += max(0.0, (nxt - ts).total_seconds())
    return total


def min_max(temps: Iterable[float]) -> Tuple[Optional[float], Optional[float]]:
    values = [float(t) for t in temps]
    if not values:
        return None, None
    return min(values), max(values)
