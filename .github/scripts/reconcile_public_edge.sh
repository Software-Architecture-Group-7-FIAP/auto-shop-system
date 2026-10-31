#!/usr/bin/env bash
set -euo pipefail

mode="${EDGE_RECONCILIATION_MODE:-}"
if [[ "$mode" != "active" && "$mode" != "maintenance" ]]; then
  echo "::error::EDGE_RECONCILIATION_MODE must be active or maintenance." >&2
  exit 1
fi

for required_variable in \
  TF_VAR_jwt_secret_arn \
  TF_VAR_enable_custom_domains \
  TF_VAR_disable_execute_api_endpoint; do
  if [[ -z "${!required_variable:-}" ]]; then
    echo "::error::$required_variable is required to preserve the existing public edge configuration." >&2
    exit 1
  fi
done

for boolean_variable in TF_VAR_enable_custom_domains TF_VAR_disable_execute_api_endpoint; do
  if [[ "${!boolean_variable}" != "true" && "${!boolean_variable}" != "false" ]]; then
    echo "::error::$boolean_variable must be the literal true or false." >&2
    exit 1
  fi
done

if [[ ! "$TF_VAR_jwt_secret_arn" =~ ^arn:aws:secretsmanager:us-east-1:[0-9]{12}:secret:.+$ ]]; then
  echo "::error::The configured JWT secret reference must be a Secrets Manager ARN in us-east-1." >&2
  exit 1
fi

TF_VAR_aws_region="us-east-1"
TF_VAR_environment="staging"
TF_VAR_enable_alb_security_group_rules="true"
if [[ "$mode" == "maintenance" ]]; then
  TF_VAR_enable_alb_security_group_rules="false"
fi
export TF_VAR_aws_region TF_VAR_environment TF_VAR_enable_alb_security_group_rules

temp_dir="$(mktemp -d "${RUNNER_TEMP:-/tmp}/edge-lifecycle.XXXXXX")"
chmod 700 "$temp_dir"
trap 'rm -rf -- "$temp_dir"' EXIT
plan_file="$temp_dir/edge.tfplan"

run_terraform() {
  if [[ "$mode" != "maintenance" ]]; then
    terraform "$@"
    return
  fi

  deadline="${TEARDOWN_DEADLINE_UTC:-}"
  if [[ ! "$deadline" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]; then
    echo "::error::TEARDOWN_DEADLINE_UTC must be a canonical UTC timestamp in maintenance mode." >&2
    return 1
  fi
  deadline_epoch="$(date -u -d "$deadline" +%s)" || {
    echo "::error::TEARDOWN_DEADLINE_UTC is not a valid date." >&2
    return 1
  }
  remaining_seconds=$((deadline_epoch - $(date -u +%s)))
  if (( remaining_seconds <= 0 )); then
    echo "::error::The teardown work deadline passed before public-edge Terraform could run." >&2
    return 1
  fi
  timeout --signal=INT --kill-after=15s "$remaining_seconds" terraform "$@"
}

if ! run_terraform -chdir=infra/aws init -input=false -lock-timeout=300s >"$temp_dir/init.log" 2>&1; then
  echo "::error::Public-edge Terraform init failed; private diagnostics were discarded." >&2
  exit 1
fi

if ! run_terraform -chdir=infra/aws plan \
  -input=false \
  -lock-timeout=300s \
  -out="$plan_file" \
  >"$temp_dir/plan.log" 2>&1; then
  echo "::error::Public-edge Terraform plan failed; private diagnostics were discarded." >&2
  exit 1
fi

if ! python3 .github/scripts/terraform_edge_lifecycle_guard.py --mode "$mode" --plan "$plan_file"; then
  exit 1
fi

if ! run_terraform -chdir=infra/aws apply \
  -input=false \
  -auto-approve \
  -lock-timeout=300s \
  "$plan_file" \
  >"$temp_dir/apply.log" 2>&1; then
  echo "::error::Public-edge Terraform apply failed; private diagnostics were discarded." >&2
  exit 1
fi

echo "Public edge reconciled in $mode mode. The API Gateway/CloudFront/domain resources remain outside the Terraform change allowlist."
