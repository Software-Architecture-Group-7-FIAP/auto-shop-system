#!/usr/bin/env bash
set -euo pipefail

namespace="${1:-auto-shop}"
hpa="auto-shop-backend-hpa"
deployment="auto-shop-backend"
load_pod="hpa-load"
started_at=$SECONDS

cleanup() {
  kubectl delete pod "$load_pod" --namespace "$namespace" --ignore-not-found --wait=false >/dev/null 2>&1 || true
  local hpa_manifest
  hpa_manifest="$(mktemp)"
  sed "s/namespace: auto-shop$/namespace: ${namespace}/" k8s/base/app/hpa.yaml >"$hpa_manifest"
  kubectl apply -f "$hpa_manifest" >/dev/null 2>&1 || true
  rm -f "$hpa_manifest"
}
trap cleanup EXIT

report_hpa_progress() {
  local elapsed_seconds="$1"
  echo "::group::HPA state after ${elapsed_seconds}s"
  kubectl get hpa "$hpa" --namespace "$namespace" --output wide 2>&1 || true
  echo "Deployment replicas:"
  kubectl get deployment "$deployment" --namespace "$namespace" \
    --output='custom-columns=NAME:.metadata.name,DESIRED:.spec.replicas,CURRENT:.status.replicas,READY:.status.readyReplicas,AVAILABLE:.status.availableReplicas' 2>&1 || true
  echo "Pod CPU/Memory usage:"
  kubectl top pods --namespace "$namespace" --selector app=auto-shop-backend 2>&1 || echo "Metrics not yet available"
  echo "::endgroup::"
}

wait_for() {
  local description="$1"
  local timeout_seconds="$2"
  shift 2
  local deadline=$((SECONDS + timeout_seconds))
  local next_report_seconds=15

  until "$@"; do
    if (( SECONDS >= deadline )); then
      echo "::error::Timed out waiting for $description"
      report_hpa_progress "$((SECONDS - started_at))"
      kubectl describe hpa "$hpa" --namespace "$namespace" 2>&1 || true
      return 1
    fi
    local elapsed_seconds=$((SECONDS - started_at))
    if (( elapsed_seconds >= next_report_seconds )); then
      report_hpa_progress "$elapsed_seconds"
      next_report_seconds=$((elapsed_seconds + 15))
    fi
    sleep 2
  done
}

has_resource_metrics() {
  kubectl top pods --namespace "$namespace" --selector app=auto-shop-backend >/dev/null 2>&1 || return 1
  kubectl get hpa "$hpa" --namespace "$namespace" --output json \
    | jq -e '[.status.currentMetrics[]? | select(.resource.current.averageUtilization != null) | .resource.name] | sort == ["cpu", "memory"]' >/dev/null
}

has_ready_replicas() {
  local expected="$1"
  kubectl get deployment "$deployment" --namespace "$namespace" --output json \
    | jq -e --argjson expected "$expected" '
        .spec.replicas == $expected
        and (.status.replicas // 0) == $expected
        and (.status.readyReplicas // 0) == $expected
        and (.status.availableReplicas // 0) == $expected
      ' >/dev/null
}

echo "Waiting for baseline: HPA minimum of two ready replicas..."
wait_for "HPA minimum of two ready replicas" 180 has_ready_replicas 2

echo "Waiting for metrics collection..."
wait_for "CPU and memory metrics" 180 has_resource_metrics

echo "::notice::Configuring HPA for scale test: max 3 replicas, CPU target 1%..."
kubectl patch hpa "$hpa" --namespace "$namespace" --type=json \
  -p='[{"op":"replace","path":"/spec/maxReplicas","value":3},{"op":"replace","path":"/spec/metrics/0/resource/target/averageUtilization","value":1},{"op":"replace","path":"/spec/behavior/scaleDown/stabilizationWindowSeconds","value":0}]'

echo "::notice::Starting CPU load generation (4 workers)..."
# Generate intensive CPU load: 4 parallel workers doing arithmetic
kubectl run "$load_pod" --namespace "$namespace" --restart=Never --image=busybox:1.36 -- \
  sh -c 'for i in 1 2 3 4; do (while true; do x=$((i*i*i*i*i*i)); done) & done; wait'

echo "Waiting for HPA to scale up to three replicas (triggered by CPU load)..."
wait_for "HPA scale up to three ready replicas" 240 has_ready_replicas 3

echo "::notice::Load generation complete, scaling down..."
kubectl delete pod "$load_pod" --namespace "$namespace" --wait=true

echo "::notice::Resetting HPA to normal thresholds..."
kubectl patch hpa "$hpa" --namespace "$namespace" --type=json \
  -p='[{"op":"replace","path":"/spec/metrics/0/resource/target/averageUtilization","value":1000},{"op":"replace","path":"/spec/metrics/1/resource/target/averageUtilization","value":1000},{"op":"replace","path":"/spec/behavior/scaleDown/policies/0/value","value":100}]'

echo "Waiting for HPA to scale down to two replicas..."
wait_for "HPA scale down to two ready replicas" 240 has_ready_replicas 2

echo "::notice::HPA scaling verification complete: received metrics and scaled both up and down."
