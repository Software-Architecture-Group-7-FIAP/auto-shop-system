from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "require_trusted_lifecycle_operator.py"
SPEC = importlib.util.spec_from_file_location("require_trusted_lifecycle_operator", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
ACTOR_GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ACTOR_GATE)


@pytest.mark.parametrize("arguments", [["--require-dispatch-actor"], ["--dispatch-only"]])
def test_actor_gate_rejects_rerun_by_another_triggering_actor(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], arguments: list[str]
) -> None:
    for key, value in {
        "GITHUB_ACTOR": "trusted-operator",
        "LIFECYCLE_TRIGGERING_ACTOR": "untrusted-rerunner",
        "LIFECYCLE_TRUSTED_OPERATORS": "trusted-operator,dispatch-bot[bot]",
        "LIFECYCLE_CROSS_REPO_ACTOR": "dispatch-bot[bot]",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), *arguments])

    assert ACTOR_GATE.main() == 1
    assert "triggering actor does not match the original workflow actor" in capsys.readouterr().err


def test_scheduled_cleanup_keeps_its_dispatch_only_operator_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key, value in {
        "GITHUB_ACTOR": "github-actions[bot]",
        "LIFECYCLE_TRIGGERING_ACTOR": "github-actions[bot]",
        "LIFECYCLE_TRUSTED_OPERATORS": "dispatch-bot[bot]",
        "LIFECYCLE_CROSS_REPO_ACTOR": "dispatch-bot[bot]",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--dispatch-only"])

    assert ACTOR_GATE.main() == 0


def test_lifecycle_coordinators_bind_current_triggering_actor_before_aws_roles() -> None:
    workflow_names = (
        "environment-start.yml",
        "environment-stop.yml",
        "lifecycle-cleanup.yml",
    )
    for workflow_name in workflow_names:
        workflow = (ROOT / ".github" / "workflows" / workflow_name).read_text(encoding="utf-8")
        assert "LIFECYCLE_TRIGGERING_ACTOR: ${{ github.triggering_actor }}" in workflow
        jobs = workflow.split("jobs:", maxsplit=1)[1]
        for match in re.finditer(r"(?m)^  [A-Za-z0-9_-]+:\s*$", jobs):
            next_job = re.search(r"(?m)^  [A-Za-z0-9_-]+:\s*$", jobs[match.end() :])
            end = match.end() + next_job.start() if next_job else len(jobs)
            job = jobs[match.start() : end]
            role_step = "aws-actions/configure-aws-credentials@"
            if role_step not in job:
                continue
            gate = "require_trusted_lifecycle_operator.py"
            assert gate in job, f"{workflow_name} job lacks an actor gate before AWS credentials"
            assert job.index(gate) < job.index(role_step), f"{workflow_name} gates the actor after AWS credentials"
