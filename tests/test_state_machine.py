"""Structural checks for statemachine/incident.asl.json (no AWS needed)."""
import json
import pathlib

ASL = json.loads((pathlib.Path(__file__).resolve().parents[1] / "statemachine" / "incident.asl.json")
                 .read_text("utf-8"))
STATES = ASL["States"]


def _targets(state):
    out = [state.get("Next"), state.get("Default")]
    out += [c["Next"] for c in state.get("Choices", [])]
    out += [c["Next"] for c in state.get("Catch", [])]
    return [t for t in out if t]


def test_jsonata_and_start():
    assert ASL["QueryLanguage"] == "JSONata"
    assert ASL["StartAt"] in STATES


def test_every_transition_exists_and_every_state_reachable():
    seen, todo = set(), [ASL["StartAt"]]
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        for t in _targets(STATES[name]):
            assert t in STATES, f"{name} -> {t}"
            todo.append(t)
    assert seen == set(STATES), set(STATES) - seen


def test_grace_wait_then_check():
    assert STATES["WaitGrace"]["Type"] == "Wait"
    assert STATES["WaitGrace"]["Next"] == "CheckRecovered"


def test_silence_becomes_escalation():
    notify = STATES["NotifyResponder"]
    assert notify["Resource"].endswith("lambda:invoke.waitForTaskToken")
    assert "TimeoutSeconds" in notify
    caught = {e for c in notify["Catch"] for e in c["ErrorEquals"]}
    assert {"States.Timeout", "NeedHelp"} <= caught
    # NeedHelp must never be retried (that would re-alert the same person instead of escalating)
    for r in notify.get("Retry", []):
        assert "States.TaskFailed" not in r["ErrorEquals"] and "States.ALL" not in r["ErrorEquals"]


def test_all_tasks_have_retry():
    for name, s in STATES.items():
        if s["Type"] == "Task":
            assert s.get("Retry"), name


def test_all_paths_end_in_evidence():
    for name in ("CloseRecovered", "MarkResolved", "NotifyEveryone"):
        assert STATES[name]["Next"] == "BuildEvidence"
