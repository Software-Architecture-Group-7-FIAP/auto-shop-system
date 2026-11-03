import importlib.util
import io
import json
import tempfile
from datetime import datetime, timedelta, timezone
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
HML_AUTO_STOP_WAIT_JOB_NAME = "hml-auto-stop-wait"
SESSION_RECORD_STEP_NAME = "Record the trusted operator and authorize the selected HML session profile"
AUTH_PREFLIGHT_STEP_NAME = "Validate persistent customer auth Lambdas before opening session resources"
ALL_INPUTS_PREFLIGHT_STEP_NAME = "Validate all credentials, repositories, deploy gates, alerting, and cost evidence inputs"
AUTH_PREFLIGHT_ROLE_STEP_NAME = "Configure the read-only persistent auth preflight role"
COST_EVIDENCE_PLACEHOLDER_STEP_NAME = "Create a cost evidence placeholder before requesting AWS credentials"
COST_READER_IDENTITY_STEP_NAME = "Configure read-only Cost Explorer identity"
COST_OBSERVATION_STEP_NAME = "Verify the account and record observed pre-cycle billing"
FOUNDATION_PLAN_STEP_NAME = "Plan the K8s foundation opening"
MUTATING_DEPLOYMENT_STEP_NAMES = (
    "Apply the exact K8s foundation opening plan",
    "Apply the exact K8s platform opening plan",
    "Apply the exact HML namespace opening plan",
    "Provision the HML database role and SSM contract",
    "Bootstrap the synthetic lifecycle database",
    "Deploy the application and recreate its synthetic seed",
    "Apply the database grants after application migrations",
    "Reconcile the public API edge against the current ALB while preserving its URL",
)


def _run(
    run_id: int,
    *,
    status: str = "completed",
    conclusion: str = "failure",
    run_attempt: int = 1,
) -> dict[str, object]:
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "id": run_id,
        "display_title": "lifecycle:hml:open:test",
        "created_at": created_at,
        "status": status,
        "conclusion": conclusion,
        "run_attempt": run_attempt,
    }


