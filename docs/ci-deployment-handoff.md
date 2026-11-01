# Handoff: workflow and migration diagnostics

Updated: 2026-11-01

## Current state

- PR [#166](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/pull/166) is open against `develop`.
- Published branch head is `7740359a1a76b433e66942e70aff6f8b11f98b74` (`fix: unblock migration deployment smoke checks`).
- Latest published CI run [41308974246](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/actions/runs/41308974246) passed every check except `cluster-smoke`.
- CI for the current branch is running after the fixes were published.
- The user authorized publishing the fixes and merging with an approval bypass after required CI checks pass. No merge or HML/PROD deployment has happened yet.
- Local Kind validation now passes migration, seed, API rollout, and HTTP smoke checks after the fixes listed below.

## Root causes found

The failed published run waited all 600 seconds even though Kubernetes had already emitted `BackoffLimitExceeded`. Kubernetes 1.31 and later can first mark a failing Job with the `FailureTarget` condition while it terminates its Pods. The old waiter only recognized `Failed`, so it ignored the early failure state and continued polling.

The Job's migration pod also could not resolve `postgres-service`. The `allow-dns` NetworkPolicy selected the `kube-system` namespace using `name=kube-system`, but the namespace carries the standard label `kubernetes.io/metadata.name=kube-system`. With egress restricted, DNS queries did not reach CoreDNS. A local reproduction logged `database hostname could not be resolved`; each lookup took about 29 seconds, and the five connection retries exhausted the Job.

The full smoke sequence exposed a second network-policy gap: database egress and ingress allowed `backend` and `migrate` pods but omitted the `seed` workload. The seed job therefore resolved PostgreSQL but timed out connecting to port 5432.

## Fixes implemented locally

- Added `k8s/scripts/wait-for-job.sh`, shared by CI and `k8s/scripts/deploy.sh` for HML/PROD. It checks `FailureTarget`, `Failed`, and failed-count versus `backoffLimit`, uses bounded API requests, polls every two seconds, reports recent logs/events every ten seconds, and prints sanitized diagnostics on failure.
- Changed the migration Job to `restartPolicy: Never` and `backoffLimit: 0`. Its explicit five-try database preflight remains the only retry loop, so the kubelet does not restart that loop after it exits.
- Changed the migration preflight to log safe failure categories and retry only transient connectivity errors. Invalid configuration and rejected credentials now fail without consuming all retries. The migration lock now uses `pg_try_advisory_lock`, so another active migration is reported instead of blocking indefinitely.
- Corrected the DNS NetworkPolicy selector to `kubernetes.io/metadata.name: kube-system` and allowed both UDP and TCP port 53.
- Added the `seed` workload to PostgreSQL ingress and egress rules.
- Removed the duplicate local migration Secret reference; the base Job already imports that Secret.
- Added contract tests for early Job failure detection, bounded polling, status/log reporting, migration retries and lock behavior, and network-policy selectors.
- Updated this handoff with the confirmed root causes and validation results.

## Validation completed locally

- Focused pytest set after the final changes: 21 passed. Ruff checks and format checks passed; both deployment Bash scripts passed `bash -n`; workflow YAML parsed; local migration/foundation Kustomize rendered; `git diff --check` passed.
- Built `auto-shop-system:local` and created a disposable Kind v1.36 cluster.
- Reproduced the original migration DNS failure and confirmed the new waiter reported `FailureTarget` and printed the preserved pod logs without waiting 600 seconds.
- After fixing DNS egress, migration completed all Alembic revisions in about seven seconds.
- After allowing seed-to-PostgreSQL traffic, the synthetic seed job completed.
- Backend Deployment rollout succeeded; `/health/live`, `/health/ready`, and `/docs` each returned HTTP 200.
- Deleted the disposable Kind cluster after validation.

## Earlier published changes in PR #166

- `aedb5e6` — avoid injecting `session_token` when dispatching external-repository workflows.
- `e2bad47` — remove time-of-day restrictions from application deployment validation while retaining environment authorization and enabled gates.
- `e1f680b` — align deployment-validator tests with the new contract.
- `435a5e1` — add database NetworkPolicy rules and initial cluster-smoke diagnostics.
- `5dd5d95` — update the seed deployment contract test.
- `7740359` — correct DNS/database NetworkPolicies, fail-fast Job waiting, and migration diagnostics.

The old HML lifecycle runs `#41`, `#42`, and `#43` were canceled during the earlier investigation. Run `#41` had a Kubernetes foundation-plan HTTP 422; `#42` and `#43` refused duplicate lifecycle openings while an opening run remained active. No AWS mutation occurred in those refused runs.

Earlier settings inspection showed HML backend deployment enabled and its AWS role present, while the HML frontend role was missing. Production readiness/cost gates were closed. Recheck those settings before attempting a production deployment; do not force a PROD deploy while those gates remain closed.

## Next steps

1. Wait for all required checks on the current branch.
2. If CI passes, use the previously authorized approval bypass and merge into `develop`.
3. Monitor the resulting HML deployment and confirm the migration and API rollout. Do not force production while its readiness/cost gates are closed.

## Links

- PR #166: https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/pull/166
- Failed CI run 41308974246: https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/actions/runs/41308974246
- Failed `cluster-smoke` logs: https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/actions/runs/41308974246/job/124857282743
