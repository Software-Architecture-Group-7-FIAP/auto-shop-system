from pathlib import Path


ROOT = Path(__file__).parents[2]
CUSTOMER_CONFIG_KEYS = (
    "CUSTOMER_JWT_JWKS_URL",
    "CUSTOMER_JWT_ISSUER",
    "CUSTOMER_JWT_AUDIENCE",
    "CUSTOMER_JWT_CLOCK_SKEW_SECONDS",
    "CUSTOMER_JWT_JWKS_TIMEOUT_SECONDS",
    "CUSTOMER_JWT_JWKS_CACHE_SECONDS",
    "SERVICE_ORDER_EVENT_BUS_NAME",
)


def test_kubernetes_and_terraform_publish_customer_identity_configuration():
    configmap = (ROOT / "k8s/base/foundation/configmap.yaml").read_text(encoding="utf-8")
    terraform = (ROOT / "infra/k8s.tf").read_text(encoding="utf-8")
    variables = (ROOT / "infra/variables.tf").read_text(encoding="utf-8")

    for key in CUSTOMER_CONFIG_KEYS:
        assert key in configmap
        assert key in terraform
    assert "customer_jwt_jwks_url deve ser HTTPS e não pode ficar vazio" in variables
    assert "customer_jwt_issuer não pode ficar vazio" in variables
    assert "service_order_event_bus_name não pode ficar vazio" in variables


def test_customer_identity_settings_are_configured_in_local_and_staging_overlays():
    local_overlay = (ROOT / "k8s/overlays/local/foundation/configmap-patch.yaml").read_text(
        encoding="utf-8"
    )
    staging_overlay = (
        ROOT / "k8s/overlays/staging/foundation/configmap-patch.yaml"
    ).read_text(encoding="utf-8")

    for key in CUSTOMER_CONFIG_KEYS:
        assert f"{key}:" in local_overlay
        assert f"{key}:" in staging_overlay
    assert 'CUSTOMER_JWT_JWKS_URL: "https://' in staging_overlay
    assert 'CUSTOMER_JWT_ISSUER: "https://' in staging_overlay
    assert 'SERVICE_ORDER_EVENT_BUS_NAME: ""' not in staging_overlay


def test_ci_and_aws_example_use_ssm_for_customer_auth_lambda():
    ci_workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    aws_tfvars_example = (ROOT / "infra/aws/terraform.tfvars.example").read_text(
        encoding="utf-8"
    )
    aws_readme = (ROOT / "infra/aws/README.md").read_text(encoding="utf-8")

    for key in (
        "customer_jwt_jwks_url",
        "customer_jwt_issuer",
        "service_order_event_bus_name",
    ):
        assert ci_workflow.count(f"-var={key}=") == 2
    assert 'upstream_ssm_prefix = "/auto-shop/staging"' in aws_tfvars_example
    assert "auth/customer-token/function-arn/hml" in aws_readme
    assert "auth/customer-token/function-arn/prd" in aws_readme
    assert "Antes do `apply`" in aws_readme


def test_customer_gateway_routes_do_not_use_admin_hs256_authorizer():
    gateway = (ROOT / "infra/aws/api_gateway.tf").read_text(encoding="utf-8")

    assert 'resource "aws_api_gateway_method" "auth_customer_token_post"' in gateway
    assert 'resource "aws_api_gateway_method" "jwks_get"' in gateway
    assert 'resource "aws_api_gateway_method" "customer_any"' in gateway

    customer_method = gateway.split(
        'resource "aws_api_gateway_method" "customer_any"', maxsplit=1
    )[1].split("resource ", maxsplit=1)[0]
    assert 'authorization = "NONE"' in customer_method
    assert "authorizer_id" not in customer_method


def test_gateway_limits_customer_lambda_permissions_to_expected_routes():
    lambda_config = (ROOT / "infra/aws/lambda.tf").read_text(encoding="utf-8")

    assert (
        "${aws_api_gateway_rest_api.main.execution_arn}/"
        "${each.key}/POST/auth/customer/token"
    ) in lambda_config
    assert (
        "${aws_api_gateway_rest_api.main.execution_arn}/"
        "${each.key}/GET/.well-known/jwks.json"
    ) in lambda_config