def _brt_created_at(minutes_from_noon: int) -> str:
    local_noon = datetime.now(timezone.utc).astimezone(GUARD.BRT).replace(
        hour=12, minute=0, second=0, microsecond=0
    )
    return (local_noon + timedelta(minutes=minutes_from_noon)).astimezone(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


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


def _recovery_steps(
    *,
    record_conclusion: str,
    plan_conclusion: str,
    preflight_conclusion: str | None = None,
) -> list[dict[str, str]]:
    steps = [
        {"name": GUARD_STEP_NAME, "status": "completed", "conclusion": "success"},
        {"name": SESSION_RECORD_STEP_NAME, "status": "completed", "conclusion": record_conclusion},
    ]
    if preflight_conclusion is not None:
        steps.append(
            {"name": AUTH_PREFLIGHT_STEP_NAME, "status": "completed", "conclusion": preflight_conclusion}
        )
    steps.extend(
        [
            {"name": FOUNDATION_PLAN_STEP_NAME, "status": "completed", "conclusion": plan_conclusion},
            *[
                {"name": name, "status": "completed", "conclusion": "skipped"}
                for name in MUTATING_DEPLOYMENT_STEP_NAMES
            ],
        ]
    )
    return steps


def _cost_reader_identity_failure_steps() -> list[dict[str, str]]:
    return [
        {"name": GUARD_STEP_NAME, "status": "completed", "conclusion": "success"},
        {"name": SESSION_RECORD_STEP_NAME, "status": "completed", "conclusion": "success"},
        {"name": ALL_INPUTS_PREFLIGHT_STEP_NAME, "status": "completed", "conclusion": "success"},
        {"name": AUTH_PREFLIGHT_ROLE_STEP_NAME, "status": "completed", "conclusion": "success"},
        {"name": AUTH_PREFLIGHT_STEP_NAME, "status": "completed", "conclusion": "success"},
        {"name": COST_EVIDENCE_PLACEHOLDER_STEP_NAME, "status": "completed", "conclusion": "success"},
        {"name": COST_READER_IDENTITY_STEP_NAME, "status": "completed", "conclusion": "failure"},
        {"name": COST_OBSERVATION_STEP_NAME, "status": "completed", "conclusion": "skipped"},
        {"name": FOUNDATION_PLAN_STEP_NAME, "status": "completed", "conclusion": "skipped"},
        *[
            {"name": name, "status": "completed", "conclusion": "skipped"}
            for name in MUTATING_DEPLOYMENT_STEP_NAMES
        ],
    ]


def _guard_failure_steps() -> list[dict[str, str]]:
    return [
        {"name": "Set up job", "status": "completed", "conclusion": "success"},
        {"name": "Run actions/checkout@v4", "status": "completed", "conclusion": "success"},
        {
            "name": "Require the triggering actor before AWS credentials",
            "status": "completed",
            "conclusion": "success",
        },
        {
            "name": "Resolve the one session identifier and all BRT deadlines",
            "status": "completed",
            "conclusion": "success",
        },
        {"name": "Sign the resolved lifecycle session capability", "status": "completed", "conclusion": "success"},
        {"name": GUARD_STEP_NAME, "status": "completed", "conclusion": "failure"},
        {"name": FIRST_MUTATION_STEP_NAME, "status": "completed", "conclusion": "skipped"},
        {"name": SESSION_RECORD_STEP_NAME, "status": "completed", "conclusion": "skipped"},
        {"name": ALL_INPUTS_PREFLIGHT_STEP_NAME, "status": "completed", "conclusion": "skipped"},
        {"name": AUTH_PREFLIGHT_ROLE_STEP_NAME, "status": "completed", "conclusion": "skipped"},
        {"name": AUTH_PREFLIGHT_STEP_NAME, "status": "completed", "conclusion": "skipped"},
        {"name": COST_EVIDENCE_PLACEHOLDER_STEP_NAME, "status": "completed", "conclusion": "skipped"},
        {"name": COST_READER_IDENTITY_STEP_NAME, "status": "completed", "conclusion": "skipped"},
        {"name": COST_OBSERVATION_STEP_NAME, "status": "completed", "conclusion": "skipped"},
        {"name": FOUNDATION_PLAN_STEP_NAME, "status": "completed", "conclusion": "skipped"},
        *[
            {"name": name, "status": "completed", "conclusion": "skipped"}
            for name in MUTATING_DEPLOYMENT_STEP_NAMES
        ],
    ]


def _active_guard_failure_payload(
    *,
    active_jobs: tuple[str, ...] = (HML_AUTO_STOP_WAIT_JOB_NAME,),
    open_status: str = "completed",
    open_conclusion: str = "failure",
    steps: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    jobs = [
        {"name": "hml-gates", "status": "completed", "conclusion": "success", "steps": []},
        {
            "name": "open",
            "status": open_status,
            "conclusion": open_conclusion,
            "steps": steps or _guard_failure_steps(),
        },
        *[
            {"name": name, "status": "in_progress", "conclusion": None, "steps": []}
            for name in active_jobs
        ],
    ]
    return {"total_count": len(jobs), "jobs": jobs}


def _set_github_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_RUN_ID", CURRENT_RUN_ID)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
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


def test_rerun_after_an_unmutated_preflight_failure_is_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_context(monkeypatch)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    current_run = _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="", run_attempt=2)
    steps = _recovery_steps(record_conclusion="failure", plan_conclusion="skipped")
    requested_urls = _stub_api(
        monkeypatch,
        [_listing(current_run), _jobs_payload(open_conclusion="failure", steps=steps)],
    )

    assert GUARD.main() == 0
    assert requested_urls[1].endswith(f"/actions/runs/{CURRENT_RUN_ID}/attempts/1/jobs?per_page=100")


def test_rerun_after_an_infrastructure_apply_blocks_duplicate_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_context(monkeypatch)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    current_run = _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="", run_attempt=2)
    steps = _recovery_steps(record_conclusion="success", plan_conclusion="failure")
    steps[-len(MUTATING_DEPLOYMENT_STEP_NAMES)] = {
        "name": MUTATING_DEPLOYMENT_STEP_NAMES[0],
        "status": "completed",
        "conclusion": "success",
    }
    _stub_api(
        monkeypatch,
        [_listing(current_run), _jobs_payload(open_conclusion="failure", steps=steps)],
    )

    assert GUARD.main() == 1


def test_rerun_with_an_existing_ledger_owner_requires_a_new_run_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_context(monkeypatch)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    current_run = _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="", run_attempt=2)
    steps = _recovery_steps(record_conclusion="success", plan_conclusion="failure")
    _stub_api(
        monkeypatch,
        [_listing(current_run), _jobs_payload(open_conclusion="failure", steps=steps)],
    )

    assert GUARD.main() == 1


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
    assert requested_urls[1].endswith(f"/actions/runs/{PRIOR_RUN_ID}/attempts/1/jobs?per_page=100")


