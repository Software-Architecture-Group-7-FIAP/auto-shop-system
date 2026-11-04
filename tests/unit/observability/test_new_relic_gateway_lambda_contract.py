from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_gateway_metrics_are_enabled_without_payload_or_identity_logging():
    gateway = (ROOT / "infra/aws/api_gateway.tf").read_text(encoding="utf-8")

    assert "metrics_enabled        = true" in gateway
    assert "data_trace_enabled     = false" in gateway
    access_log = gateway.split("access_log_settings", maxsplit=1)[1].split(
        "depends_on", maxsplit=1
    )[0]
    for field in ("requestId", "requestTime", "httpMethod", "resourcePath", "status"):
        assert field in access_log
    for sensitive_field in (
        "identity.sourceIp",
        "authorization",
        "cookie",
        "requestOverride",
        "authorizer.claims",
        "request.body",
    ):
        assert sensitive_field.lower() not in access_log.lower()


def test_polling_bootstrap_contract_requires_external_id_and_read_only_permissions():
    runbook = (
        ROOT / "docs/observability/new-relic-gateway-lambda.md"
    ).read_text(encoding="utf-8")

    assert "sts:ExternalId" in runbook
    assert "NEW_RELIC_LICENSE_KEY cannot configure" in runbook
    for action in (
        "cloudwatch:GetMetricData",
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListMetrics",
        "apigateway:GET",
        "lambda:ListFunctions",
        "lambda:GetFunctionConfiguration",
        "lambda:ListTags",
    ):
        assert action in runbook
    for forbidden in ("logs:GetLogEvents", "logs:FilterLogEvents", 'Action = "*"'):
        assert forbidden not in runbook


def test_synthetic_auth_workflow_is_manual_hml_only_and_bounded():
    workflow = (
        ROOT / ".github/workflows/new-relic-hml-auth-synthetic.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "push:" not in workflow
    assert "refs/heads/develop" in workflow
    assert "environment: hml" in workflow
    assert "confirm_privacy_contract" in workflow
    assert "confirm_synthetic_identity" in workflow
    assert "HML_SYNTHETIC_CUSTOMER_CPF" in workflow
    assert workflow.count("synthetic_auth.py") == 1
    for forbidden in ("curl -v", "--trace", "response.json", "access_token"):
        assert forbidden not in workflow


def test_lambda_handoff_and_runbook_cover_signals_privacy_and_gaps():
    handoff = (
        ROOT / "docs/observability/lambda-auth-new-relic-handoff.md"
    ).read_text(encoding="utf-8")
    runbook = (
        ROOT / "docs/observability/new-relic-gateway-lambda.md"
    ).read_text(encoding="utf-8")

    for text in (
        "lambda-auth",
        "official New Relic Lambda layer",
        "cold start",
        "distributed tracing",
        "CPF",
        "CNPJ",
        "JWT",
        "Cookie",
        "Authorization",
        "request body",
        "raw Lambda event",
    ):
        assert text in handoff

    for text in (
        "ApiGatewaySample",
        "provider.count",
        "provider.latency",
        "provider.4xxError",
        "provider.5xxError",
        "invocations",
        "errors",
        "duration",
        "cold starts",
        "throttles",
        "five-minute polling",
        "approved HML session",
        "aggregate",
    ):
        assert text in runbook
