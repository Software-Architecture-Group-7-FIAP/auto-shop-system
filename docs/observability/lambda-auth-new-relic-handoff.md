# `lambda-auth` New Relic instrumentation handoff

The `lambda-auth` repository owns the customer authentication Lambda. This
repository must not duplicate its handler, package, Terraform, or deployment.
Issue 4 cannot claim cold start or request-level correlation until that owner
implements and verifies this contract.

## Required implementation

- Install the official New Relic Lambda layer and extension compatible with
  the function's pinned runtime and architecture. Pin the layer version/ARN.
- Wrap the existing handler using the official agent integration and name the
  HML entity `lambda-auth-hml` with environment `hml` and the immutable build
  version.
- Enable distributed tracing only after the privacy tests below pass.
- Obtain the ingest license through the approved AWS Secrets Manager mechanism
  supported by the layer. Never place it in Terraform defaults, environment
  files, source control, Lambda output, or CI logs.
- Preserve native CloudWatch metrics for invocations, errors, duration and
  throttles. Verify New Relic cold start telemetry on a genuinely new execution
  environment.

## Mandatory privacy boundary

Disable capture of the raw Lambda event, request body, response body, query and
path parameters, and request/response headers. Explicitly exclude CPF, CNPJ,
JWT, Cookie, Set-Cookie and Authorization values from attributes, errors,
traces, logs, metrics and tags. Do not log the raw Lambda event or context.

The only synthetic correlation attribute allowed is
`observability.run_id`, copied from `X-Observability-Run-ID` after strict UUID
validation. It must never be derived from a customer document, customer ID,
credential or token. Add tests proving malicious events containing documents,
cookies, authorization headers and JWT responses cannot reach agent APIs or
captured logs.

Publish the resulting immutable function ARN through the existing
`/auto-shop/staging/auth/customer-token/function-arn/hml` SSM contract. The
normal preflight in this repository remains responsible only for verifying the
published function state and network contract.
