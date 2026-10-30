from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_kubernetes_seed_job_is_hardened_and_uses_runtime_secret() -> None:
    manifest = (ROOT / "k8s/base/seed/seed-job.yaml").read_text(encoding="utf-8")

    assert 'command: ["python", "-m", "src.scripts.seed_synthetic_environment"]' in manifest
    assert "readOnlyRootFilesystem: true" in manifest
    assert "allowPrivilegeEscalation: false" in manifest
    assert 'runAsNonRoot: true' in manifest
    assert "activeDeadlineSeconds: 300" in manifest
    assert "ttlSecondsAfterFinished: 600" in manifest
    assert "name: auto-shop-secrets" in manifest
    assert "DEMO_ADMIN_PASSWORD" not in manifest


def test_deploy_scripts_apply_seed_after_migration_and_before_app() -> None:
    bash = (ROOT / "k8s/scripts/deploy.sh").read_text(encoding="utf-8")
    powershell = (ROOT / "k8s/scripts/deploy.ps1").read_text(encoding="utf-8")

    assert bash.index("apply_phase migration") < bash.index("apply_phase seed")
    assert bash.index("wait_seed") < bash.index("apply_phase app")
    assert powershell.index('Apply-RenderedPhase "migration"') < powershell.index(
        'Apply-RenderedPhase "seed"'
    )
    assert powershell.index("Wait-ForSeed") < powershell.index('Apply-RenderedPhase "app"')


def test_each_environment_has_a_seed_overlay() -> None:
    for environment in ("local", "staging", "production"):
        overlay = ROOT / f"k8s/overlays/{environment}/seed/kustomization.yaml"
        assert overlay.is_file()
        assert "../../../base/seed" in overlay.read_text(encoding="utf-8")


def test_ci_renders_seed_manifests_and_runs_seed_after_migrations() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "for phase in foundation migration seed app ingress" in workflow
    assert 's#__ALLOW_SYNTHETIC_SEED_IN_PRD__#"false"#g' in workflow
    assert 'demo_admin_password="$(openssl rand -hex 32)"' in workflow
    assert "DEMO_ADMIN_PASSWORD=%s\\n" in workflow
    migration_wait = workflow.index(
        "kubectl wait --for=condition=complete job/auto-shop-migrate"
    )
    seed_apply = workflow.index("kubectl apply -k k8s/overlays/local/seed")
    seed_wait = workflow.index(
        "kubectl wait --for=condition=complete job/auto-shop-seed"
    )
    app_apply = workflow.index("kubectl apply -k k8s/overlays/local/app")

    assert migration_wait < seed_apply < seed_wait < app_apply
