from pathlib import Path
import re

import pytest


WORKFLOW_DIRECTORY = Path(__file__).resolve().parents[2] / ".github" / "workflows"
DISPATCH_CONTRACTS = {
    "environment-start.yml": {
        "inputs": ("stage", "started_at"),
        "hml_choices": ("stage",),
    },
    "environment-health.yml": {
        "inputs": (
            "stage",
            "session_id",
            "started_at",
            "session_mode",
            "session_token",
            "lifecycle_dispatch_id",
        ),
        "hml_choices": ("stage",),
    },
    "environment-stop.yml": {
        "inputs": (
            "stage",
            "session_id",
            "started_at",
            "close_request_id",
            "session_token",
            "lifecycle_dispatch_id",
        ),
        "hml_choices": ("stage",),
    },
    "cd-staging.yml": {
        "inputs": (
            "session_id",
            "started_at",
            "session_mode",
            "session_token",
            "lifecycle_dispatch_id",
        ),
        "hml_choices": ("session_mode",),
    },
}


@pytest.mark.parametrize("workflow_name, contract", DISPATCH_CONTRACTS.items())
def test_default_branch_workflow_dispatch_contract_is_hml_only_and_fail_closed(
    workflow_name: str, contract: dict[str, tuple[str, ...]]
) -> None:
    workflow = (WORKFLOW_DIRECTORY / workflow_name).read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "permissions:\n  contents: read\n" in workflow
    assert "jobs:\n  reject-default-branch:" in workflow
    assert "exit 1" in workflow
    assert "Dispatch this workflow on the develop branch" in workflow

    for input_name in contract["inputs"]:
        assert f"      {input_name}:\n" in workflow

    for choice_name in contract["hml_choices"]:
        choice_block = workflow.split(f"      {choice_name}:\n", maxsplit=1)[1]
        choice_block = re.split(r"\n {6}\S", choice_block, maxsplit=1)[0]
        assert "options: [hml]" in choice_block

    for forbidden in ("id-token: write", "actions: write", "uses:", "schedule:"):
        assert forbidden not in workflow
