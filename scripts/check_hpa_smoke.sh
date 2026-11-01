#!/usr/bin/env bash
set -euo pipefail

namespace="${1:-auto-shop}"
hpa="auto-shop-backend-hpa"
deployment="auto-shop-backend"
started_at=$SECONDS
load_exec_pids=()

stop_load() {
  # kubectl exec (without a TTY) does not reliably propagate client-side
  # termination to the remote process, so killing the local backgrounded
  # `kubectl exec` client is not sufficient on its own. The container image
  # has no pkill/kill binary, so use Python (always present in this image)
  # to find and SIGKILL any process carrying our marker string.
  local pid
  for pid in "${load_exec_pids[@]:-}"; do
    [[ -n "$pid" ]] || continue
    kill "$pid" >/dev/null 2>&1 || true
  done
  load_exec_pids=()

  local pod
  for pod in $(kubectl get pods --namespace "$namespace" --selector app=auto-shop-backend \
    --output=jsonpath='{.items[*].metadata.name}' 2>/dev/null || true); do
    kubectl exec --namespace "$namespace" "$pod" -- python -c "
import os, signal
# Build the marker at runtime (not as one literal) so this scanner's own
# cmdline/source never contains the contiguous marker string and can't
# accidentally match (and SIGKILL) itself.
marker = 'hpa_cpu_load' + '_marker'
self_pid = os.getpid()
for pid in os.listdir('/proc'):
    if not pid.isdigit() or int(pid) == self_pid:
        continue
    try:
        with open(f'/proc/{pid}/cmdline', 'rb') as f:
            cmdline = f.read().decode(errors='replace')
    except (FileNotFoundError, ProcessLookupError):
        continue
    if marker in cmdline:
        try:
            os.kill(int(pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
" >/dev/null 2>&1 || true
  done
}

cleanup() {
  stop_load
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
if ! kubectl patch hpa "$hpa" --namespace "$namespace" --type=json \
  -p='[{"op":"replace","path":"/spec/maxReplicas","value":3},{"op":"replace","path":"/spec/metrics/0/resource/target/averageUtilization","value":1},{"op":"replace","path":"/spec/behavior/scaleDown/stabilizationWindowSeconds","value":0}]'; then
  echo "::error::Failed to patch HPA configuration"
  return 1
fi

echo "::notice::Starting CPU load directly inside backend pods (bypasses network path entirely)..."
# Exec a CPU-bound busy loop into each backend pod's own container. This avoids
# relying on pod-to-pod service networking (which can behave inconsistently
# across CNI/runner environments) and guarantees the exact pods being measured
# by the HPA are the ones generating load.
backend_pods="$(kubectl get pods --namespace "$namespace" --selector app=auto-shop-backend \
  --output=jsonpath='{.items[*].metadata.name}')"
if [[ -z "$backend_pods" ]]; then
  echo "::error::No backend pods found to load"
  return 1
fi
for pod in $backend_pods; do
  kubectl exec --namespace "$namespace" "$pod" -- python -c "
while True:
    pass
" hpa_cpu_load_marker &
  load_exec_pids+=("$!")
done
echo "Started ${#load_exec_pids[@]} load process(es) across pods: $backend_pods"

echo "Waiting for HPA to scale up to three replicas (triggered by CPU load)..."
wait_for "HPA scale up to three ready replicas" 240 has_ready_replicas 3

echo "::notice::Load generation complete, stopping load..."
stop_load

# Metrics-server/HPA have inherent reporting lag (samples can be tens of
# seconds stale), so the HPA may still act on "high CPU" readings for a
# while after the load is actually gone. Restore realistic CPU/memory
# targets now, but deliberately KEEP maxReplicas capped at 3 and
# scaleDown.stabilizationWindowSeconds at 0: this makes any lag-driven
# scale decision harmless (capped at the same 3 we already expect) instead
# of letting a stale "still hot" sample race the cap back up to 10.
echo "::notice::Restoring realistic CPU/memory targets (keeping safety cap at 3 replicas)..."
kubectl patch hpa "$hpa" --namespace "$namespace" --type=json \
  -p='[{"op":"replace","path":"/spec/metrics/0/resource/target/averageUtilization","value":70},{"op":"replace","path":"/spec/metrics/1/resource/target/averageUtilization","value":80}]'

echo "Waiting for HPA to scale down to two replicas..."
wait_for "HPA scale down to two ready replicas" 240 has_ready_replicas 2

echo "::notice::Restoring production HPA configuration (maxReplicas=10, scaleDown stabilization=300s)..."
kubectl patch hpa "$hpa" --namespace "$namespace" --type=json \
  -p='[{"op":"replace","path":"/spec/maxReplicas","value":10},{"op":"replace","path":"/spec/behavior/scaleDown/stabilizationWindowSeconds","value":300},{"op":"replace","path":"/spec/behavior/scaleDown/policies/0/value","value":10}]'

echo "::notice::HPA scaling verification complete: received metrics and scaled both up and down."
