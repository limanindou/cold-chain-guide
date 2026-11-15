"""Demo time scaling.

TIME_SCALE divides every grace / acknowledgement / recheck time so a 15-minute grace
period becomes 20 seconds at TIME_SCALE=45. The state machine applies the same formula
in JSONata ($max([min, $floor(seconds / scale)])); keep the two in sync.
"""
from __future__ import annotations

import math
import os
from typing import Mapping, Optional


def get_time_scale(env: Optional[Mapping[str, str]] = None) -> int:
    env = os.environ if env is None else env
    raw = env.get("TIME_SCALE", "1")
    try:
        value = int(float(raw))
    except (TypeError, ValueError):
        return 1
    return max(1, value)


def scale_seconds(seconds, time_scale: int, minimum: int = 1) -> int:
    """floor(seconds / time_scale), never below `minimum`."""
    return max(int(minimum), int(math.floor(float(seconds) / max(1, int(time_scale)))))


def recovery_checks(recovery_window_seconds, recheck_seconds) -> int:
    """How many post-acknowledgement checks fit in the recovery window (unscaled ratio)."""
    return max(1, int(math.ceil(float(recovery_window_seconds) / float(recheck_seconds))))
