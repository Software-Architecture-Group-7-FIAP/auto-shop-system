# PR47-05 — Immutable Images with SHA Tagging (Already Complete)

**Status:** ✅ Complete  
**Date:** 2026-11-01

## Summary

Image immutability is **fully implemented** across the build, deployment, and execution layers.

## Image Tagging Strategy

### Build-time (CI)
**Workflow:** `.github/workflows/reusable-build-push.yml`

```bash
# Tag = first 7 chars of commit SHA
tag="sha-${GITHUB_SHA::7}"
reference="ghcr.io/${repo}:${tag}"
# Example: ghcr.io/auto-shop-system:sha-a1b2c3d
```

### Local Development
**Deploy:** `k8s/scripts/deploy.ps1`

```bash
./deploy.ps1 -Environment local
# Generates: auto-shop-system:local-{random-12-chars}
# Builds image locally and loads into Kind/Docker Desktop
```

### Staging & Production
**Deploy:** `k8s/scripts/deploy.ps1`

```bash
./deploy.ps1 -Environment staging -ImageReference ghcr.io/auto-shop-system:sha-a1b2c3d
./deploy.ps1 -Environment production -ImageReference ghcr.io/auto-shop-system:sha-a1b2c3d -ConfirmProduction
```

**Requirements:**
- Must be immutable format (digest or SHA tag)
- Validated by `Test-ReleaseImage()` function
- Accepted formats:
  - `image@sha256:[64-hex-chars]` (full digest)
  - `image:sha-[7-40 hex-chars]` (commit SHA)
  - `image:[7-64 hex-chars]` (generic hex tag)

## Container Security (UID/GID)

### Dockerfile Setup
**File:** `Dockerfile` lines 39-51

```dockerfile
# Non-system UID/GID (10001)
RUN groupadd --gid 10001 appgroup \
    && useradd --uid 10001 --gid 10001 --create-home appuser

# All files owned by 10001:10001
COPY --chown=10001:10001 src/ ./src
COPY --chown=10001:10001 alembic/ ./alembic

# Run as non-root
USER 10001:10001
```

### Kubernetes Deployment
**File:** `k8s/base/app/deployment.yaml` lines 33-39

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  runAsGroup: 10001
  fsGroup: 10001
  seccompProfile:
    type: RuntimeDefault
```

### Kubernetes Migration Job
**File:** `k8s/base/migration/migrate-job.yaml` lines 24-30

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  runAsGroup: 10001
  fsGroup: 10001
  seccompProfile:
    type: RuntimeDefault
```

**Both use same UID/GID (10001) and seccomp profile.**

## Image Injection in Kustomize

### Template Reference
**Pattern:** `__IMAGE_TAG__` placeholder in manifests

```yaml
# Deployment and Job both use same placeholder
image: auto-shop-system:__IMAGE_TAG__
```

### Runtime Replacement
**Deploy Script:** `k8s/scripts/deploy.ps1` lines 88-95

```powershell
$rendered = $rendered.Replace(
    "auto-shop-system:__IMAGE_TAG__",
    $ImageReference
)
```

## Security Properties

✅ **Container Security:**
- Runs as non-root user (UID 10001)
- Read-only root filesystem
- No capabilities (drop: ALL)
- No privilege escalation allowed
- seccomp: RuntimeDefault

✅ **Image Immutability:**
- Commit SHA in tag prevents accidental tag reuse
- New build = new commit = new tag = new PodTemplate
- Rolling update automatically triggered on new image
- No `latest` tag (prevents mutation)
- No pull policies that accept mutable tags

✅ **Consistency:**
- API Deployment and Migration Job use identical image
- Same UID/GID between Dockerfile and manifests
- Same seccompProfile and capabilities in both workloads

## Deployment Flow

1. **Build** (GitHub Actions):
   - Build image with tag `sha-{commit-short-sha}`
   - Push to GHCR
   
2. **Deploy Local**:
   - Generate random tag `local-{guid}`
   - Build locally, load into Kind/Docker Desktop
   
3. **Deploy Staging/Production**:
   - Pass image reference (must be immutable format)
   - Validate via `Test-ReleaseImage()`
   - Replace `__IMAGE_TAG__` with real reference
   - Apply manifests (triggers rolling update)

## Verification

### Test Image Tag
```powershell
# Valid (immutable)
./deploy.ps1 -Environment staging -ImageReference ghcr.io/auto-shop-system:sha-a1b2c3d
./deploy.ps1 -Environment staging -ImageReference ghcr.io/auto-shop-system@sha256:abc...xyz

# Invalid (would be rejected)
./deploy.ps1 -Environment staging -ImageReference ghcr.io/auto-shop-system:latest
# Error: "Staging and production require an immutable image digest or hexadecimal tag"
```

## Test Coverage

- Dockerfile creates UID/GID 10001 ✓
- Security context uses UID/GID 10001 ✓
- Image tag enforced immutable for prod ✓
- Image replacement works for both Deployment and Job ✓
- No mutable tags allowed ✓

## Conclusion

**No action needed** — PR47-05 requirements are fully implemented:
- Images tagged by commit SHA
- Non-system UID/GID (10001) in both Dockerfile and manifests
- Immutability enforced for staging/production
- Security hardening (seccomp, capabilities, read-only FS)

Next: **PR47-06 (TLS enforcement)**
