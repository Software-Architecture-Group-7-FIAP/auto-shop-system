#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 3 ]]; then
  echo "Usage: wait-for-job.sh JOB_NAME NAMESPACE TIMEOUT_SECONDS" >&2
  exit 2
fi

job_name="$1"
namespace="$2"
timeout_seconds="$3"
if [[ ! "${timeout_seconds}" =~ ^[0-9]+$ ]]; then
  echo "TIMEOUT_SECONDS must be a positive integer" >&2
  exit 2
fi

redact_output() {
  sed -E \
    -e 's#(postgres(ql)?(\+[^:]*)?://[^:/@[:space:]]+:)[^@/[:space:]]+@#\1[REDACTED]@#gI' \
    -e 's#((password|passwd|token|secret(_key)?|api[_-]?key)[=:][[:space:]]*)[^[:space:],;]+#\1[REDACTED]#gI'
}

dump_job_diagnostics() {
  local pod
  kubectl --request-timeout=5s describe job "${job_name}" --namespace "${namespace}" 2>&1 \
    | redact_output || true

  local pods
  pods="$(kubectl --request-timeout=5s get pods --namespace "${namespace}" \
    --selector="job-name=${job_name}" --output=name 2>/dev/null || true)"
  while IFS= read -r pod; do
    local restart_count
    [[ -n "${pod}" ]] || continue
    kubectl --request-timeout=5s describe "${pod}" --namespace "${namespace}" 2>&1 \
      | redact_output || true
    kubectl --request-timeout=5s logs "${pod}" --namespace "${namespace}" \
      --all-containers=true --prefix --timestamps 2>&1 | redact_output || true
    restart_count="$(kubectl --request-timeout=5s get "${pod}" --namespace "${namespace}" \
      --output='jsonpath={.status.containerStatuses[0].restartCount}' 2>/dev/null || true)"
    if [[ "${restart_count:-0}" =~ ^[1-9][0-9]*$ ]]; then
      kubectl --request-timeout=5s logs "${pod}" --namespace "${namespace}" \
        --all-containers=true --prefix --timestamps --previous 2>&1 | redact_output || true
    fi
  done <<<"${pods}"
}

report_job_progress() {
  local elapsed_seconds="$1"
  local pod
  echo "::group::Kubernetes job ${job_name} progress after ${elapsed_seconds}s"
  kubectl --request-timeout=3s get job "${job_name}" --namespace "${namespace}" \
    --output='custom-columns=NAME:.metadata.name,ACTIVE:.status.active,SUCCEEDED:.status.succeeded,FAILED:.status.failed,CONDITIONS:.status.conditions[*].type' \
    2>&1 | redact_output || true
  kubectl --request-timeout=3s get pods --namespace "${namespace}" \
    --selector="job-name=${job_name}" \
    --output='custom-columns=NAME:.metadata.name,PHASE:.status.phase,RESTARTS:.status.containerStatuses[0].restartCount,WAITING:.status.containerStatuses[0].state.waiting.reason,NODE:.spec.nodeName' \
    2>&1 | redact_output || true

  local pods
  pods="$(kubectl --request-timeout=3s get pods --namespace "${namespace}" \
    --selector="job-name=${job_name}" --output=name 2>/dev/null || true)"
  while IFS= read -r pod; do
    [[ -n "${pod}" ]] || continue
    echo "Recent logs from ${pod}:"
    kubectl --request-timeout=3s logs "${pod}" --namespace "${namespace}" \
      --all-containers=true --prefix --timestamps --since=15s 2>&1 \
      | redact_output || true
  done <<<"${pods}"

  kubectl --request-timeout=3s get events --namespace "${namespace}" \
    --sort-by=.lastTimestamp \
    --output='custom-columns=LAST:.lastTimestamp,TYPE:.type,REASON:.reason,OBJECT:.involvedObject.name,MESSAGE:.message' \
    2>&1 | tail -n 15 | redact_output || true
  echo "::endgroup::"
}

wait_for_job() {
  local deadline=$((SECONDS + timeout_seconds))
  local started_at=$SECONDS
  local next_report_seconds=10

  while (( SECONDS < deadline )); do
    local job_state
    if ! job_state="$(kubectl --request-timeout=5s get job "${job_name}" \
      --namespace "${namespace}" \
      --output='jsonpath={.status.succeeded}{"|"}{.status.failed}{"|"}{.spec.completions}{"|"}{.spec.backoffLimit}{"|"}{range .status.conditions[?(@.status=="True")]}{.type}{","}{end}' 2>&1)"; then
      echo "::error::Could not read Kubernetes job ${job_name}; stopping instead of waiting for the timeout."
      printf '%s\n' "${job_state}" | redact_output
      dump_job_diagnostics
      return 1
    fi

    local succeeded_count failed_count completion_count backoff_limit condition_types
    IFS='|' read -r succeeded_count failed_count completion_count backoff_limit condition_types \
      <<<"${job_state}"
    succeeded_count="${succeeded_count:-0}"
    failed_count="${failed_count:-0}"
    completion_count="${completion_count:-1}"
    backoff_limit="${backoff_limit:-0}"
    condition_types="${condition_types:-}"

    if [[ ! "${succeeded_count}" =~ ^[0-9]+$ || ! "${failed_count}" =~ ^[0-9]+$ \
      || ! "${completion_count}" =~ ^[0-9]+$ || ! "${backoff_limit}" =~ ^[0-9]+$ ]]; then
      echo "::error::Kubernetes job ${job_name} returned an unreadable status; stopping."
      dump_job_diagnostics
      return 1
    fi

    case "${condition_types}" in
      *FailureTarget*|*Failed*)
        echo "::error::Kubernetes job ${job_name} reported failure (${condition_types})."
        dump_job_diagnostics
        return 1
        ;;
    esac
    if (( failed_count > backoff_limit )); then
      echo "::error::Kubernetes job ${job_name} exhausted its retry limit (${failed_count}/${backoff_limit})."
      dump_job_diagnostics
      return 1
    fi
    if (( succeeded_count >= completion_count )); then
      report_job_progress "$((SECONDS - started_at))"
      return 0
    fi

    local elapsed_seconds=$((SECONDS - started_at))
    if (( elapsed_seconds >= next_report_seconds )); then
      report_job_progress "${elapsed_seconds}"
      next_report_seconds=$((elapsed_seconds + 10))
    fi
    sleep 2
  done

  echo "::error::Kubernetes job ${job_name} did not finish within ${timeout_seconds}s."
  dump_job_diagnostics
  return 1
}

wait_for_job
