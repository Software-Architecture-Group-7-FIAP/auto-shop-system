# PR47-08 — Migration Blocking (Already Complete)

**Status:** ✅ Complete  
**Date:** 2026-11-01

## Summary

Migration blocking and serialization are **fully implemented** across deploy script, Kubernetes Job configuration, and CI/CD pipelines.

## Job Configuration

**File:** `k8s/base/migration/migrate-job.yaml`

### Blocking Parameters
```yaml
spec:
  backoffLimit: 1
  activeDeadlineSeconds: 300  # 5 minutes
  ttlSecondsAfterFinished: 600  # Auto-cleanup after 10 minutes
  
  template:
    spec:
      restartPolicy: OnFailure
      terminationGracePeriodSeconds: 30
```

### Key Properties
- **backoffLimit: 1** — Fail immediately after first failure (no retry at Job level)
- **activeDeadlineSeconds: 300** — 5 minute timeout for entire Job execution
- **ttlSecondsAfterFinished: 600** — Auto-cleanup completed Jobs after 10 minutes
- **restartPolicy: OnFailure** — Container-level retry for transient failures
- **terminationGracePeriodSeconds: 30** — Graceful shutdown window

### Image & UID Configuration
```yaml
spec:
  template:
    spec:
      securityContext:
        runAsUser: 10001
        runAsGroup: 10001
        fsGroup: 10001
        
    spec:
      containers:
        - image: auto-shop-system:__IMAGE_TAG__
          # Same image placeholder as API Deployment
          # Same UID/GID as API Deployment (10001)
```

## Job Naming (Recreation Safety)

**Script:** `k8s/scripts/deploy.ps1` (lines 296-298)

```powershell
$lifecycleSessionId = if ($env:LIFECYCLE_SESSION_ID) {
    $env:LIFECYCLE_SESSION_ID
} else {
    "local-$([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))"
}

$releaseSuffix = Get-ReleaseSuffix $ImageReference $lifecycleSessionId
$migrationJobName = "auto-shop-migrate-$releaseSuffix"
```

**Result:**
- Local: `auto-shop-migrate-local-20261101T120000Z-{hash}`
- Staging/Production: `auto-shop-migrate-hml-2026-11-01-{hash}`
- Unique per deployment → safe recreation on redeploy

## Deploy Script Blocking

**Lines 305-310:**

```powershell
# 1. Apply migration Job
Apply-RenderedPhase "migration"

# 2. Wait for completion
Wait-ForMigration  # Throws error if migration fails

# 3. Only proceed if migration succeeded
Apply-RenderedPhase "app"
```

### Wait-ForMigration Function (lines 195-207)

```powershell
function Wait-ForMigration {
    try {
        # Wait for Job to complete (max 300 seconds)
        Invoke-RequiredCommand "kubectl" @(
            "wait", "--for=condition=complete", "job/$migrationJobName",
            "--namespace", $namespace, "--timeout=300s"
        )
    } catch {
        # If Job fails, fetch and sanitize logs, then fail deployment
        $logs = & kubectl logs job/$migrationJobName --namespace $namespace --tail=100
        $sanitized = ($logs -join [Environment]::NewLine) -replace `
            '(?i)(postgres(?:ql)?://)[^\s''"]+', '$1[REDACTED]'
        Write-Error "Migration failed. Sanitized migration logs:`n$sanitized"
        throw  # Prevents API from rolling out
    }
}
```

**Behavior:**
- Waits up to 300 seconds for Job to complete
- Fails deployment if Job fails
- Prevents API rollout if migration fails
- Sanitizes connection strings in logs (redacts database URLs)

## Concurrency Control

### Local Deployment (Mutex)

**Script:** `k8s/scripts/deploy.ps1` (lines 282-285)

```powershell
$mutex = [System.Threading.Mutex]::new($false, "Local\AutoShopDeploy-$Environment")
if (-not $mutex.WaitOne(0)) {
    throw "Another deployment is already running for $Environment"
}
```

**Effect:**
- Per-environment mutex (local, staging, production separate)
- Non-blocking check (WaitOne(0))
- Prevents concurrent deployments to same environment
- Released in finally block (line 330)

### CI/CD Concurrency

**Files:** `.github/workflows/cd-staging.yml`, `.github/workflows/cd-prod.yml` (lines 34-36)

```yaml
concurrency:
  group: cd-staging-${{ github.ref }}
  cancel-in-progress: false
