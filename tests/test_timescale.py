from shared.timescale import get_time_scale, recovery_checks, scale_seconds


def test_default_scale_is_one():
    assert get_time_scale({}) == 1


def test_parse_scale():
    assert get_time_scale({"TIME_SCALE": "45"}) == 45
    assert get_time_scale({"TIME_SCALE": "0"}) == 1
    assert get_time_scale({"TIME_SCALE": "nonsense"}) == 1


def test_fifteen_minute_grace_becomes_twenty_seconds_at_45x():
    assert scale_seconds(900, 45) == 20


def test_scale_one_is_identity():
    assert scale_seconds(600, 1) == 600


def test_minimum_is_enforced():
    assert scale_seconds(60, 45, minimum=5) == 5
    assert scale_seconds(10, 1000) == 1


def test_matches_state_machine_formulas():
    # Same as the JSONata in the Init state:
    #   ackTimeout = max(5, floor(600/45)), recheck = max(3, floor(300/45)), checks = ceil(3600/300)
    assert scale_seconds(600, 45, minimum=5) == 13
    assert scale_seconds(300, 45, minimum=3) == 6
    assert recovery_checks(3600, 300) == 12
