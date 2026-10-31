import importlib.util
import io
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / ".github" / "scripts" / "assert_lifecycle_close_needed.py"
SPEC = importlib.util.spec_from_file_location("assert_lifecycle_close_needed", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
CLOSE_GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLOSE_GUARD)


def _opening(run_id: int, *, status: str = "completed") -> dict[str, object]:
    return {"id": run_id, "status": status}


def test_duplicate_nonmutating_openings_close_ledger_without_teardown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CLOSE_GUARD, "_opening_mutation_started", lambda *_args: False)

    close_needed, teardown_needed, reason = CLOSE_GUARD._opening_close_decision(
        [_opening(101), _opening(102)], "owner/repo", "token"
    )

    assert close_needed is True
    assert teardown_needed is False
    assert "without starting a mutating lifecycle step" in reason


def test_only_mutating_opening_requires_teardown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CLOSE_GUARD, "_opening_mutation_started", lambda _repo, run_id, _token: run_id == 102)

    close_needed, teardown_needed, _reason = CLOSE_GUARD._opening_close_decision(
        [_opening(101), _opening(102)], "owner/repo", "token"
    )

    assert close_needed is True
    assert teardown_needed is True


def test_multiple_mutating_openings_still_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CLOSE_GUARD, "_opening_mutation_started", lambda *_args: True)

    with pytest.raises(ValueError, match="Multiple mutating opening runs"):
        CLOSE_GUARD._opening_close_decision([_opening(101), _opening(102)], "owner/repo", "token")


def test_duplicate_openings_with_skipped_mutation_markers_close_without_teardown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "total_count": 1,
        "jobs": [
            {
                "name": "open",
                "conclusion": "failure",
                "steps": [
                    {
                        "name": CLOSE_GUARD.FIRST_MUTATION_MARKER,
                        "status": "completed",
                        "conclusion": "skipped",
                        "started_at": "2026-10-31T18:30:20Z",
                    }
                ],
            }
        ],
    }
    responses = iter(
        io.BytesIO(json.dumps(payload).encode("utf-8"))
        for _ in range(2)
    )
    monkeypatch.setattr(
        CLOSE_GUARD,
        "urlopen",
        lambda *_args, **_kwargs: next(responses),
    )

    close_needed, teardown_needed, reason = CLOSE_GUARD._opening_close_decision(
        [_opening(101), _opening(102)], "owner/repo", "token"
    )

    assert close_needed is True
    assert teardown_needed is False
    assert "without starting a mutating lifecycle step" in reason


def test_failed_mutation_marker_with_timestamp_still_requires_teardown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "total_count": 1,
        "jobs": [
            {
                "name": "open",
                "conclusion": "failure",
                "steps": [
                    {
                        "name": CLOSE_GUARD.FIRST_MUTATION_MARKER,
                        "status": "completed",
                        "conclusion": "failure",
                        "started_at": "2026-10-31T18:30:20Z",
                    }
                ],
            }
        ],
    }
    monkeypatch.setattr(
        CLOSE_GUARD,
        "urlopen",
        lambda *_args, **_kwargs: io.BytesIO(json.dumps(payload).encode("utf-8")),
    )

    assert CLOSE_GUARD._opening_mutation_started("owner/repo", 101, "token") is True


def test_active_opening_fails_closed_before_teardown_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CLOSE_GUARD, "_opening_mutation_started", lambda *_args: False)

    with pytest.raises(ValueError, match="still active"):
        CLOSE_GUARD._opening_close_decision([_opening(101, status="in_progress")], "owner/repo", "token")


def test_no_matching_opening_keeps_current_no_close_decision() -> None:
    assert CLOSE_GUARD._opening_close_decision([], "owner/repo", "token") == (
        False,
        False,
        "No matching opening run exists for this session; no infrastructure was changed.",
    )
