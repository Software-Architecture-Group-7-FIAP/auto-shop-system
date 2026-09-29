#!/usr/bin/env bash
set -euo pipefail

namespace="auto-shop"
hpa="auto-shop-backend-hpa"
deployment="auto-shop-backend"
load_pod="hpa-load"

cleanup() {
  kubectl delete pod "$load_pod" --namespace "$namespace" --ignore-not-found --wait=false >/dev/null 2>&1 || true
  kubectl apply -f k8s/base/app/hpa.yaml >/dev/null 2>&1 || true
}
trap cleanup EXIT

wait_for() {
  local description="$1"
  local timeout_seconds="$2"
  shift 2
  local deadline=$((SECONDS + timeout_seconds))
  until "$@"; do
    if (( SECONDS >= deadline )); then
      echo "Timed out waiting for $description" >&2
      kubectl describe hpa "$hpa" --namespace "$namespace" >&2 || true
      return 1
    fi
    sleep 5
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

wait_for "HPA minimum of two ready replicas" 180 has_ready_replicas 2
wait_for "CPU and memory metrics" 180 has_resource_metrics

# Force a low CPU target only in this disposable Kind cluster to exercise scaling.
kubectl patch hpa "$hpa" --namespace "$namespace" --type=json \
  -p='[{"op":"replace","path":"/spec/maxReplicas","value":3},{"op":"replace","path":"/spec/metrics/0/resource/target/averageUtilization","value":1},{"op":"replace","path":"/spec/behavior/scaleDown/stabilizationWindowSeconds","value":0}]'
kubectl run "$load_pod" --namespace "$namespace" --restart=Never --image=busybox:1.36 -- \
  /bin/sh -c 'for i in 1 2 3 4; do while true; do wget -q -O /dev/null http://auto-shop-backend-service/health/live; done & done; wait'
wait_for "HPA scale up to three ready replicas" 240 has_ready_replicas 3

kubectl delete pod "$load_pod" --namespace "$namespace" --wait=true
kubectl patch hpa "$hpa" --namespace "$namespace" --type=json \
  -p='[{"op":"replace","path":"/spec/metrics/0/resource/target/averageUtilization","value":1000},{"op":"replace","path":"/spec/metrics/1/resource/target/averageUtilization","value":1000},{"op":"replace","path":"/spec/behavior/scaleDown/policies/0/value","value":100}]'
wait_for "HPA scale down to two ready replicas" 240 has_ready_replicas 2
echo "HPA received CPU and memory metrics and scaled in both directions."
