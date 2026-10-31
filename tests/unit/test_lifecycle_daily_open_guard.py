import importlib.util
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / ".github" / "scripts" / "assert_daily_lifecycle_unique.py"
SPEC = importlib.util.spec_from_file_location("assert_daily_lifecycle_unique", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


CURRENT_RUN_ID = "999"
PRIOR_RUN_ID = 123
GUARD_STEP_NAME = "Reject a second opening run for the same HML date"
FIRST_MUTATION_STEP_NAME = "Configure the narrow lifecycle start role"


def _run(run_id: int, *, status: str = "completed", conclusion: str = "failure") -> dict[str, object]:
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "id": run_id,
        "display_title": "lifecycle:hml:open:test",
        "created_at": created_at,
        "status": status,
        "conclusion": conclusion,
    }


def _jobs_payload(
    *,
    open_status: str = "completed",
    open_conclusion: str = "skipped",
    steps: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    jobs = [{"name": "hml-gates", "status": "completed", "conclusion": "success", "steps": []}]
    if open_status != "missing":
        jobs.append(
            {
                "name": "open",
                "status": open_status,
                "conclusion": open_conclusion,
                "steps": steps or [],
            }
        )
    return {"total_count": len(jobs), "jobs": jobs}


def _set_github_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_RUN_ID", CURRENT_RUN_ID)
    monkeypatch.setenv("LIFECYCLE_CROSS_REPO_TOKEN", "unit-test-token")
    monkeypatch.setattr("sys.argv", [str(MODULE_PATH), "--stage", "hml"])


def _stub_api(monkeypatch: pytest.MonkeyPatch, responses: list[object]) -> list[str]:
    pending = iter(responses)
    requested_urls: list[str] = []

    def fake_urlopen(request: object, timeout: int) -> io.BytesIO:
        requested_urls.append(request.full_url)  # type: ignore[attr-defined]
        response = next(pending)
        if isinstance(response, Exception):
            raise response
        return io.BytesIO(json.dumps(response).encode("utf-8"))

    monkeypatch.setattr(GUARD, "urlopen", fake_urlopen)
    return requested_urls


def _listing(*runs: dict[str, object]) -> dict[str, object]:
    return {"total_count": len(runs), "workflow_runs": list(runs)}


def test_first_opening_run_is_allowed_without_prior_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_github_context(monkeypatch)
    current_run = _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="")
    requested_urls = _stub_api(monkeypatch, [_listing(current_run)])

    assert GUARD.main() == 0
    assert len(requested_urls) == 1


def test_preflight_failure_is_retryable_when_open_job_was_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_github_context(monkeypatch)
    requested_urls = _stub_api(
        monkeypatch,
        [
            _listing(_run(PRIOR_RUN_ID), _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="")),
            _jobs_payload(open_conclusion="skipped"),
        ],
    )

    assert GUARD.main() == 0
    assert requested_urls[1].endswith(f"/actions/runs/{PRIOR_RUN_ID}/jobs?per_page=100")


def test_duplicate_guard_failure_is_retryable_before_first_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_github_context(monkeypatch)
    steps = [
        {"name": GUARD_STEP_NAME, "status": "completed", "conclusion": "failure"},
        {"name": FIRST_MUTATION_STEP_NAME, "status": "completed", "conclusion": "skipped"},
    ]
    _stub_api(
        monkeypatch,
        [
            _listing(_run(PRIOR_RUN_ID), _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="")),
            _jobs_payload(open_conclusion="failure", steps=steps),
        ],
    )

    assert GUARD.main() == 0


def test_active_prior_opening_run_blocks_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_github_context(monkeypatch)
    requested_urls = _stub_api(
        monkeypatch,
        [_listing(_run(PRIOR_RUN_ID, status="in_progress", conclusion=""))],
    )

    assert GUARD.main() == 1
    assert len(requested_urls) == 1


def test_failure_after_first_mutation_started_blocks_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_github_context(monkeypatch)
    steps = [
        {"name": GUARD_STEP_NAME, "status": "completed", "conclusion": "success"},
        {"name": FIRST_MUTATION_STEP_NAME, "status": "completed", "conclusion": "success"},
    ]
    _stub_api(
        monkeypatch,
        [
            _listing(_run(PRIOR_RUN_ID), _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="")),
            _jobs_payload(open_conclusion="failure", steps=steps),
        ],
    )

    assert GUARD.main() == 1


def test_unknown_open_job_failure_blocks_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_github_context(monkeypatch)
    steps = [{"name": "Checkout", "status": "completed", "conclusion": "failure"}]
    _stub_api(
        monkeypatch,
        [
            _listing(_run(PRIOR_RUN_ID), _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="")),
            _jobs_payload(open_conclusion="failure", steps=steps),
        ],
    )

    assert GUARD.main() == 1


def test_github_jobs_api_failure_blocks_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_github_context(monkeypatch)
    requested_urls = _stub_api(
        monkeypatch,
        [
            _listing(_run(PRIOR_RUN_ID), _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="")),
            URLError("unavailable"),
        ],
    )

    assert GUARD.main() == 1
    assert len(requested_urls) == 2


def test_incomplete_github_jobs_listing_blocks_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_github_context(monkeypatch)
    _stub_api(
        monkeypatch,
        [
            _listing(_run(PRIOR_RUN_ID), _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="")),
            {"total_count": 2, "jobs": [{"name": "open", "status": "completed", "conclusion": "skipped"}]},
        ],
    )

    assert GUARD.main() == 1


def test_retry_contract_step_names_match_the_workflow() -> None:
    workflow = (ROOT / ".github" / "workflows" / "environment-start.yml").read_text(encoding="utf-8")

    guard_index = workflow.index(f"- name: {GUARD_STEP_NAME}")
    mutation_index = workflow.index(f"- name: {FIRST_MUTATION_STEP_NAME}")
    assert guard_index < mutation_index
