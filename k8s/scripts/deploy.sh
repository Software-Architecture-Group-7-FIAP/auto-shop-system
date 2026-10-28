#!/usr/bin/env bash
# Bash deploy for CI/CD (staging/production). Local NGINX Ingress remains in deploy.ps1.
set -euo pipefail

if [[ ! -d /dev/shm || ! -w /dev/shm ]]; then
  echo "A writable tmpfs at /dev/shm is required for deployment temporary files." >&2
  exit 1
fi
export TMPDIR=/dev/shm
umask 077

ENVIRONMENT="${1:?environment (staging|production)}"
IMAGE_REFERENCE="${2:?immutable image reference}"
CONFIRM_PRODUCTION="${3:-}"
MIGRATION_DATABASE_SECRET_ARN="${MIGRATION_DATABASE_SECRET_ARN:-}"

case "${ENVIRONMENT}" in
  staging) NAMESPACE="auto-shop-hml" ;;
  production) NAMESPACE="auto-shop-prd" ;;
esac
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OVERLAY_ROOT="${REPO_ROOT}/k8s/overlays/${ENVIRONMENT}"

if [[ "${ENVIRONMENT}" != "staging" && "${ENVIRONMENT}" != "production" ]]; then
  echo "Only staging and production are supported in deploy.sh"
  exit 1
fi

if [[ ! "${MIGRATION_DATABASE_SECRET_ARN}" =~ ^arn:aws:secretsmanager:[a-z0-9-]+:[0-9]{12}:secret:.+ ]]; then
  echo "A valid migration database secret ARN from the approved SSM parameter is required."
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
  rendered="${rendered//__MIGRATION_DATABASE_SECRET_ARN__/${MIGRATION_DATABASE_SECRET_ARN}}"
  if [[ "${phase}" == "migration" ]]; then
    rendered="${rendered//name: auto-shop-migrate/name: ${MIGRATION_JOB}}"
  fi
  if grep -Eq '__IMAGE_TAG__|__MIGRATION_DATABASE_SECRET_ARN__' <<< "${rendered}"; then
    echo "Unresolved deployment placeholder in ${ENVIRONMENT}/${phase}"
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
}

assert_redis_secret_key() {
  local key="$1"
  local b64
  b64="$(kubectl get secret auto-shop-redis-credentials --namespace "${NAMESPACE}" \
    --output "jsonpath={.data.${key}}" 2>/dev/null || true)"
  if [[ -z "${b64}" ]]; then
    echo "Secret auto-shop-redis-credentials missing key ${key}"
    exit 1
  fi
}

ensure_redis_credentials() {
  if kubectl get secret auto-shop-redis-credentials --namespace "${NAMESPACE}" \
    --output name >/dev/null 2>&1; then
    assert_redis_secret_key REDIS_PASSWORD
    assert_redis_secret_key REDIS_URL
    return
  fi

  command -v openssl >/dev/null
  local password_file url_file redis_password redis_url
  password_file="$(mktemp)"
  url_file="$(mktemp)"
  TEMP_FILES+=("${password_file}" "${url_file}")
  redis_password="$(openssl rand -hex 32)"
  redis_url="redis://:${redis_password}@auto-shop-redis:6379/0"
  printf '%s' "${redis_password}" > "${password_file}"
  printf '%s' "${redis_url}" > "${url_file}"
  kubectl create secret generic auto-shop-redis-credentials \
    --namespace "${NAMESPACE}" \
    --from-file="REDIS_PASSWORD=${password_file}" \
    --from-file="REDIS_URL=${url_file}" \
    --dry-run=client --output=yaml | kubectl apply --filename=-
  unset redis_password redis_url
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

kubectl create namespace "${NAMESPACE}" --dry-run=client --output=yaml | kubectl apply --filename=-
ensure_secret
ensure_redis_credentials
apply_phase foundation
apply_phase migration
wait_migration
apply_phase app
kubectl rollout status deployment/auto-shop-redis --namespace "${NAMESPACE}" --timeout=180s
kubectl rollout status deployment/auto-shop-backend --namespace "${NAMESPACE}" --timeout=300s
smoke_test
echo "Auto Shop ${ENVIRONMENT} deployment completed successfully."