def test_duplicate_guard_failure_is_retryable_before_first_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_github_context(monkeypatch)
    steps = _recovery_steps(record_conclusion="skipped", plan_conclusion="skipped")
    steps[0]["conclusion"] = "failure"
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
        [
            _listing(_run(PRIOR_RUN_ID, status="in_progress", conclusion="")),
            _jobs_payload(open_status="in_progress", open_conclusion="", steps=[]),
        ],
    )

    assert GUARD.main() == 1
    assert len(requested_urls) == 2


def test_active_prior_guard_failure_allows_recovery_only_while_auto_stop_wait_is_the_only_active_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_context(monkeypatch)
    owner_run = _run(PRIOR_RUN_ID)
    active_guard_failure_run = _run(PRIOR_RUN_ID + 1, status="in_progress", conclusion="")
    current_run = _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="")
    with tempfile.TemporaryDirectory(prefix="lifecycle-guard-active-wait-recovery-test-") as temporary_directory:
        output_path = Path(temporary_directory) / "github-output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))
        _stub_api(
            monkeypatch,
            [
                _listing(owner_run, active_guard_failure_run, current_run),
                _active_guard_failure_payload(),
                _jobs_payload(open_conclusion="failure", steps=_cost_reader_identity_failure_steps()),
            ],
        )

        assert GUARD.main() == 0
        assert output_path.read_text(encoding="utf-8") == f"recovery_source_run_id={PRIOR_RUN_ID}\n"


def test_active_open_job_does_not_qualify_for_auto_stop_wait_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_context(monkeypatch)
    active_run = _run(PRIOR_RUN_ID, status="in_progress", conclusion="")
    _stub_api(
        monkeypatch,
        [
            _listing(active_run, _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="")),
            _active_guard_failure_payload(active_jobs=(), open_status="in_progress", open_conclusion=""),
        ],
    )

    assert GUARD.main() == 1


def test_active_wait_with_a_ledger_owner_is_not_eligible_for_the_guard_failure_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_context(monkeypatch)
    active_run = _run(PRIOR_RUN_ID, status="in_progress", conclusion="")
    _stub_api(
        monkeypatch,
        [
            _listing(active_run, _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="")),
            _active_guard_failure_payload(steps=_cost_reader_identity_failure_steps()),
        ],
    )

    assert GUARD.main() == 1


def test_another_active_job_blocks_auto_stop_wait_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_context(monkeypatch)
    active_run = _run(PRIOR_RUN_ID, status="in_progress", conclusion="")
    _stub_api(
        monkeypatch,
        [
            _listing(active_run, _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="")),
            _active_guard_failure_payload(active_jobs=(HML_AUTO_STOP_WAIT_JOB_NAME, "database-migration")),
        ],
    )

    assert GUARD.main() == 1


def test_unknown_mutation_evidence_blocks_auto_stop_wait_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_context(monkeypatch)
    active_run = _run(PRIOR_RUN_ID, status="in_progress", conclusion="")
    steps = _guard_failure_steps()
    steps[-1]["name"] = "Unknown infrastructure mutation step"
    _stub_api(
        monkeypatch,
        [
            _listing(active_run, _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="")),
            _active_guard_failure_payload(steps=steps),
        ],
    )

    assert GUARD.main() == 1


