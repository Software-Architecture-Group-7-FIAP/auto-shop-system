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

    for key in CUSTOMER_CONFIG_KEYS:
        assert key in configmap
        assert key in terraform


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

    assert "/*/POST/auth/customer/token" in lambda_config
    assert "/*/GET/.well-known/jwks.json" in lambda_config
