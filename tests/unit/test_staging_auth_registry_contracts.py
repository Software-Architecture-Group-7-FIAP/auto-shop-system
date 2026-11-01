import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _workflow_job(workflow: str, job_name: str) -> str:
    lines = workflow.splitlines()
    job_header = f"  {job_name}:"

    try:
        start = lines.index(job_header)
    except ValueError as error:
        raise AssertionError(f"Workflow job {job_name!r} is missing") from error

    job_lines = [lines[start]]
    for line in lines[start + 1 :]:
        if line.startswith("  ") and not line.startswith("    "):
            break
        job_lines.append(line)

    return "\n".join(job_lines)


def test_auth_preflight_policy_matches_lambda_auth_function_names() -> None:
    policy = (ROOT / "infra/aws/github_oidc.tf").read_text(encoding="utf-8")

    assert 'default     = "lambda-auth"' in policy
    assert "function:${var.auth_lambda_function_name}-hml" in policy
    assert "function:${var.auth_lambda_function_name}-prd" in policy
    assert "function:${var.auth_lambda_function_name}-homolog" not in policy
    assert "function:${var.auth_lambda_function_name}-prod" not in policy


@pytest.mark.parametrize(
    ("workflow_name", "role_reference"),
    (
        ("cd-staging.yml", "role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN_HML }}"),
        ("cd-prod.yml", "role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN_PRD }}"),
    ),
)
def test_deploy_authenticates_and_mirrors_ghcr_after_aws_credentials(
    workflow_name: str, role_reference: str,
) -> None:
    workflow = (ROOT / ".github/workflows" / workflow_name).read_text(
        encoding="utf-8"
    )
    aws_credentials = workflow.index(role_reference)
    mirror = workflow.index("Mirror authenticated GHCR image to private ECR")
    deploy = workflow.index("./k8s/scripts/deploy.sh")

    assert workflow.index("SOURCE_IMAGE: ${{ needs.build-push.outputs.ghcr_image_reference }}") < aws_credentials
    assert aws_credentials < mirror < deploy
    assert "packages: read" in workflow
    assert "GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in workflow
    assert "mirror_ghcr_image_to_ecr.py \"${SOURCE_IMAGE}\"" in workflow
    assert "IMAGE_REFERENCE: ${{ steps.ecr_image.outputs.image_reference }}" in workflow
    assert 'docker pull "${IMAGE_REFERENCE}"' not in workflow


def test_reusable_build_publishes_a_commit_derived_ghcr_source_reference() -> None:
    workflow = (ROOT / ".github/workflows/reusable-build-push.yml").read_text(
        encoding="utf-8"
    )
    build_job = _workflow_job(workflow, "build-push")

    assert "permissions: {}" in workflow
    assert "permissions:" in build_job
    assert "packages: write" in build_job
    assert "verify-anonymous-pull" not in workflow

    assert 'short="${GITHUB_SHA::7}"' in build_job
    assert 'tag="sha-${short}"' in build_job
    assert "ghcr_image_reference: ${{ steps.meta.outputs.image_reference }}" in build_job
    assert "value: ${{ jobs.build-push.outputs.ghcr_image_reference }}" in workflow


def test_ecr_mirror_enforces_commit_bound_source_and_immutable_private_target() -> None:
    mirror = (ROOT / "scripts/mirror_ghcr_image_to_ecr.py").read_text(
        encoding="utf-8"
    )
    terraform = (ROOT / "infra/aws/github_oidc.tf").read_text(encoding="utf-8")

    assert 'expected_tag = f"sha-{github_sha[:7]}"' in mirror
    assert 'expected_source = f"ghcr.io/{github_repository}:{expected_tag}"' in mirror
    assert "source_image != expected_source" in mirror
    assert '"docker", "login", "ghcr.io"' in mirror
    assert '"docker", "pull", source_image' in mirror
    assert '"imageTagMutability") != "IMMUTABLE"' in mirror
    assert "target_config_id != source_config_id" in mirror

    assert 'sid    = "MirrorAndPullApplicationImage"' in terraform
    assert "resources = [local.github_ecr_repository_arn]" in terraform
    assert 'sid       = "AuthenticateToECR"' in terraform
    assert 'actions   = ["ecr:GetAuthorizationToken"]' in terraform
    assert 'resources = ["*"]' in terraform
    assert 'permissions_boundary = local.github_deploy_permissions_boundary_arn' in terraform
    assert '"ecr:BatchCheckLayerAvailability"' in terraform
    assert '"ecr:BatchGetImage"' in terraform
    assert '"ecr:CompleteLayerUpload"' in terraform
    assert '"ecr:DescribeRepositories"' in terraform
    assert '"ecr:GetDownloadUrlForLayer"' in terraform
    assert '"ecr:InitiateLayerUpload"' in terraform
    assert '"ecr:PutImage"' in terraform
    assert '"ecr:UploadLayerPart"' in terraform


