from pathlib import Path


WORKFLOW_DIRECTORY = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def test_hml_health_and_close_dispatches_target_develop() -> None:
    start_workflow = (WORKFLOW_DIRECTORY / "environment-start.yml").read_text(
        encoding="utf-8"
    )

    assert (
        "HEALTH_REF: ${{ steps.window.outputs.stage == 'prd' && 'main' || 'develop' }}"
        in start_workflow
    )
    assert '--workflow environment-health.yml --ref "$HEALTH_REF"' in start_workflow
    assert "--workflow environment-stop.yml --ref develop" in start_workflow