```

**Effect:**
- Groups by branch + environment
- Queues deployments (cancel-in-progress: false)
- Prevents parallel deployments from same branch
- Allows per-branch/environment serialization

## Migration Preflight & Database Unavailability

**Script:** `k8s/base/migration/migrate-job.yaml` (lines 40-57)

```bash
attempt=1
while [ "$attempt" -le 5 ]; do
  migration_status=0
  python -m src.scripts.run_migrations || migration_status=$?
  
  if [ "$migration_status" -eq 0 ]; then
    exit 0  # Success → proceed
  fi
  
  if [ "$migration_status" -ne 10 ]; then
    echo "migration failed"
    exit 20  # Hard failure → do not retry
  fi
  
  # Status 10 = database unavailable (retryable)
  if [ "$attempt" -eq 5 ]; then
    echo "migration failed: database unavailable"
    exit 10  # Give up after 5 attempts
  fi
  
  attempt=$((attempt + 1))
  sleep 5
done
```

**Exit Codes:**
- `0` — Success (proceed to app)
- `10` — Database unavailable after retries (hard fail)
- `20` — Migration error (hard fail, no retry)

**Retry Window:** 5 attempts × 5 seconds = 25 seconds

## External Database Handling

**Configuration:**
- No embedded database in staging/production
- Database URL pre-provisioned in `auto-shop-secrets` Secret
- Migration Job connects to external database
- Preflight retries handle temporary unavailability
- Exit code 10 (unavailable) vs 20 (error) distinction

**Timeout Chain:**
1. activeDeadlineSeconds: 300 (5 minutes max for entire Job)
2. Preflight retry window: 25 seconds (5 attempts)
3. Each attempt: 5 second delay
4. Deploy script timeout: 300s `kubectl wait`

## API Startup Configuration

**File:** `Dockerfile` (line 59)

```dockerfile
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
```

**Configuration:**
- Uvicorn only (no auto-migrations)
- Migrations run in separate Job
- API assumes database is ready
- Health checks validate database readiness

## Log Sanitization

**Script:** `k8s/scripts/deploy.ps1` (line 203)

```powershell
$sanitized = ($logs -join [Environment]::NewLine) -replace `
    '(?i)(postgres(?:ql)?://)[^\s''"]+', '$1[REDACTED]'
```

**Pattern:** Matches and redacts PostgreSQL connection strings
- Before: `postgresql://user:password@host:5432/db`
- After: `postgresql://[REDACTED]`

## Verification Checklist

- [x] Job backoffLimit: 1 (fail immediately)
- [x] activeDeadlineSeconds: 300 (5 minute timeout)
- [x] Job name unique per deployment (releaseSuffix)
- [x] Deploy script waits for Job completion
- [x] API rollout blocked if migration fails
- [x] Migration logs sanitized (database URLs redacted)
- [x] Mutex prevents concurrent local deployments
- [x] CI concurrency group prevents parallel deployments
- [x] Exit code distinction (10 vs 20)
- [x] Preflight retry logic (5 attempts, 25s window)
- [x] UID/GID matches API (10001)
- [x] Same image placeholder as API (__IMAGE_TAG__)

## Testing Migration Blocking

**Test failure blocking:**
```bash
# Simulate migration failure
kubectl set env job/auto-shop-migrate-xxxxx \
  FORCE_MIGRATION_FAILURE=true -n auto-shop

# Run deployment
./deploy.ps1 -Environment local

# Result: Deployment fails, API doesn't roll out
```

**Test database unavailability:**
```bash
# Kill database before migration
kubectl delete pod -l app=postgres -n auto-shop

# Run deployment
./deploy.ps1 -Environment local

# Result: Migration retries 5 times, then fails
# API doesn't roll out
```

**Test concurrency control:**
```bash
# Start first deployment in one shell
./deploy.ps1 -Environment local &

# Try to start second deployment (should fail immediately)
./deploy.ps1 -Environment local
# Result: "Another deployment is already running for local"
```

## Summary

✅ **Migration Blocking:**
- Job waits for completion before API rollout
- Failure prevents API deployment
- 300 second timeout with backoffLimit: 1

✅ **Serialization:**
- Deploy script mutex per environment
- CI concurrency group per branch
- Job naming allows safe recreation

✅ **Error Handling:**
- Database unavailable vs migration error distinction
- Preflight retry logic (5 attempts, 25s)
- Log sanitization (redact connection strings)

✅ **Consistency:**
- UID/GID 10001 matches API
- Image placeholder matches API
- Timeout chain: 300s Job, 5min active deadline, 25s preflight

**No action needed** — PR47-08 requirements are fully met.

Next: **PR47-09 (Liveness/readiness separation)**