@pytest.mark.parametrize(
    ("workflow_name", "job_name", "branch"),
    (
        ("cd-staging.yml", "deploy-staging", "refs/heads/develop"),
        ("cd-prod.yml", "deploy-production", "refs/heads/main"),
    ),
)
def test_deploy_jobs_require_dispatch_and_successful_prerequisites(
    workflow_name: str, job_name: str, branch: str,
) -> None:
    workflow = (ROOT / ".github/workflows" / workflow_name).read_text(
        encoding="utf-8"
    )
    deploy_job = _workflow_job(workflow, job_name)
    condition_match = re.search(
        r"(?ms)^    if:\s*(.*?)(?=^    [A-Za-z_][\w-]*:|\Z)", deploy_job
    )

    assert condition_match is not None
    condition = condition_match.group(1)
    assert "github.event_name == 'workflow_dispatch'" in condition
    assert f"github.ref == '{branch}'" in condition
    assert "needs.build-push.result == 'success'" in condition
    assert "needs.lifecycle-authorization.result == 'success'" in condition
    assert (
        re.search(r"github\.event_name\s*(?:==|!=)\s*'push'", condition)
        is None
    )
    assert "always()" not in condition
    assert "needs: [build-push, lifecycle-authorization]" in deploy_job


def test_customer_auth_overlays_share_issuer_and_select_stage_jwks() -> None:
    staging = (
        ROOT / "k8s/overlays/staging/foundation/configmap-patch.yaml"
    ).read_text(encoding="utf-8")
    production = (
        ROOT / "k8s/overlays/production/foundation/configmap-patch.yaml"
    ).read_text(encoding="utf-8")

    issuer = 'CUSTOMER_JWT_ISSUER: "https://api.oficina-workshop.com.br"'
    assert issuer in staging
    assert issuer in production
    assert (
        'CUSTOMER_JWT_JWKS_URL: "https://api.oficina-workshop.com.br/hml/'
        '.well-known/jwks.json"'
    ) in staging
    assert (
        'CUSTOMER_JWT_JWKS_URL: "https://api.oficina-workshop.com.br/prd/'
        '.well-known/jwks.json"'
    ) in production
    assert 'CUSTOMER_JWT_AUDIENCE: "auto-shop-api"' in staging
    assert 'CUSTOMER_JWT_AUDIENCE: "auto-shop-api"' in production


def test_documented_ssm_jwt_contract_matches_published_parameters() -> None:
    adr = (
        ROOT
        / "docs/architecture/decisions/ADR-0071-infraestrutura-cloud-fase-3.md"
    ).read_text(encoding="utf-8")
    infrastructure_readme = (ROOT / "infra/aws/README.md").read_text(
        encoding="utf-8"
    )

    assert "/auto-shop/staging/auth/customer-token/function-arn/hml" in adr
    assert "/auto-shop/staging/auth/customer-token/function-arn/prd" in adr
    assert "/auto-shop/staging/auth/customer-jwt/issuer" not in adr
    assert "lambda-auth-hml" in infrastructure_readme
    assert "lambda-auth-prd" in infrastructure_readme
    assert "customer-cpf-auth-homolog" not in infrastructure_readme


def test_registry_decision_documents_authenticated_private_ecr_mirroring() -> None:
    deployment = (ROOT / "docs/deployment.md").read_text(encoding="utf-8")
    cd_docs = (ROOT / ".github/CD.md").read_text(encoding="utf-8")
    adr = (
        ROOT / "docs/architecture/decisions/ADR-0079-registry-privado-ecr.md"
    ).read_text(encoding="utf-8")

    assert "authenticated GHCR" in deployment
    assert "private ECR" in deployment
    assert "anonymous pull" not in deployment.lower()
    assert "pull anônimo" not in cd_docs.lower()
    assert "repositório privado ECR" in cd_docs
    assert "supersedes" in adr.lower()
    assert "GITHUB_TOKEN" in adr
    assert "ECR" in adr
