# PR47-03 — Secret Management

**Status:** ✅ Complete  
**Date:** 2026-11-01

## Changes

Configured environment-specific secret management without example secrets in deployed manifests:

### 1. Example Secrets (Documentation Only)

**Files:** `k8s/examples/`
- `secrets.example.env` — Template for local development
- `secret.example.yaml` — YAML template reference (never applied)

These files are **NOT referenced by Kustomize** and are **never deployed**.

### 2. Local Environment

**Setup:**
```bash
cp k8s/examples/secrets.example.env k8s/overlays/local/secrets.env
# Edit with real local values (ignored by git)
```

**Flow:**
1. `deploy.ps1 -Environment local` reads `k8s/overlays/local/secrets.env` (git-ignored)
2. Generates `DATABASE_URL` from `DB_NAME`, `DB_USER`, `DB_PASSWORD`
3. Creates secret via `kubectl create secret generic auto-shop-secrets --from-env-file` (dry-run → apply)
4. Validates no placeholders in secret values
5. Tests required keys: `DATABASE_URL`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `SECRET_KEY`, `DEMO_ADMIN_PASSWORD`

**Git Safety:** `k8s/overlays/**/secrets.env` ignored in `.gitignore`

### 3. Staging & Production

**Requirement:** Secrets must be pre-provisioned before deployment

**Setup (manual, once per environment):**
```bash
kubectl create secret generic auto-shop-secrets \
  --namespace auto-shop \
  --from-literal=DATABASE_URL='postgresql://user:pass@host:5432/db' \
  --from-literal=SECRET_KEY='<32-char-minimum-random-secret>' \
  --from-literal=INVERTEXTO_API_TOKEN='<real-provider-token>' \
  --from-literal=SMTP_USER='<smtp-user>' \
  --from-literal=SMTP_PASSWORD='<smtp-password>' \
  --from-literal=DEMO_ADMIN_PASSWORD='<demo-password>'
```

Also required:
- TLS secret: `staging-auto-shop-tls` (staging) or `auto-shop-tls` (production)

**Deployment Flow:**
1. `deploy.ps1 -Environment staging` verifies `auto-shop-secrets` exists
2. Tests required keys: `DATABASE_URL`, `SECRET_KEY`, `INVERTEXTO_API_TOKEN`, `SMTP_USER`, `SMTP_PASSWORD`, `DEMO_ADMIN_PASSWORD`
3. Detects and rejects any placeholder values
4. Validates TLS secret exists
5. Proceeds only if all secrets pass validation

### 4. Secret Validation

**Script:** `k8s/scripts/validate-secrets.ps1`

Usage:
```bash
# Local: Validates secrets.env file
.\k8s\scripts\validate-secrets.ps1 -Environment local

# Staging/Production: Validates cluster secret
.\k8s\scripts\validate-secrets.ps1 -Environment staging
.\k8s\scripts\validate-secrets.ps1 -Environment production
```

**Detection:** Rejects values matching patterns:
- `__placeholder__`
- `replace-with-*`, `change-me`
- `seu_`, `sua_`, `your_`
- `example.com`
- `local-development-token`, `local-secret-change-me`

### 5. CI/CD Integration

**CI Validation (PR47-11):**
- Local: Validates rendered manifests for placeholder references
- Staging/Production: Ensures example secrets are NOT in overlays

**No Sensitive Data in Logs:**
- `deploy.ps1` sanitizes logs: `postgresql://...` → `postgresql://[REDACTED]`
- Secret values are never printed
- Only key existence is validated, not values

## Checklist

- [x] Example secrets moved to `k8s/examples/` (not referenced by Kustomize)
- [x] Local creation via `kubectl create secret generic --from-env-file` ✓
- [x] Staging/production require pre-provisioned secret ✓
- [x] Secret validation without printing values ✓
- [x] Placeholder detection in both local and cluster secrets ✓
- [x] Single source for DATABASE_URL generation (from `DB_*` vars) ✓
- [x] `.gitignore` prevents local secrets from committing ✓
- [x] TLS secrets required for staging/production ✓

## Dependencies Met

- ✅ PR47-02 (Kustomize overlays) — secrets are referenced but not defined in manifests
- ✅ PR47-01 (config validation) — config.py validates placeholders at runtime

## Next: PR47-04 (JWT/ECDSA Replacement)
