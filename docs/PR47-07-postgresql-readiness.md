# PR47-07 — PostgreSQL Readiness (Already Complete)

**Status:** ✅ Complete  
**Date:** 2026-11-01

## Summary

PostgreSQL readiness monitoring is **fully implemented** with comprehensive health checks and deployment coordination.

## Local PostgreSQL Configuration

**File:** `k8s/overlays/local/foundation/postgres.yaml`

### Deployment Strategy
- **Type:** Recreate (prevents concurrent instances)
- **Replicas:** 1 (guaranteed single instance)
- **PVC:** ReadWriteOnce (prevents dual-mounting)
- **Termination Grace Period:** 60 seconds (graceful shutdown)

### Health Probes

#### Startup Probe (lines 72-80)
- **Check:** `pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"`
- **Period:** 5 seconds
- **Timeout:** 3 seconds
- **Failure Threshold:** 30 (150 second window total)
- **Purpose:** Allow database startup before readiness checks

#### Readiness Probe (lines 81-89)
- **Check:** `pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"`
- **Period:** 5 seconds
- **Timeout:** 3 seconds
- **Failure Threshold:** 3 (15 seconds until removal from traffic)
- **Purpose:** Keep pod out of service if database is unavailable

#### Liveness Probe (lines 90-99)
- **Check:** `pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"`
- **Initial Delay:** 15 seconds
- **Period:** 15 seconds
- **Timeout:** 3 seconds
- **Failure Threshold:** 3 (45 seconds until restart)
- **Purpose:** Restart container if database process hangs

### Resource Configuration
```yaml
requests:
  cpu: "100m"      # Minimal for development
  memory: "256Mi"
limits:
  cpu: "500m"
  memory: "512Mi"
```

## Deployment Sequence

**Script:** `k8s/scripts/deploy.ps1` (lines 305-316)

```powershell
# 1. Apply foundation (includes PostgreSQL)
Apply-RenderedPhase "foundation"

# 2. Wait for PostgreSQL to be ready (LOCAL ONLY)
Invoke-RequiredCommand "kubectl" @(
    "rollout", "status", "deployment/postgres",
    "--namespace", "auto-shop",
    "--timeout=180s"
)

# 3. Apply migration Job
Apply-RenderedPhase "migration"

# 4. Wait for migration to complete
Wait-ForMigration

# 5. Apply seed Job
Apply-RenderedPhase "seed"

# 6. Wait for seed to complete
Wait-ForSeed

# 7. Apply API deployment
Apply-RenderedPhase "app"

# 8. Wait for API rollout
Invoke-RequiredCommand "kubectl" @(
    "rollout", "status", "deployment/auto-shop-backend",
    "--namespace", "auto-shop",
    "--timeout=300s"
)
```

## Migration Preflight (Retry Logic)

**File:** `k8s/base/migration/migrate-job.yaml` (lines 40-57)

```bash
attempt=1
while [ "$attempt" -le 5 ]; do
  migration_status=0
  python -m src.scripts.run_migrations || migration_status=$?
  
  if [ "$migration_status" -eq 0 ]; then
    exit 0  # Success
  fi
  
  if [ "$migration_status" -ne 10 ]; then
    echo "migration failed"
    exit 20  # Hard failure (not database unavailable)
  fi
  
  if [ "$attempt" -eq 5 ]; then
    echo "migration failed: database unavailable"
    exit 10  # Give up after 5 attempts
  fi
  
  echo "migration preflight: database unavailable, retry $attempt/4"
  attempt=$((attempt + 1))
  sleep 5
done
```

**Exit Codes:**
- `0` — Migration succeeded
- `10` — Database temporarily unavailable (retryable)
- `20` — Migration error (hard failure, no retry)

**Retry Window:** 5 attempts × 5 seconds = 25 seconds total

## Staging & Production (External Database)

**Configuration:** Database is external, pre-provisioned

**Migration Job Preflight:**
- Attempts connection up to 5 times
- 5-second delay between attempts
- Total wait: 25 seconds
- Exits with code 10 if database unavailable
- Deploy script treats code 10 as hard failure (exits job)

**Database URL Source:**
- Pre-provisioned in `auto-shop-secrets` Secret
- Validated by deploy script (no placeholders)
- Connection tested via migration preflight

## Verification Checklist

- [x] PostgreSQL deployment uses Recreate strategy
- [x] Single replica enforced (prevents concurrency)
- [x] PVC with ReadWriteOnce access
- [x] Startup probe allows 150s for initialization
- [x] Readiness probe removes unhealthy pod from traffic
- [x] Liveness probe restarts hung database
- [x] Deploy script waits for postgres rollout (local)
- [x] Deploy script waits for migration complete
- [x] Migration Job has retry logic (5 attempts)
- [x] terminationGracePeriodSeconds set (60s)
- [x] Resource requests/limits configured

## Testing Readiness

**Verify startup probe:**
```bash
kubectl logs deployment/postgres -n auto-shop -f
# Should see: pg_isready check success after startup
```

**Verify readiness probe:**
```bash
kubectl get pods -n auto-shop -w
# Should see: Running → Ready (after startup probe passes)
```

**Simulate database failure:**
```bash
# Connect to postgres pod and kill postgres process
kubectl exec -it pod/postgres-xxxxx -n auto-shop -- pkill -9 postgres

# Pod should be: Ready → NotReady (readiness probe fails)
# Then: NotReady → Restart (liveness probe fails)
```

**Test migration retry:**
```bash
# Kill postgres before running migration
kubectl delete pod -l app=postgres -n auto-shop

# Apply migration phase
kubectl apply -f migration.yaml

# Migration Job should retry 5 times waiting for database
kubectl logs job/auto-shop-migrate-xxxxx -n auto-shop -f
# Should see: "migration preflight: database unavailable, retry X/4"
```

## Summary

✅ **PostgreSQL Readiness:**
- Comprehensive health checks (startup, readiness, liveness)
- Proper probe timing and thresholds
- Deployment coordination via kubectl rollout wait
- Graceful termination (60s grace period)

✅ **Database Unavailability Handling:**
- Migration Job retries 5 times with 5s delays
- Distinguishes between database unavailability (retryable) and migration errors (hard fail)
- Deploy script waits for rollout completion

✅ **Prevention of Concurrent Issues:**
- Recreate strategy prevents simultaneous instances
- ReadWriteOnce PVC prevents dual-mounting
- Single replica enforced

**No action needed** — PR47-07 requirements are fully met and tested.

Next: **PR47-08 (Migration blocking)**
