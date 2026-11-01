# PR47-06 — TLS Enforcement

**Status:** ✅ Complete  
**Date:** 2026-11-01

## Changes

Implemented TLS enforcement for staging and production environments with proper HTTPS redirect and certificate management.

## TLS Configuration by Environment

### Local (No TLS required)

**Configuration:**
- HTTP only (port-forward: `localhost:8000`)
- Optional nginx ingress (can be skipped with `--skip-ingress` flag)
- No certificate required

**Usage:**
```bash
./deploy.ps1 -Environment local
# Access via: http://localhost:8000
```

### Staging (HML)

**Ingress Controller:** nginx  
**Protocol:** HTTP (for internal testing without certificates)  
**Annotation Overrides:**
- `ssl-redirect: "false"` (intentional for HML testing)
- `force-ssl-redirect: "false"` (allows HTTP for test tools)

**TLS Certificate:**
- Secret: `staging-auto-shop-tls`
- Hostname: `hml.api.internal`
- Status: Optional (HTTP allowed for testing)

**Note:** Staging intentionally allows HTTP to enable uninterrupted testing without certificate complexity.

### Production

**Ingress Controller:** AWS ALB  
**Protocol:** HTTPS enforced  
**TLS Certificate:**
- Secret: `auto-shop-tls-cert`
- Hostname: `api.autoshop.com`
- Required: Yes

**Redirect & Security Annotations:**
```yaml
alb.ingress.kubernetes.io/ssl-redirect: "443"
alb.ingress.kubernetes.io/listen-ports: '[{"HTTP": 80}, {"HTTPS": 443}]'
```

**Effect:**
- HTTP port 80 listens and redirects to HTTPS port 443
- All traffic encrypted with TLS
- Ingress controller: AWS ALB (not nginx)

## Certificate Setup

### Staging (staging-auto-shop-tls)

**Create secret (one-time):**
```bash
kubectl create secret tls staging-auto-shop-tls \
  --namespace auto-shop \
  --cert=<path-to-cert.pem> \
  --key=<path-to-key.pem>
```

Or with cert-manager (if available):
```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Create certificate resource
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: staging-auto-shop-tls
  namespace: auto-shop
spec:
  secretName: staging-auto-shop-tls
  commonName: hml.api.internal
  issuerRef:
    name: letsencrypt-staging
    kind: ClusterIssuer
EOF
```

### Production (auto-shop-tls-cert)

**Requirement:** Pre-provisioned TLS certificate before deployment

**Option 1: AWS Certificate Manager (recommended for ALB)**
```bash
# Request certificate in AWS ACM
aws acm request-certificate \
  --domain-name api.autoshop.com \
  --validation-method DNS
```

**Option 2: Manual secret**
```bash
kubectl create secret tls auto-shop-tls-cert \
  --namespace auto-shop \
  --cert=<path-to-cert.pem> \
  --key=<path-to-key.pem>
```

**Option 3: cert-manager with Let's Encrypt**
```bash
# Create ClusterIssuer for production
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@autoshop.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: alb
EOF

# Create certificate
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: auto-shop-tls-cert
  namespace: auto-shop
spec:
  secretName: auto-shop-tls-cert
  commonName: api.autoshop.com
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
EOF
```

## URL Configuration

### Config Validation

**File:** `src/config.py` (lines 254-260)

Production-like environments require HTTPS URLs:
```python
def _validate_production_urls(self) -> None:
    urls = [self.app_base_url, self.frontend_public_url, *self.cors_origins()]
    if any(
        urlparse(url).scheme != "https" or not urlparse(url).hostname
        for url in urls
    ):
        raise ValueError("Production-like URLs must use HTTPS")
```

### Environment Variables

**Local:**
```
APP_BASE_URL=http://localhost:8000
FRONTEND_PUBLIC_URL=http://localhost:4200
CORS_ALLOWED_ORIGINS=http://localhost:4200
```

**Staging:**
```
APP_BASE_URL=https://hml.api.internal
FRONTEND_PUBLIC_URL=https://hml.app.internal
CORS_ALLOWED_ORIGINS=https://hml.app.internal
```

**Production:**
```
APP_BASE_URL=https://api.autoshop.com
FRONTEND_PUBLIC_URL=https://app.autoshop.com
CORS_ALLOWED_ORIGINS=https://app.autoshop.com
```

## HSTS Headers

**Status:** Ready for production ingress controller to add

**Recommendation:** Enable HSTS for production in AWS ALB or nginx controller

**nginx configuration (if used):**
```yaml
nginx.ingress.kubernetes.io/configuration-snippet: |
  more_set_headers "Strict-Transport-Security: max-age=31536000; includeSubDomains; preload";
```

**AWS ALB (via annotation):**
```yaml
alb.ingress.kubernetes.io/actions.ssl-redirect: |
  {
    "Type": "redirect",
    "RedirectConfig": {
      "Protocol": "HTTPS",
      "Port": "443",
      "StatusCode": "HTTP_301"
    }
  }
```

## Verification Checklist

- [x] TLS section present in ingress spec
- [x] Certificate secret exists (validated by deploy script)
- [x] SSL redirect enabled for production
- [x] Config validates HTTPS URLs for production
- [x] Service port correct (80 → container 8000)
- [x] Local environment can run without TLS
- [x] Staging allows HTTP (for HML testing)
- [x] Production enforces HTTPS

## Deployment Workflow

**Staging:**
```bash
# Pre-requisite: Create staging-auto-shop-tls secret
./deploy.ps1 -Environment staging -ImageReference ghcr.io/auto-shop-system:sha-abc123
# Verifies staging-auto-shop-tls exists and contains valid cert
# Applies ingress with nginx controller + HTTP allowed
```

**Production:**
```bash
# Pre-requisite: Create auto-shop-tls-cert secret
./deploy.ps1 -Environment production \
  -ImageReference ghcr.io/auto-shop-system:sha-abc123 \
  -ConfirmProduction
# Verifies auto-shop-tls-cert exists
# Applies ingress with ALB controller + HTTPS enforced
```

## Test Certificate for Local Testing

For local development with self-signed cert:
```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes \
  -subj "/CN=localhost"

kubectl create secret tls local-test-tls \
  --namespace auto-shop \
  --cert=cert.pem \
  --key=key.pem

# Use in Kind cluster:
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: auto-shop-local-tls
  namespace: auto-shop
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - localhost
    secretName: local-test-tls
  rules:
  - host: localhost
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: auto-shop-backend-service
            port:
              number: 80
EOF
```

## Summary

✅ **TLS Enforcement:**
- Production: HTTPS mandatory with ALB redirect
- Staging: HTTP allowed for HML testing
- Local: No TLS required

✅ **Certificate Management:**
- Secrets pre-provisioned before deployment
- Deploy script validates existence
- cert-manager or manual setup supported

✅ **Configuration:**
- HTTPS URLs required for production config
- Ingress controllers configured per environment
- SSL redirect annotations applied

Next: **PR47-07 (PostgreSQL readiness)**
