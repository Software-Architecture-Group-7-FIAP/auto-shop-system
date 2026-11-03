from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / ".github" / "scripts" / "reconcile_codebuild_runner_webhook.py"
WORKFLOWS = ROOT / ".github" / "workflows"


def _load_script():
    spec = importlib.util.spec_from_file_location("codebuild_runner_webhook", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _filter_groups(workflow_pattern: str) -> list[list[dict[str, str]]]:
    return [
        [
            {"type": "EVENT", "pattern": "WORKFLOW_JOB_QUEUED"},
            {"type": "WORKFLOW_NAME", "pattern": workflow_pattern},
        ],
        [
            {"type": "EVENT", "pattern": "PUSH"},
            {"type": "HEAD_REF", "pattern": "^refs/heads/main$"},
        ],
    ]


def test_reconciliation_changes_only_the_runner_filter_and_is_idempotent() -> None:
    script = _load_script()
    original = _filter_groups(script.LEGACY_WORKFLOW_NAME_PATTERN)

    updated, changed = script.reconcile_filter_groups(original)

    assert changed is True
    assert original == _filter_groups(script.LEGACY_WORKFLOW_NAME_PATTERN)
    assert updated[0][1] == {
        "type": "WORKFLOW_NAME",
        "pattern": script.TARGET_WORKFLOW_NAME_PATTERN,
    }
    assert updated[1] == original[1]

    repeated, changed_again = script.reconcile_filter_groups(updated)

    assert changed_again is False
    assert repeated == updated


def test_runner_filter_matches_only_expected_deploy_run_name_shapes() -> None:
    script = _load_script()
    matcher = re.compile(script.TARGET_WORKFLOW_NAME_PATTERN)

    matching_names = (
        f"HML deploy {'a' * 40}",
        f"lifecycle:hml-2026-11-03:app-deploy:{'b' * 32}",
        "lifecycle:prd-2026-11-03:app-deploy:1234567890",
    )
    rejected_names = (
        "HML deploy abc123",
        "lifecycle:push-123:app-deploy:123",
        "lifecycle:hml-2026-11-03:environment-stop:123",
        "lifecycle:other-session:app-deploy:123",
        "lifecycle:hml-2026-11-03:app-deploy:leading-zero-01",
    )

    assert all(matcher.fullmatch(name) for name in matching_names)
    assert not any(matcher.fullmatch(name) for name in rejected_names)


def test_unexpected_runner_webhook_filter_fails_closed() -> None:
    script = _load_script()
    current = _filter_groups("^.*$")

    with pytest.raises(script.WebhookContractError):
        script.reconcile_filter_groups(current)


def test_runner_filter_does_not_share_an_event_group_with_other_events() -> None:
    script = _load_script()
    current = _filter_groups(script.LEGACY_WORKFLOW_NAME_PATTERN)
    current[0][0]["pattern"] = "WORKFLOW_JOB_QUEUED,PUSH"

    with pytest.raises(script.WebhookContractError):
        script.reconcile_filter_groups(current)


def test_reconciliation_rejects_excluding_runner_filters() -> None:
    script = _load_script()
    current = _filter_groups(script.LEGACY_WORKFLOW_NAME_PATTERN)
    current[0][1]["excludeMatchedPattern"] = True

    with pytest.raises(script.WebhookContractError):
        script.reconcile_filter_groups(current)


@pytest.mark.parametrize(
    "source_location",
    (
        "https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system.git",
        "CODEBUILD_DEFAULT_WEBHOOK_SOURCE_LOCATION",
    ),
)
def test_operational_command_is_read_only_without_apply(
    monkeypatch, capsys, source_location: str
) -> None:
    script = _load_script()
    groups = _filter_groups(script.LEGACY_WORKFLOW_NAME_PATTERN)
    commands: list[list[str]] = []

    def fake_aws_json(arguments, *, region: str, profile: str | None):
        commands.append(list(arguments))
        if arguments[:2] == ["sts", "get-caller-identity"]:
            return {"Account": "123456789012"}
        if arguments[:2] == ["codebuild", "batch-get-projects"]:
            return {
                "projects": [
                    {
                        "name": script.PROJECT_NAME,
                        "source": {
                            "type": "GITHUB",
                            "location": source_location,
                        },
                        "webhook": {"status": "ACTIVE", "filterGroups": groups},
                    }
                ]
            }
        raise AssertionError(f"Unexpected AWS command: {arguments}")

    monkeypatch.setattr(script, "_run_aws_json", fake_aws_json)

    result = script.main(["--expected-account-id", "123456789012"])

    assert result == 0
    assert not any(
        command[:2] == ["codebuild", "update-webhook"] for command in commands
    )
    assert "Read-only plan" in capsys.readouterr().out


def test_apply_updates_once_then_becomes_a_noop(monkeypatch, capsys) -> None:
    script = _load_script()
    groups = _filter_groups(script.LEGACY_WORKFLOW_NAME_PATTERN)
    update_calls = 0

    def fake_aws_json(arguments, *, region: str, profile: str | None):
        nonlocal update_calls
        if arguments[:2] == ["sts", "get-caller-identity"]:
            return {"Account": "123456789012"}
        if arguments[:2] == ["codebuild", "batch-get-projects"]:
            return {
                "projects": [
                    {
                        "name": script.PROJECT_NAME,
                        "source": {
                            "type": "GITHUB",
                            "location": "https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system.git",
                        },
                        "webhook": {"status": "ACTIVE", "filterGroups": groups},
                    }
                ]
            }
        if arguments[:2] == ["codebuild", "update-webhook"]:
            update_calls += 1
            groups[:] = json.loads(arguments[5])
            return {"webhook": {"status": "ACTIVE"}}
        raise AssertionError(f"Unexpected AWS command: {arguments}")

    monkeypatch.setattr(script, "_run_aws_json", fake_aws_json)
    cli_args = ["--expected-account-id", "123456789012", "--apply"]

    assert script.main(cli_args) == 0
    assert script.main(cli_args) == 0

    assert update_calls == 1
    assert "already matches" in capsys.readouterr().out


def test_account_mismatch_stops_before_project_lookup(monkeypatch, capsys) -> None:
    script = _load_script()
    commands: list[list[str]] = []

    def fake_aws_json(arguments, *, region: str, profile: str | None):
        commands.append(list(arguments))
        return {"Account": "999999999999"}

    monkeypatch.setattr(script, "_run_aws_json", fake_aws_json)

    result = script.main(
        ["--expected-account-id", "123456789012", "--apply"]
    )

    assert result == 2
    assert commands == [["sts", "get-caller-identity"]]
    assert "does not match" in capsys.readouterr().err


def test_lifecycle_workflow_titles_remain_correlated_with_the_ledger() -> None:
    expected_run_name = (
        "run-name: lifecycle:${{ inputs.session_id || format('push-{0}', github.run_id) }}:"
        "app-deploy:${{ inputs.lifecycle_dispatch_id || github.run_id }}"
    )

    for filename in ("cd-staging.yml", "cd-prod.yml"):
        workflow = (WORKFLOWS / filename).read_text(encoding="utf-8")
        assert expected_run_name in workflow

    coordinator = (WORKFLOWS / "environment-start.yml").read_text(encoding="utf-8")
    assert "EXPECTED_TITLE: lifecycle:${{ steps.window.outputs.session_id }}:app-deploy" in coordinator
