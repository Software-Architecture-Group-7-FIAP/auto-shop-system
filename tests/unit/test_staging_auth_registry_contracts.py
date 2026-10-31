from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def test_auth_preflight_policy_matches_lambda_auth_function_names() -> None:
    policy = (ROOT / "infra/aws/github_oidc.tf").read_text(encoding="utf-8")

    assert 'default     = "lambda-auth"' in policy
    assert "function:${var.auth_lambda_function_name}-hml" in policy
    assert "function:${var.auth_lambda_function_name}-prd" in policy
    assert "function:${var.auth_lambda_function_name}-homolog" not in policy
    assert "function:${var.auth_lambda_function_name}-prod" not in policy


@pytest.mark.parametrize("workflow_name", ("cd-staging.yml", "cd-prod.yml"))
def test_deploy_requires_anonymous_ghcr_pull_before_aws_credentials(
    workflow_name: str,
) -> None:
    workflow = (ROOT / ".github/workflows" / workflow_name).read_text(
        encoding="utf-8"
    )

    anonymous_pull_checks = [
        workflow.find('docker manifest inspect "$IMAGE_REFERENCE"'),
        workflow.find('docker pull "${IMAGE_REFERENCE}"'),
    ]
    public_pull_check = min(
        position for position in anonymous_pull_checks if position >= 0
    )
    aws_credentials = workflow.index(
        "role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}"
    )

    assert public_pull_check < aws_credentials
    assert "packages: read" not in workflow
    assert "mirror_ghcr_image_to_ecr.py" not in workflow
    assert "ecr_image" not in workflow


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


def test_registry_decision_documents_public_ghcr_without_ecr_mirroring() -> None:
    deployment = (ROOT / "docs/deployment.md").read_text(encoding="utf-8")
    adr = (
        ROOT / "docs/architecture/decisions/ADR-0074-estrategia-branches-e-ci.md"
    ).read_text(encoding="utf-8")

    assert "GHCR package is intended to remain public" in deployment
    assert "anonymous" in deployment.lower()
    assert "mirror it to the private ECR" not in deployment
    assert "public GHCR" in adr
    assert "private ECR" not in adr
