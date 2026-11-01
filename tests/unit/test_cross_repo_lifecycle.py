import argparse
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest


SCRIPT_PATH = Path(__file__).parents[2] / ".github" / "scripts" / "cross_repo_lifecycle.py"
SPEC = importlib.util.spec_from_file_location("cross_repo_lifecycle", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
cross_repo_lifecycle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cross_repo_lifecycle)


def make_arguments(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "repository": "example/infra",
        "workflow": "apply.yml",
        "ref": "main",
        "expected_title": "session-platform-open",
        "output_name": "platform",
        "timeout_seconds": 60,
        "poll_seconds": 1,
        "cancel_wait_seconds": 30,
        "cancel_active_workflow": "",
        "cancel_title_prefix": "",
        "authorization_action": "",
        "inputs": '{"session_id":"hml-2026-10-29"}',
        "deadline_utc": "",
        "github_output": "",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_cancel_wait_is_limited_to_the_reserved_thirty_seconds():
    with pytest.raises(cross_repo_lifecycle.LifecycleDispatchError, match="between 1 and 30"):
        cross_repo_lifecycle._validate_arguments(make_arguments(cancel_wait_seconds=31))

    repository, _ = cross_repo_lifecycle._validate_arguments(make_arguments(cancel_wait_seconds=30))
    assert repository == "example/infra"


def test_validation_rejects_unknown_lifecycle_authorization_action():
    with pytest.raises(cross_repo_lifecycle.LifecycleDispatchError, match="authorization action is not allowed"):
        cross_repo_lifecycle._validate_arguments(make_arguments(authorization_action="restart"))


def test_api_request_applies_the_remaining_deadline_timeout():
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b"{}"

    with patch.object(cross_repo_lifecycle, "urlopen", return_value=Response()) as urlopen:
        assert cross_repo_lifecycle._api_request(
            "token", "GET", "/test", timeout_seconds=2.5
        ) == {}

    assert urlopen.call_args.kwargs["timeout"] == 2.5


def test_dispatch_id_is_stable_for_a_workflow_run_and_does_not_depend_on_the_session_token():
    arguments = make_arguments()
    inputs = {"session_id": "hml-2026-10-29", "session_token": "a" * 64}

    with patch.dict("os.environ", {"GITHUB_RUN_ID": "123456"}):
        first = cross_repo_lifecycle._stable_dispatch_id(arguments, "example/infra", inputs)
        second = cross_repo_lifecycle._stable_dispatch_id(
            arguments,
            "example/infra",
            {"session_id": "hml-2026-10-29", "session_token": "b" * 64},
        )

    assert first == second
    assert len(first) == 32


def test_dispatch_id_changes_on_a_new_central_workflow_attempt():
    arguments = make_arguments()
    inputs = {"session_id": "hml-2026-10-29"}

    with patch.dict("os.environ", {"GITHUB_RUN_ID": "123456", "GITHUB_RUN_ATTEMPT": "1"}):
        first_attempt = cross_repo_lifecycle._stable_dispatch_id(arguments, "example/infra", inputs)
    with patch.dict("os.environ", {"GITHUB_RUN_ID": "123456", "GITHUB_RUN_ATTEMPT": "2"}):
        second_attempt = cross_repo_lifecycle._stable_dispatch_id(arguments, "example/infra", inputs)

    assert first_attempt != second_attempt


def test_issue_dispatch_authorization_uses_the_ledger_cli_with_the_exact_payload():
    inputs = {
        "session_id": "hml-2026-10-29",
        "started_at": "2026-10-29T12:00:00Z",
        "session_mode": "hml",
        "session_token": "a" * 64,
        "lifecycle_dispatch_id": "b" * 32,
    }
    with patch.object(
        cross_repo_lifecycle.subprocess,
        "run",
        return_value=SimpleNamespace(returncode=0, stdout="", stderr=""),
    ) as run:
        cross_repo_lifecycle._issue_dispatch_authorization(
            action="close",
            session_id="hml-2026-10-29",
            dispatch_id="b" * 32,
            repository="example/infra",
            workflow="apply.yml",
            ref="main",
            inputs=inputs,
        )

    command = run.call_args.args[0]
    assert command[1].endswith("lifecycle_session_ledger.py")
    assert command[2:13] == [
        "issue-dispatch",
        "--session-id",
        "hml-2026-10-29",
        "--dispatch-id",
        "b" * 32,
        "--action",
        "close",
        "--repository",
        "example/infra",
        "--workflow",
        "apply.yml",
    ]
    assert command[13:16] == ["--ref", "main", "--inputs"]
    assert command[16] == json.dumps(inputs, separators=(",", ":"))
    assert run.call_args.kwargs["check"] is False


def test_dispatch_rerun_resumes_an_existing_completed_run_without_dispatching_again(tmp_path):
    arguments = make_arguments(github_output=str(tmp_path / "github-output"))
    inputs = {"session_id": "hml-2026-10-29"}
    with patch.dict(
        "os.environ",
        {
            "GITHUB_RUN_ID": "123456",
            "LIFECYCLE_CROSS_REPO_TOKEN": "github-token",
            "LIFECYCLE_SESSION_TOKEN": "a" * 64,
        },
    ):
        dispatch_id = cross_repo_lifecycle._stable_dispatch_id(arguments, "example/infra", inputs)
        now = datetime.now(timezone.utc)
        existing_run = {
            "id": 8675309,
            "run_attempt": 1,
            "display_title": f"{arguments.expected_title}:{dispatch_id}",
            "created_at": (now - timedelta(seconds=10)).isoformat(),
            "status": "completed",
            "conclusion": "success",
            "completed_at": (now - timedelta(seconds=2)).isoformat(),
        }
        with (
            patch.object(cross_repo_lifecycle, "_list_runs", return_value=[existing_run]),
            patch.object(cross_repo_lifecycle, "_api_request") as api_request,
            patch.object(cross_repo_lifecycle, "_issue_dispatch_authorization") as issue_authorization,
        ):
            assert cross_repo_lifecycle.dispatch_and_wait(arguments) == 0

    api_request.assert_not_called()
    issue_authorization.assert_not_called()
    assert (tmp_path / "github-output").read_text(encoding="utf-8").splitlines() == [
        "platform_run_id=8675309",
        f"platform_dispatch_id={dispatch_id}",
        "platform_run_attempt=1",
        "platform_plan_id=8675309-1",
    ]


def test_dispatch_rerun_resumes_prior_successful_attempt(tmp_path):
    arguments = make_arguments(github_output=str(tmp_path / "github-output"))
    inputs = {"session_id": "hml-2026-10-29"}
    with patch.dict(
        "os.environ",
        {
            "GITHUB_RUN_ID": "123456",
            "GITHUB_RUN_ATTEMPT": "2",
            "LIFECYCLE_CROSS_REPO_TOKEN": "github-token",
            "LIFECYCLE_SESSION_TOKEN": "a" * 64,
        },
    ):
        previous_dispatch_id = cross_repo_lifecycle._stable_dispatch_id(
            arguments, "example/infra", inputs, run_attempt=1
        )
        now = datetime.now(timezone.utc)
        successful_run = {
            "id": 8675309,
            "run_attempt": 1,
            "display_title": f"{arguments.expected_title}:{previous_dispatch_id}",
            "created_at": (now - timedelta(seconds=10)).isoformat(),
            "status": "completed",
            "conclusion": "success",
            "completed_at": (now - timedelta(seconds=2)).isoformat(),
        }
        with (
            patch.object(cross_repo_lifecycle, "_list_runs", return_value=[successful_run]),
            patch.object(cross_repo_lifecycle, "_api_request") as api_request,
            patch.object(cross_repo_lifecycle, "_issue_dispatch_authorization") as issue_authorization,
        ):
            assert cross_repo_lifecycle.dispatch_and_wait(arguments) == 0

    api_request.assert_not_called()
    issue_authorization.assert_not_called()
    assert (tmp_path / "github-output").read_text(encoding="utf-8").splitlines() == [
        "platform_run_id=8675309",
        f"platform_dispatch_id={previous_dispatch_id}",
        "platform_run_attempt=1",
        "platform_plan_id=8675309-1",
    ]


def test_dispatch_rerun_retries_a_prior_terminal_failure(tmp_path):
    inputs = {
        "session_id": "hml-2026-10-29",
        "started_at": "2026-10-29T12:00:00Z",
        "session_mode": "hml",
    }
    arguments = make_arguments(
        github_output=str(tmp_path / "github-output"),
        authorization_action="close",
        inputs=json.dumps(inputs),
    )
    with patch.dict(
        "os.environ",
        {
            "GITHUB_RUN_ID": "123456",
            "GITHUB_RUN_ATTEMPT": "2",
            "LIFECYCLE_CROSS_REPO_TOKEN": "github-token",
            "LIFECYCLE_SESSION_TOKEN": "a" * 64,
        },
    ):
        previous_dispatch_id = cross_repo_lifecycle._stable_dispatch_id(
            arguments, "example/infra", inputs, run_attempt=1
        )
        current_dispatch_id = cross_repo_lifecycle._stable_dispatch_id(
            arguments, "example/infra", inputs, run_attempt=2
        )
        now = datetime.now(timezone.utc)
        failed_run = {
            "id": 8675308,
            "run_attempt": 1,
            "display_title": f"{arguments.expected_title}:{previous_dispatch_id}",
            "created_at": (now - timedelta(seconds=10)).isoformat(),
            "status": "completed",
            "conclusion": "failure",
            "completed_at": (now - timedelta(seconds=2)).isoformat(),
        }
        retried_run = {
            "id": 8675309,
            "run_attempt": 1,
            "display_title": f"{arguments.expected_title}:{current_dispatch_id}",
            "created_at": (now + timedelta(seconds=5)).isoformat(),
            "status": "completed",
            "conclusion": "success",
            "completed_at": (now + timedelta(seconds=6)).isoformat(),
        }
        list_runs_call = 0

        def list_runs(*_args, **_kwargs):
            nonlocal list_runs_call
            list_runs_call += 1
            if list_runs_call == 1:
                return [failed_run]
            dispatch_not_before = _args[4]
            return [
                {
                    **retried_run,
                    "created_at": (dispatch_not_before + timedelta(seconds=1)).isoformat(),
                    "completed_at": (dispatch_not_before + timedelta(seconds=2)).isoformat(),
                }
            ]

        events: list[tuple[str, object]] = []
        with (
            patch.object(cross_repo_lifecycle, "_list_runs", side_effect=list_runs),
            patch.object(
                cross_repo_lifecycle,
                "_api_request",
                side_effect=lambda *args, **_kwargs: events.append(("dispatch", args)),
            ) as api_request,
            patch.object(
                cross_repo_lifecycle,
                "_issue_dispatch_authorization",
                side_effect=lambda **kwargs: events.append(("authorize", kwargs)),
            ) as issue_authorization,
            patch.object(cross_repo_lifecycle.time, "sleep"),
        ):
            assert cross_repo_lifecycle.dispatch_and_wait(arguments) == 0

    assert api_request.call_args.args[1] == "POST"
    assert api_request.call_args.args[2].endswith("/actions/workflows/apply.yml/dispatches")
    assert issue_authorization.call_count == 1
    assert [event[0] for event in events] == ["authorize", "dispatch"]
    assert events[0][1] == {
        "action": "close",
        "session_id": "hml-2026-10-29",
        "dispatch_id": current_dispatch_id,
        "repository": "example/infra",
        "workflow": "apply.yml",
        "ref": "main",
        "inputs": {
            **inputs,
            "session_token": "a" * 64,
            "lifecycle_dispatch_id": current_dispatch_id,
        },
    }
    assert (tmp_path / "github-output").read_text(encoding="utf-8").splitlines()[1] == (
        f"platform_dispatch_id={current_dispatch_id}"
    )


def test_dispatch_rerun_resumes_an_in_progress_child_without_reauthorizing(tmp_path):
    arguments = make_arguments(github_output=str(tmp_path / "github-output"), timeout_seconds=10)
    inputs = {"session_id": "hml-2026-10-29"}
    with patch.dict(
        "os.environ",
        {
            "GITHUB_RUN_ID": "123456",
            "LIFECYCLE_CROSS_REPO_TOKEN": "github-token",
            "LIFECYCLE_SESSION_TOKEN": "a" * 64,
        },
    ):
        dispatch_id = cross_repo_lifecycle._stable_dispatch_id(arguments, "example/infra", inputs)
        now = datetime.now(timezone.utc)
        active_run = {
            "id": 8675309,
            "run_attempt": 1,
            "display_title": f"{arguments.expected_title}:{dispatch_id}",
            "created_at": (now - timedelta(seconds=10)).isoformat(),
            "status": "in_progress",
        }
        completed_run = {
            **active_run,
            "status": "completed",
            "conclusion": "success",
            "completed_at": (now + timedelta(seconds=1)).isoformat(),
        }
        with (
            patch.object(cross_repo_lifecycle, "_list_runs", side_effect=[[active_run], [completed_run]]),
            patch.object(cross_repo_lifecycle, "_api_request") as api_request,
            patch.object(cross_repo_lifecycle, "_issue_dispatch_authorization") as issue_authorization,
            patch.object(cross_repo_lifecycle.time, "sleep"),
        ):
            assert cross_repo_lifecycle.dispatch_and_wait(arguments) == 0

    api_request.assert_not_called()
    issue_authorization.assert_not_called()
    assert (tmp_path / "github-output").read_text(encoding="utf-8").splitlines()[1] == (
        f"platform_dispatch_id={dispatch_id}"
    )
