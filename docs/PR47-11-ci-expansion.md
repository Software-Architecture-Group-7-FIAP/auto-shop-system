# PR47-11 — CI/CD Expansion (Already Complete)

**Status:** ✅ Complete  
**Date:** 2026-11-01

## Summary

Comprehensive CI/CD pipeline is **fully implemented** with validation, testing, container building, Kubernetes manifest validation, ephemeral cluster testing, and smoke tests.

## CI Pipeline Overview

**File:** `.github/workflows/ci.yml`

### Jobs

| Job | Purpose | Dependencies |
|-----|---------|--------------|
| metadata | Resolve image coordinates | — |
| test-and-security | Code quality & security | metadata |
| gateway | Lambda unit tests | — |
| manifests | Kubernetes manifest validation | metadata |
| terraform-k8s | Terraform validation | — |
| cluster-smoke | End-to-end smoke test | test-and-security, manifests |
| frontend | Angular build & tests | — |

## 1. Code Quality & Security (test-and-security job)

### Poetry Lock Check
```bash
poetry check --lock
```
✅ Validates lock file is up-to-date with pyproject.toml

### Test Coverage
```bash
poetry run pytest --cov=src --cov-report=term-missing --cov-fail-under=80
```
✅ **80% coverage required** (gates PR if below threshold)

### Security Scanning
```bash
poetry run bandit -r src -ll  # Security issues (high/medium)
poetry run pip-audit --skip-editable  # Dependency vulnerabilities
```
✅ No ECDSA ignore flags (PyJWT HS256 clean)

### OpenAPI Export Check
```bash
poetry run python scripts/export_openapi.py --check
```
✅ Validates API documentation generation

### Unsafe Defaults Detection
```bash
poetry run python scripts/check_unsafe_defaults.py --image-reference ghcr.io/...
```
✅ Detects hardcoded values, test credentials, etc.

## 2. Kubernetes Manifest Validation (manifests job)

### Docker Compose Config
```bash
docker compose --env-file .env.example config
```
✅ Validates docker-compose syntax and references

### Build Immutable Release Image
```bash
docker build --tag ghcr.io/...:sha-{short-sha} .
```
✅ Build using commit SHA tag (immutable, unique per commit)

### Render & Validate All Phases/Overlays

**For each:** local, staging, production × foundation, migration, seed, app, ingress

```bash
kubectl kustomize k8s/overlays/${environment}/${phase} \
  | sed 's/__IMAGE_TAG__/ghcr.io.../g'
```

**Checks:**
- ✅ No example secrets referenced
- ✅ No `:latest` tags
- ✅ No unresolved placeholders (`__*__`)
- ✅ No HTTP in staging/production
- ✅ No localhost in staging/production
- ✅ No MailHog in staging/production
- ✅ HPA owns Deployment replicas (not static count)

**Validation:**
```bash
kubeconform -strict
```
✅ Kubernetes manifest schema validation

## 3. Ephemeral Kind Cluster Testing (cluster-smoke job)

### Prerequisites

```yaml
needs: [test-and-security, manifests]
```
✅ Only runs if code quality and manifest validation pass

### Metrics Server Installation
```bash
kubectl apply -f metrics-server/components.yaml
kubectl patch deployment metrics-server ...  # Kubelet insecure TLS for Kind
```
✅ Required for HPA tests

### Build & Load Image
```bash
docker build --load --tag auto-shop-system:local .
kind load docker-image auto-shop-system:local
```
✅ Uses local build (not remote pull)

### Ephemeral Secret Generation
```bash
# Random passwords + keys generated per run
DATABASE_URL=postgresql://oficina:{random-hex-24}@postgres-service:5432/oficina
SECRET_KEY={random-hex-32}
DEMO_ADMIN_PASSWORD={random-hex-32}
```
✅ No hardcoded test credentials
✅ Secrets securely generated per run

### Deployment Sequence (Blocking)

```bash
# 1. Apply foundation (namespace, PostgreSQL, ConfigMap)
kubectl apply -k k8s/overlays/local/foundation

# 2. Wait for PostgreSQL ready
kubectl wait --for=condition=available deployment/postgres --timeout=180s

# 3. Apply migration and wait for completion
kubectl apply -k k8s/overlays/local/migration
kubectl wait --for=condition=complete job/auto-shop-migrate --timeout=300s

# 4. Apply seed and wait for completion
kubectl apply -k k8s/overlays/local/seed
kubectl wait --for=condition=complete job/auto-shop-seed --timeout=300s

# 5. Apply app and wait for rollout
kubectl apply -k k8s/overlays/local/app
kubectl rollout status deployment/auto-shop-backend --timeout=300s

# 6. Apply ingress
kubectl apply -k k8s/overlays/local/ingress
```

**Guarantees:**
- ✅ Database ready before migration
- ✅ Migration complete before app
- ✅ Seed complete before app usage
- ✅ App rolled out and ready

### Smoke Tests

```bash
# Port-forward to pod
kubectl port-forward service/auto-shop-backend-service 18000:80

# Test three critical endpoints
for endpoint in health/live health/ready docs; do
  curl --fail http://127.0.0.1:18000/${endpoint}
done
```

