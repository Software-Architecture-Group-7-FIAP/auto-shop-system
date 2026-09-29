#!/usr/bin/env bash
# Bash deploy for CI/CD (staging/production). Local deploy continues to use deploy.ps1.
set -euo pipefail

ENVIRONMENT="${1:?environment (staging|production)}"
IMAGE_REFERENCE="${2:?immutable image reference}"
CONFIRM_PRODUCTION="${3:-}"

NAMESPACE="auto-shop"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OVERLAY_ROOT="${REPO_ROOT}/k8s/overlays/${ENVIRONMENT}"

if [[ "${ENVIRONMENT}" != "staging" && "${ENVIRONMENT}" != "production" ]]; then
  echo "Only staging and production are supported in deploy.sh"
  exit 1
fi

if [[ "${ENVIRONMENT}" == "production" && "${CONFIRM_PRODUCTION}" != "yes" ]]; then
  echo "Production deploy requires explicit confirmation (pass 'yes' as third argument)."
  exit 1
fi

is_release_image() {
  local ref="$1"
  [[ "${ref}" =~ @sha256:[0-9a-fA-F]{64}$ ]] && return 0
  [[ "${ref}" =~ :sha-[0-9a-fA-F]{7,40}$ ]] && return 0
  [[ "${ref}" =~ :[0-9a-fA-F]{7,64}$ ]] && return 0
  return 1
}

if ! is_release_image "${IMAGE_REFERENCE}"; then
  echo "Image reference must use digest or commit-SHA tag (optional sha- prefix)."
  exit 1
fi

command -v kubectl >/dev/null

if [[ ! -d "${OVERLAY_ROOT}" ]]; then
  echo "Overlay not found: ${OVERLAY_ROOT}"
  exit 1
fi

release_suffix() {
  printf '%s' "${IMAGE_REFERENCE}" | sha256sum | awk '{print substr($1,1,12)}'
}

MIGRATION_JOB="auto-shop-migrate-$(release_suffix)"
TEMP_FILES=()

cleanup() {
  for f in "${TEMP_FILES[@]:-}"; do
    rm -f "${f}"
  done
}
trap cleanup EXIT

render_phase() {
  local phase="$1"
  local rendered
  rendered="$(kubectl kustomize "${OVERLAY_ROOT}/${phase}")"
  rendered="${rendered//registry.example.com\/auto-shop-system:__IMAGE_TAG__/${IMAGE_REFERENCE}}"
  rendered="${rendered//auto-shop-system:__IMAGE_TAG__/${IMAGE_REFERENCE}}"
  if [[ "${phase}" == "migration" ]]; then
    rendered="${rendered//name: auto-shop-migrate/name: ${MIGRATION_JOB}}"
  fi
  if grep -q '__IMAGE_TAG__' <<< "${rendered}"; then
    echo "Unresolved __IMAGE_TAG__ in ${ENVIRONMENT}/${phase}"
    exit 1
  fi
  printf '%s' "${rendered}"
}

apply_phase() {
  local phase="$1"
  local tmp
  tmp="$(mktemp)"
  TEMP_FILES+=("${tmp}")
  render_phase "${phase}" > "${tmp}"
  kubectl apply --filename "${tmp}"
}

assert_secret_key() {
  local key="$1"
  local b64
  b64="$(kubectl get secret auto-shop-secrets --namespace "${NAMESPACE}" \
    --output "jsonpath={.data.${key}}" 2>/dev/null || true)"
  if [[ -z "${b64}" ]]; then
    echo "Secret auto-shop-secrets missing key ${key}"
    exit 1
  fi
}

ensure_secret() {
  kubectl get secret auto-shop-secrets --namespace "${NAMESPACE}" --output name >/dev/null
  for key in DATABASE_URL SECRET_KEY INVERTEXTO_API_TOKEN SMTP_USER SMTP_PASSWORD; do
    assert_secret_key "${key}"
  done
  local tls_secret="auto-shop-tls"
  if [[ "${ENVIRONMENT}" == "staging" ]]; then
    tls_secret="staging-auto-shop-tls"
  fi
  kubectl get secret "${tls_secret}" --namespace "${NAMESPACE}" --output name >/dev/null
}

wait_migration() {
  if ! kubectl wait --for=condition=complete "job/${MIGRATION_JOB}" \
    --namespace "${NAMESPACE}" --timeout=300s; then
    kubectl logs "job/${MIGRATION_JOB}" --namespace "${NAMESPACE}" --tail=100 2>&1 \
      | sed -E 's#(postgres(ql)?://)[^[:space:]]+#\1[REDACTED]#Ig' || true
    exit 1
  fi
}

smoke_test() {
  local port=18000
  kubectl port-forward --namespace "${NAMESPACE}" service/auto-shop-backend-service "${port}:80" \
    >/tmp/auto-shop-pf.log 2>&1 &
  local pf_pid=$!
  trap 'kill "${pf_pid}" 2>/dev/null || true; cleanup' EXIT
  for _ in $(seq 1 30); do
    if curl --fail --silent "http://127.0.0.1:${port}/health/live" >/dev/null \
      && curl --fail --silent "http://127.0.0.1:${port}/health/ready" >/dev/null \
      && curl --fail --silent "http://127.0.0.1:${port}/docs" >/dev/null; then
      kill "${pf_pid}" 2>/dev/null || true
      trap cleanup EXIT
      return 0
    fi
    sleep 1
  done
  cat /tmp/auto-shop-pf.log
  exit 1
}

kubectl apply --filename "${REPO_ROOT}/k8s/base/foundation/namespace.yaml"
ensure_secret
apply_phase foundation
apply_phase migration
wait_migration
apply_phase app
kubectl rollout status deployment/auto-shop-backend --namespace "${NAMESPACE}" --timeout=300s
apply_phase ingress
smoke_test
echo "Auto Shop ${ENVIRONMENT} deployment completed successfully."
