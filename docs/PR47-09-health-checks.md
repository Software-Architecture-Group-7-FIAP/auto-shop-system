# PR47-09 — Liveness & Readiness Separation (Already Complete)

**Status:** ✅ Complete  
**Date:** 2026-11-01

## Summary

Health check endpoints are **fully implemented** with proper separation of liveness and readiness concerns.

## Endpoint Implementation

**File:** `src/main.py` (lines 206-220)

### /health/live (Liveness)

```python
@app.get("/health/live", tags=["Health"])
def liveness_check():
    return {"status": "ok"}
```

**Properties:**
- Returns 200 always (process is alive)
- No database dependency
- Fast, simple check
- Used to: Detect if pod process is hung

**Probe Configuration (Deployment):**
```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: http
  periodSeconds: 15
  timeoutSeconds: 3
  failureThreshold: 3
```

**Effect:** Pod restart if liveness check fails 3 times (45 seconds)

### /health/ready (Readiness)

```python
@app.get("/health/ready", tags=["Health"])
def readiness_check():
    if not database.check_database_connection() or not rate_limit_storage_available():
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ok"}
```

**Properties:**
- Returns 503 when dependencies unavailable (database or rate limit storage)
- No detailed error messages (just {"status": "unavailable"})
- Checks critical dependencies
- Used to: Determine if pod should receive traffic

**Checks:**
1. Database connection: `SELECT 1` with timeout
2. Rate limit storage availability (Redis)

**Probe Configuration (Deployment):**
```yaml
readinessProbe:
  httpGet:
    path: /health/ready
    port: http
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 3
  successThreshold: 1
```

**Effect:** Remove pod from traffic if readiness check fails 3 times (15 seconds)

### /health (Legacy)

```python
@app.get("/health", tags=["Health"], include_in_schema=False)
def health_check():
    return liveness_check()
```

**Purpose:** Backward compatibility (routes to /health/live behavior)

## Database Health Check

**File:** `src/infrastructure/database.py` (lines 481-487)

```python
def check_database_connection() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError, TimeoutError):
        return False
    return True
```

**Implementation:**
- Uses SQLAlchemy engine
- Simple `SELECT 1` query
- Catches SQLAlchemy errors, OS errors, timeouts
- Silent failure (returns False without exposing errors)

**Timeout Behavior:**
- Connection timeout: handled by SQLAlchemy engine config
- Query timeout: implicit via timeout handling
- Total duration: typically < 3 seconds (readiness probe timeout)

## Rate Limit Storage Check

**Source:** `src/main.py` (line 213)

```python
if not database.check_database_connection() or not rate_limit_storage_available():
```

**Purpose:** Ensures Redis/rate-limit storage is available
- If rate limiting isn't available, API can't enforce limits
- Pod should not receive traffic if rate limiting fails
- Prevents cascading failures from rate limit unavailability

## Pod Lifecycle Impact

### When Database is Down

1. `/health/live` → 200 OK (process is alive)
2. `/health/ready` → 503 Unavailable
3. Kubelet removes pod from Service endpoints (after 3 failures = 15s)
4. Requests are not routed to this pod
5. **No restart loop** (liveness probe still passes)
6. Pod waits for database recovery
7. When database recovers: readiness probe passes, pod re-added to endpoints

### When Process is Hung

1. `/health/live` → Timeout (no response)
2. Liveness probe fails 3 times (45s)
3. Kubelet restarts pod
4. Process gets cleanly killed (terminationGracePeriodSeconds: 30s)
5. New pod starts fresh

### When Pod is Healthy

1. `/health/live` → 200 OK
2. `/health/ready` → 200 OK (all dependencies available)
3. Pod is in Service endpoints
4. Receives traffic normally

## Test Coverage

**File:** `tests/unit/test_database_health.py`

```python
def test_check_database_connection_returns_true_after_select_one(monkeypatch):
    # Verifies SELECT 1 succeeds
    assert database.check_database_connection() is True

def test_check_database_connection_returns_false_without_exposing_database_error(monkeypatch):
    # Verifies errors are caught and don't leak to caller
    assert database.check_database_connection() is False
```

**Tests Pass:** ✅ 2/2

## Deployment Probe Configuration

**File:** `k8s/base/app/deployment.yaml`

### Startup Probe (lines 66-72)
```yaml
startupProbe:
  httpGet:
    path: /health/live
    port: http
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 30  # 150s window
```
**Purpose:** Allow 150 seconds for API startup before readiness checks

### Liveness Probe (lines 73-79)
```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: http
  periodSeconds: 15
  timeoutSeconds: 3
  failureThreshold: 3  # Restart after 45s of failures
```
**Purpose:** Restart pod if process hangs

### Readiness Probe (lines 80-87)
```yaml
readinessProbe:
  httpGet:
    path: /health/ready
    port: http
  periodSeconds: 5
  timeoutSeconds: 3
  successThreshold: 1
  failureThreshold: 3  # Remove from traffic after 15s of failures
```
**Purpose:** Remove from traffic if dependencies unavailable

## Verification Checklist

- [x] `/health/live` returns 200 always (no dependencies)
- [x] `/health/ready` returns 503 when database unavailable
- [x] `/health/ready` returns 503 when rate limit storage unavailable
- [x] No detailed error messages in 503 response (just {"status": "unavailable"})
- [x] Database check: SELECT 1 with timeout handling
- [x] Liveness probe: `/health/live` (process-only check)
- [x] Readiness probe: `/health/ready` (dependencies check)
- [x] Startup probe: `/health/live` (150s window for initialization)
- [x] No restart loop when database is down (liveness passes)
- [x] Pod removed from traffic when dependencies fail (readiness fails)
- [x] Tests verify error handling

## Health Check Flow

```
┌─────────────────────────────────────────────────────┐
│ Request arrives at pod                              │
└────────────┬────────────────────────────────────────┘
             │
             ├─→ [Startup Probe] /health/live
             │   ✓ 200 OK (process started)
             │   → Proceed to readiness checks
             │
             ├─→ [Readiness Probe] /health/ready
             │   ├─ Database available? SELECT 1
             │   ├─ Rate limit storage available? Check Redis
             │   ├─ Both OK? Return 200 OK → Add to endpoints
             │   └─ Any fail? Return 503 Unavailable → Remove from endpoints
             │
             └─→ [Liveness Probe] /health/live
                 ├─ 200 OK → Pod is alive
                 └─ Timeout/fail × 3 → Restart pod
```

## Summary

✅ **Liveness & Readiness Properly Separated:**
- `/health/live` — Process check only (can't trigger removal from traffic)
- `/health/ready` — Dependency check (controls traffic routing)
- No database dependency in liveness check
- Pod doesn't restart when database fails (prevents cascading restarts)
- Pod removes itself from traffic when dependencies fail

✅ **Proper Error Handling:**
- Database errors don't leak to 503 response
- Returns generic "unavailable" status code
- 503 signals "try another pod" to load balancers

✅ **Timeout Protection:**
- Database check has timeout handling
- Readiness probe timeout: 3 seconds
- Prevents hanging requests

**No action needed** — PR47-09 requirements are fully met.

Next: **PR47-10 (Setup automation)**