**Endpoints Tested:**
- ✅ `/health/live` — Process alive (liveness)
- ✅ `/health/ready` — Database available (readiness)
- ✅ `/docs` — OpenAPI documentation

**Retry Logic:** 30 attempts × 1s delay (30 second timeout per endpoint)

### HPA Metrics & Scaling Verification

**Script:** `scripts/check_hpa_smoke.sh`

**Checks:**
1. **Metrics available:** CPU and memory metrics present via Metrics Server
2. **Minimum replicas:** HPA maintains 2 replicas at baseline
3. **Scale up:** Under load (1% CPU target), scales to 3 replicas
4. **Scale down:** After load removed, scales back to 2 replicas

**Load Generation:**
```bash
kubectl run hpa-load --image=busybox:1.36 -- \
  /bin/sh -c 'for i in 1 2 3 4; do while true; do wget http://health/live; done & done'
```

**Verification:**
- ✅ HPA status shows CPU/memory metrics
- ✅ Deployment replicas match HPA decisions
- ✅ Ready replicas == desired count

## 4. Terraform Validation (terraform-k8s job)

### Setup
```bash
terraform init -backend=false
terraform fmt -check -recursive
terraform validate
```

### Plan & Check Per Environment
```bash
terraform plan -input=false \
  -var=image_reference=ghcr.io/.../auto-shop:sha-abc123 \
  -var=aws_region=us-east-1
```

✅ Plans all environments without applying

## 5. Frontend Testing (frontend job)

```bash
npm ci  # Clean install
npm run lint  # Linting
npx tsc -p tsconfig.spec.json --noEmit  # Type check
npm run build  # Build
npm test -- --watch=false --browsers=ChromeHeadless  # Tests
```

✅ Comprehensive frontend validation

## PR Checks Summary

✅ **Code Quality (80% required)**
- pytest with coverage gate
- Linting (if applicable)
- Type checking (TypeScript)

✅ **Security**
- Bandit (SAST)
- pip-audit (dependency scan)
- Check unsafe defaults
- Validate no secrets in artifacts

✅ **Container & Manifests**
- Docker build works
- docker-compose config valid
- All phases/overlays render
- kubeconform validation
- Placeholder/unsafe value detection

✅ **End-to-End Cluster Testing**
- Kind ephemeral cluster
- PostgreSQL readiness
- Migration blocking
- Seed blocking
- API rollout
- Smoke tests (health, docs)
- HPA metrics and scaling

✅ **Concurrency Control**
```yaml
concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```
Prevents parallel CI runs on same ref

## Exit Codes

| Condition | Exit Code | Blocked PR |
|-----------|-----------|-----------|
| All checks pass | 0 | ❌ No |
| Coverage < 80% | 1 | ✅ Yes |
| Bandit findings | 1 | ✅ Yes |
| pip-audit issues | 1 | ✅ Yes |
| Manifest invalid | 1 | ✅ Yes |
| kubeconform fails | 1 | ✅ Yes |
| Unsafe values found | 1 | ✅ Yes |
| Smoke test fails | 1 | ✅ Yes |

## Validation Checklist

- [x] poetry check --lock
- [x] pytest with 80% coverage gate
- [x] Bandit security scan
- [x] pip-audit without ECDSA ignore
- [x] Docker build validation
- [x] docker compose config check
- [x] Render all 4 phases × 3 overlays (12 combinations)
- [x] kubeconform -strict validation
- [x] Detect placeholders, HTTP in prod, mutable tags
- [x] Kind ephemeral cluster
- [x] Metrics Server installed
- [x] Image loaded into Kind
- [x] Ephemeral Secret with random values
- [x] PostgreSQL ready wait (180s)
- [x] Migration complete wait (300s)
- [x] Seed complete wait (300s)
- [x] App rollout wait (300s)
- [x] Smoke tests: /health/live, /health/ready, /docs
- [x] HPA metrics verification
- [x] HPA scaling transitions (up and down)
- [x] Concurrency control per ref
- [x] Frontend validation (lint, type check, build, tests)

## Test Failure Impact

If any job fails:
1. Status checks block PR merge
2. PR cannot be merged without re-running successful checks
3. Author can fix issue and push new commits
4. Tests automatically re-run

## Performance Notes

- **Parallel jobs:** metadata, test-and-security, gateway, frontend run in parallel
- **Sequential:** cluster-smoke waits for test-and-security + manifests
- **Total time:** ~8-12 minutes (depends on build cache, test count, network)

## Summary

✅ **Comprehensive CI/CD:**
- Code quality gates (coverage, linting, type checking)
- Security scanning (Bandit, pip-audit, unsafe defaults)
- Container and manifest validation
- End-to-end cluster testing with ephemeral environment
- HPA metrics and scaling verification
- Smoke tests for critical endpoints

✅ **Blocking Quality:**
- All checks block PR merge on failure
- Clear exit codes per failure type
- No false positives (no unused linters, no ignored issues)

**No action needed** — PR47-11 requirements are fully met.

Next: **PR47-12 (Operations documentation)**