def test_successful_prior_run_still_blocks_recovery(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_github_context(monkeypatch)
    requested_urls = _stub_api(
        monkeypatch,
        [_listing(_run(PRIOR_RUN_ID, status="completed", conclusion="success"))],
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


def test_failed_authorization_attempts_allow_only_verified_ledger_handoff(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_github_context(monkeypatch)
    with tempfile.TemporaryDirectory(prefix="lifecycle-guard-test-") as temporary_directory:
        output_path = Path(temporary_directory) / "github-output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))
        current_run = _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="")
        requested_urls = _stub_api(
            monkeypatch,
            [
                _listing(_run(PRIOR_RUN_ID, run_attempt=2), current_run),
                _jobs_payload(
                    open_conclusion="failure",
                    steps=_recovery_steps(record_conclusion="success", plan_conclusion="failure"),
                ),
                _jobs_payload(
                    open_conclusion="failure",
                    steps=_recovery_steps(record_conclusion="failure", plan_conclusion="skipped"),
                ),
            ],
        )

        assert GUARD.main() == 0
        assert requested_urls[1].endswith(f"/actions/runs/{PRIOR_RUN_ID}/attempts/1/jobs?per_page=100")
        assert requested_urls[2].endswith(f"/actions/runs/{PRIOR_RUN_ID}/attempts/2/jobs?per_page=100")
        assert output_path.read_text(encoding="utf-8") == f"recovery_source_run_id={PRIOR_RUN_ID}\n"


def test_unrecorded_failed_retry_does_not_hide_the_older_verified_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_context(monkeypatch)
    older_owner_run = _run(PRIOR_RUN_ID)
    older_owner_run["created_at"] = _brt_created_at(-2)
    unrecorded_retry_run = _run(PRIOR_RUN_ID + 1)
    unrecorded_retry_run["created_at"] = _brt_created_at(-1)
    current_run = _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="")
    with tempfile.TemporaryDirectory(prefix="lifecycle-guard-unrecorded-retry-test-") as temporary_directory:
        output_path = Path(temporary_directory) / "github-output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))
        _stub_api(
            monkeypatch,
            [
                _listing(older_owner_run, unrecorded_retry_run, current_run),
                _jobs_payload(
                    open_conclusion="failure",
                    steps=_recovery_steps(record_conclusion="success", plan_conclusion="failure"),
                ),
                _jobs_payload(
                    open_conclusion="failure",
                    steps=_recovery_steps(record_conclusion="failure", plan_conclusion="skipped"),
                ),
            ],
        )

        assert GUARD.main() == 0
        assert output_path.read_text(encoding="utf-8") == f"recovery_source_run_id={PRIOR_RUN_ID}\n"


def test_recorded_auth_preflight_failure_is_a_safe_recovery_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_context(monkeypatch)
    failed_run = _run(PRIOR_RUN_ID)
    current_run = _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="")
    with tempfile.TemporaryDirectory(
        prefix="lifecycle-guard-auth-preflight-recovery-test-"
    ) as temporary_directory:
        output_path = Path(temporary_directory) / "github-output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))
        _stub_api(
            monkeypatch,
            [
                _listing(failed_run, current_run),
                _jobs_payload(
                    open_conclusion="failure",
                    steps=_recovery_steps(
                        record_conclusion="success",
                        plan_conclusion="skipped",
                        preflight_conclusion="failure",
                    ),
                ),
            ],
        )

        assert GUARD.main() == 0
        assert output_path.read_text(encoding="utf-8") == f"recovery_source_run_id={PRIOR_RUN_ID}\n"


def test_recorded_auth_preflight_failure_is_not_recoverable_after_a_deployment_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_context(monkeypatch)
    failed_steps = _recovery_steps(
        record_conclusion="success",
        plan_conclusion="skipped",
        preflight_conclusion="failure",
    )
    failed_steps[-1] = {
        "name": MUTATING_DEPLOYMENT_STEP_NAMES[-1],
        "status": "completed",
        "conclusion": "success",
    }
    _stub_api(
        monkeypatch,
        [
            _listing(_run(PRIOR_RUN_ID), _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="")),
            _jobs_payload(open_conclusion="failure", steps=failed_steps),
        ],
    )

    assert GUARD.main() == 1


def test_recorded_cost_reader_identity_failure_is_a_safe_recovery_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_context(monkeypatch)
    with tempfile.TemporaryDirectory(prefix="lifecycle-guard-cost-reader-recovery-test-") as temporary_directory:
        output_path = Path(temporary_directory) / "github-output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))
        _stub_api(
            monkeypatch,
            [
                _listing(_run(PRIOR_RUN_ID), _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="")),
                _jobs_payload(
                    open_conclusion="failure",
                    steps=_cost_reader_identity_failure_steps(),
                ),
            ],
        )

        assert GUARD.main() == 0
        assert output_path.read_text(encoding="utf-8") == f"recovery_source_run_id={PRIOR_RUN_ID}\n"


def test_cost_reader_identity_failure_is_not_recoverable_after_a_deployment_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_context(monkeypatch)
    steps = _cost_reader_identity_failure_steps()
    steps[-1] = {
        "name": MUTATING_DEPLOYMENT_STEP_NAMES[-1],
        "status": "completed",
        "conclusion": "success",
    }
    _stub_api(
        monkeypatch,
        [
            _listing(_run(PRIOR_RUN_ID), _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="")),
            _jobs_payload(open_conclusion="failure", steps=steps),
        ],
    )

    assert GUARD.main() == 1


def test_cost_reader_identity_failure_is_not_recoverable_with_unknown_mutation_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_context(monkeypatch)
    steps = _cost_reader_identity_failure_steps()
    steps[-1] = {
        "name": "Unknown infrastructure mutation step",
        "status": "completed",
        "conclusion": "skipped",
    }
    _stub_api(
        monkeypatch,
        [
            _listing(_run(PRIOR_RUN_ID), _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="")),
            _jobs_payload(open_conclusion="failure", steps=steps),
        ],
    )

    assert GUARD.main() == 1


