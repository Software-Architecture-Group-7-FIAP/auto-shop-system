import re
from collections import Counter
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


def test_api_gateway_stage_prefix_is_configured_for_fastapi_root_path():
    app = (ROOT / "src/main.py").read_text(encoding="utf-8")
    settings = (ROOT / "src/config.py").read_text(encoding="utf-8")
    staging_overlay = (
        ROOT / "k8s/overlays/staging/foundation/configmap-patch.yaml"
    ).read_text(encoding="utf-8")
    production_overlay = (
        ROOT / "k8s/overlays/production/foundation/configmap-patch.yaml"
    ).read_text(encoding="utf-8")

    assert "root_path=settings.api_root_path" in app
    assert "api_root_path: str = \"\"" in settings
    assert 'API_ROOT_PATH: "/hml"' in staging_overlay
    assert 'API_ROOT_PATH: "/prd"' in production_overlay


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
    assert "parâmetros SSM upstream listados acima" in aws_readme


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


def test_public_customer_lookup_is_forwarded_through_gateway_without_auth():
    gateway = (ROOT / "infra/aws/api_gateway.tf").read_text(encoding="utf-8")

    assert 'resource "aws_api_gateway_resource" "customers_lookup"' in gateway
    assert 'resource "aws_api_gateway_method" "customers_lookup_post"' in gateway
    assert 'resource "aws_api_gateway_method" "customers_lookup_options"' in gateway
    assert "/api/v1/customers/lookup" in gateway
    assert "aws_api_gateway_integration.customers_lookup_post," in gateway
    assert "aws_api_gateway_integration.customers_lookup_options," in gateway

    customer_lookup_method = gateway.split(
        'resource "aws_api_gateway_method" "customers_lookup_post"', maxsplit=1
    )[1].split("resource ", maxsplit=1)[0]
    assert 'authorization = "NONE"' in customer_lookup_method
    assert "authorizer_id" not in customer_lookup_method

    customer_lookup_integration = gateway.split(
        'resource "aws_api_gateway_integration" "customers_lookup_post"', maxsplit=1
    )[1].split("resource ", maxsplit=1)[0]
    assert 'type                    = "HTTP_PROXY"' in customer_lookup_integration
    assert 'connection_type         = "VPC_LINK"' in customer_lookup_integration


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


def test_regional_waf_uses_one_aggregate_source_ip_cap():
    waf = (ROOT / "infra/aws/waf.tf").read_text(encoding="utf-8")
    regional_acl = waf.split("cloudfront", maxsplit=1)[0]

    assert regional_acl.count("var.waf_regional_rate_limit") == 1
    assert regional_acl.count("rate_based_statement {") == 1
    assert "scope_down_statement" not in regional_acl


def test_waf_hcl_braces_are_balanced():
    waf = (ROOT / "infra/aws/waf.tf").read_text(encoding="utf-8")

    assert waf.count("{") == waf.count("}"), "Unbalanced WAF HCL braces"


def test_deploy_script_requires_complete_arn_values():
    deploy_script = (ROOT / "k8s/scripts/deploy.sh").read_text(encoding="utf-8")

    assert "secret:[A-Za-z0-9/_+=.@-]+$" in deploy_script
    assert "role/[A-Za-z0-9+=,.@_/-]+$" in deploy_script
    assert "assert_pod_identity_agent_ready" in deploy_script
    assert "assert_pod_identity_agent_ready\nkubectl create namespace" in deploy_script


def test_cd_workflows_check_anonymous_image_access_before_aws_authentication():
    workflows = (
        ROOT / ".github/workflows/cd-staging.yml",
        ROOT / ".github/workflows/cd-prod.yml",
    )

    for workflow_path in workflows:
        workflow = workflow_path.read_text(encoding="utf-8")
        assert 'run: docker pull "${IMAGE_REFERENCE}"' in workflow
        assert workflow.index("Verify image is pullable without credentials") < workflow.index(
            "Configure AWS credentials (OIDC)"
        )


def test_ci_and_cd_kubernetes_tools_match_the_staging_baseline():
    ci_workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    staging_workflow = (ROOT / ".github/workflows/cd-staging.yml").read_text(
        encoding="utf-8"
    )
    production_workflow = (ROOT / ".github/workflows/cd-prod.yml").read_text(
        encoding="utf-8"
    )

    assert "version: v1.37.1" in ci_workflow
    assert "version: v1.37.1" in staging_workflow
    assert "version: v1.37.1" in production_workflow
    assert ci_workflow.count("version: v0.32.0") == 2
    assert ci_workflow.count("node_image: kindest/node:v1.36.1") == 2


def test_terraform_block_addresses_are_unique():
    declarations = Counter()
    resource_or_data = re.compile(
        r'^\s*(resource|data)\s+"([^"]+)"\s+"([^"]+)"', re.MULTILINE
    )
    named_blocks = re.compile(r'^\s*(output|variable)\s+"([^"]+)"', re.MULTILINE)

    for terraform_file in (ROOT / "infra").rglob("*.tf"):
        source = terraform_file.read_text(encoding="utf-8")
        module_directory = terraform_file.parent
        declarations.update(
            (module_directory, *declaration)
            for declaration in resource_or_data.findall(source)
        )
        declarations.update(
            (module_directory, kind, name)
            for kind, name in named_blocks.findall(source)
        )

    duplicates = sorted(address for address, count in declarations.items() if count > 1)
    duplicate_addresses = [
        f"{directory.relative_to(ROOT)}: {address[1:]}"
        for directory, *address in duplicates
    ]
    assert not duplicate_addresses, (
        f"Duplicate Terraform block addresses: {duplicate_addresses}"
    )