def test_cost_observation_failure_is_not_misclassified_as_identity_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_context(monkeypatch)
    steps = _cost_reader_identity_failure_steps()
    steps[5]["conclusion"] = "success"
    steps[6]["conclusion"] = "failure"
    _stub_api(
        monkeypatch,
        [
            _listing(_run(PRIOR_RUN_ID), _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="")),
            _jobs_payload(open_conclusion="failure", steps=steps),
        ],
    )

    assert GUARD.main() == 1


def test_cost_reader_identity_recovery_is_limited_to_hml(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_context(monkeypatch)
    monkeypatch.setattr("sys.argv", [str(MODULE_PATH), "--stage", "prd"])
    prior_run = _run(PRIOR_RUN_ID)
    prior_run["display_title"] = "lifecycle:prd:open:test"
    current_run = _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="")
    current_run["display_title"] = "lifecycle:prd:open:test"
    _stub_api(
        monkeypatch,
        [
            _listing(prior_run, current_run),
            _jobs_payload(open_conclusion="failure", steps=_cost_reader_identity_failure_steps()),
        ],
    )

    assert GUARD.main() == 1


def test_cost_reader_recovery_rejects_mutation_in_a_later_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_context(monkeypatch)
    prior_run = _run(PRIOR_RUN_ID, run_attempt=2)
    later_attempt_steps = _cost_reader_identity_failure_steps()
    later_attempt_steps[-1] = {
        "name": MUTATING_DEPLOYMENT_STEP_NAMES[-1],
        "status": "completed",
        "conclusion": "success",
    }
    _stub_api(
        monkeypatch,
        [
            _listing(prior_run, _run(int(CURRENT_RUN_ID), status="in_progress", conclusion="")),
            _jobs_payload(open_conclusion="failure", steps=_cost_reader_identity_failure_steps()),
            _jobs_payload(open_conclusion="failure", steps=later_attempt_steps),
        ],
    )

    assert GUARD.main() == 1


def test_any_deployment_mutation_in_any_attempt_blocks_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_context(monkeypatch)
    attempt_one_steps = _recovery_steps(record_conclusion="success", plan_conclusion="failure")
    attempt_one_steps[-1] = {
        "name": MUTATING_DEPLOYMENT_STEP_NAMES[-1],
        "status": "completed",
        "conclusion": "success",
    }
    _stub_api(
        monkeypatch,
        [
            _listing(_run(PRIOR_RUN_ID, run_attempt=2)),
            _jobs_payload(
                open_conclusion="failure",
                steps=_recovery_steps(record_conclusion="success", plan_conclusion="failure"),
            ),
            _jobs_payload(open_conclusion="failure", steps=attempt_one_steps),
        ],
    )

    assert GUARD.main() == 1


def test_recovery_chain_uses_the_most_recent_verified_owner_run(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_github_context(monkeypatch)
    older_run = _run(PRIOR_RUN_ID)
    older_run["created_at"] = _brt_created_at(-2)
    newer_run = _run(PRIOR_RUN_ID + 1)
    newer_run["created_at"] = _brt_created_at(-1)
    with tempfile.TemporaryDirectory(prefix="lifecycle-guard-chain-test-") as temporary_directory:
        output_path = Path(temporary_directory) / "github-output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))
        _stub_api(
            monkeypatch,
            [
                _listing(older_run, newer_run),
                _jobs_payload(
                    open_conclusion="failure",
                    steps=_recovery_steps(record_conclusion="success", plan_conclusion="failure"),
                ),
                _jobs_payload(
                    open_conclusion="failure",
                    steps=_recovery_steps(record_conclusion="success", plan_conclusion="failure"),
                ),
            ],
        )

        assert GUARD.main() == 0
        assert output_path.read_text(encoding="utf-8") == f"recovery_source_run_id={PRIOR_RUN_ID + 1}\n"


def test_retry_contract_step_names_match_the_workflow() -> None:
    workflow = (ROOT / ".github" / "workflows" / "environment-start.yml").read_text(encoding="utf-8")

    guard_index = workflow.index(f"- name: {GUARD_STEP_NAME}")
    mutation_index = workflow.index(f"- name: {FIRST_MUTATION_STEP_NAME}")
    assert guard_index < mutation_index
    assert "id: daily_unique" in workflow
    assert "--safe-retry-source-run-id \"$SAFE_RETRY_SOURCE_RUN_ID\"" in workflow
    assert SESSION_RECORD_STEP_NAME in workflow
    assert AUTH_PREFLIGHT_STEP_NAME in workflow
    assert FOUNDATION_PLAN_STEP_NAME in workflow
    assert all(name in workflow for name in MUTATING_DEPLOYMENT_STEP_NAMES)

