# Infrastructure — Issues #01-#05 Complete

**Status:** 🟢 DEPLOYED | **Updated:** 2026-10-31 | **Version:** v1.0

## Overview

Auto Shop System infrastructure consists of 5 interconnected issues providing OIDC security, AWS bootstrap, private GitHub runners, digest-based deployments, and Kubernetes network isolation with HTTPS edge termination.

---

## Issue #01: OIDC Security Foundation

**Status:** ✅ COMPLETE

### Implementation

GitHub Actions OIDC identity provider enables secure, token-less authentication from CI/CD to AWS.

**AWS OIDC Configuration**
- Provider: token.actions.githubusercontent.com
- Audience: sts.amazonaws.com
- Trust Policy: StringEquals (exact matching, no wildcards)
- Action: sts:AssumeRoleWithWebIdentity

**Key Features**
- No hardcoded AWS credentials in GitHub
- Time-limited tokens (default 60 min)
- Subject-based scoping (branch/tag/environment)
- Auditability via CloudTrail

---

## Issue #02: AWS Bootstrap & State Management

**Status:** ✅ COMPLETE

### Deployed Infrastructure

**Compute**
- EKS Cluster (1.26+)
- Node groups (auto-scaling)
- Managed IAM roles

**Networking**
- VPC with public/private subnets
- Security groups for EKS, RDS, ALB
- VPC Endpoints

**State Management**
- S3 bucket for Terraform state
- DynamoDB table for state locking
- Versioning and encryption enabled

**Lifecycle Infrastructure**
- DynamoDB table for session tracking
- Lambda functions for health checks
- EventBridge automation rules

### Environment Variables Set

**k8s-infra:**
```
ENABLE_PRIVATE_EKS_RUNNER = "true"
GITHUB_RUNNER_GROUP_ID = "3"
GITHUB_CODECONNECTION_ARN = "arn:aws:codeconnections:us-east-1:035611741563:connection/..."
```

**auto-shop-system (hml-lifecycle):**
```
K8S_HML_TERRAFORM_ROOT_READY = "true"
K8S_PRIVATE_RUNNER_PREREQUISITES_READY = "true"
```

---

## Issue #03: Private GitHub Runners & Lifecycle

**Status:** ✅ COMPLETE

### Configuration

**Runner Group**
- ID: 3 (custom group)
- Target: CodeBuild compute
- Labels: infrastructure-only, hml-lifecycle

**CodeConnections Integration**
- GitHub App authentication (no manual AWS authorization)
- Connection ARN: arn:aws:codeconnections:us-east-1:035611741563:connection/...

**Lifecycle Automation**
- Daily schedule: 0 0-1,14-23 * * * (hourly during window)
- Session tracking via DynamoDB
- Automatic teardown at 23:00 UTC
- Cost control: Closes long-running sessions

**Cleanup Workflow** (`.github/workflows/lifecycle-cleanup.yml`)
- Trigger: Scheduled hourly
- Action: Finds expired HML sessions, dispatches cleanup
- Ledger: DynamoDB tracks infrastructure-only sessions

---

## Issue #04: Digest-Based Deployment & OIDC Validation

**Status:** ✅ COMPLETE & VALIDATED

### Execution

**Workflow Runs**
- Issue #04 test: 41238552338 ✓ PASS
- Issue #05 deployment: 41239161719 ✓ PASS

**Image Digest**
```
SHA256: 337649663cb7ff084703c7a1f1ff29e030e29941823524cf46253a8ad21d6983
Built: 2026-10-31T20:30:16Z
Registry: ghcr.io/software-architecture-group-7-fiap/auto-shop-system
```

### OIDC Authentication Chain

1. GitHub Actions workflow starts
2. Actions generates JWT token
3. Token sent to GitHub OIDC provider
4. AWS receives OIDC assertion
5. AssumeRoleWithWebIdentity called
6. Temporary credentials issued (15 min)
7. Deploy script uses credentials
8. Image built with digest reference (not tag)
9. CloudTrail logs event

**Validations**
- ✅ Prefer image digest: true
- ✅ Digest persisted in containerimage.digest
- ✅ No tag-based fallback
- ✅ Rollback via digest reference possible
- ✅ OIDC token exchange successful

---

## Issue #05: Kubernetes Infrastructure

**Status:** ✅ DEPLOYED

### Network Policies (Strict Mode)

**File:** `k8s/base/network/network-policy-strict.yaml`

Rules implemented:
- Default deny all ingress
- Allow DNS egress to kube-system (port 53 UDP)
- Allow ALB ingress to backend (ports 8000/8080 TCP)
- Allow RDS egress (external port 5432)
- Allow external HTTPS egress (ports 443/80)

**Principle:** Explicit allow-lists only; blocks lateral movement

### HTTPS Ingress

**File:** `k8s/overlays/production/ingress/ingress-patch.yaml`

Configuration:
```
Host: api.autoshop.com
TLS: auto-shop-tls-cert (AWS Secrets Manager)
Backend: auto-shop-backend service (port 8000)
Controller: ALB
Protocol: HTTPS with auto HTTP→HTTPS redirect
```

### Backend Deployment

**Configuration**
- Replicas: 2 (rolling update)
- Image: Digest-based (no tags)
- Strategy: RollingUpdate (1 surge, 0 unavailable)
- HPA: CPU/memory auto-scaling (5-10 pods)
- Health checks: Liveness + readiness probes

**Database Migration**
- Pre-deployment Job
- Runs Alembic migrations
- Waits for completion before deployment

### Terraform Resources

Seven resources in `infra/k8s.tf`:

| Resource | Name | Purpose |
|----------|------|---------|
| kubernetes_namespace_v1 | auto_shop | K8s namespace isolation |
| kubernetes_config_map_v1 | app | App configuration |
| kubernetes_deployment_v1 | backend | Backend service (2 replicas) |
| kubernetes_service_v1 | backend | ClusterIP service |
| kubernetes_horizontal_pod_autoscaler_v1 | backend | Auto-scaling |
| kubernetes_job_v1 | migrate | Database migration |
| kubernetes_ingress_v1 | api | ALB ingress + HTTPS |

---

## Deployment Process

### Local Development
```bash
cd infra/
terraform init      # Download providers
terraform plan      # Review changes
terraform apply     # Deploy (requires K8s cluster)
```

### CI/CD (GitHub Actions)
1. Push to develop
2. GitHub Actions triggered (lifecycle:push-*)
3. Build image + generate digest
4. OIDC auth → AWS credentials
5. Terraform init
6. Terraform apply (EKS cluster)
7. Deployment gates evaluated
8. K8s resources created

---

## Validation Commands

### Network Policies
```bash
kubectl get networkpolicies -n auto-shop
kubectl run test-pod -n auto-shop --image=busybox --sleep 3600
kubectl exec test-pod -- nslookup kubernetes.default
```

### HTTPS Ingress
```bash
kubectl get ingress -n auto-shop
curl https://api.autoshop.com/health
kubectl get secret auto-shop-tls-cert -n auto-shop -o yaml
```

### Deployment Health
```bash
kubectl get deployment auto-shop-backend -n auto-shop    # 2/2 ready
kubectl get pods -n auto-shop                            # all Running
kubectl get endpoints auto-shop-backend -n auto-shop     # 2 IPs
```

---

## Cleanup & Teardown

### Automatic (23:00 UTC daily)
- Lifecycle cleanup dispatcher runs
- Finds expired HML sessions (hml-YYYY-MM-DD)
- Triggers environment-stop.yml workflow
- Removes DynamoDB session record
- Stops GitHub runner

### Manual
```bash
kubectl delete namespace auto-shop
terraform destroy
```

---

## Security Checklist

- [x] OIDC authentication (no hardcoded credentials)
- [x] Network policies (strict default-deny)
- [x] TLS/HTTPS ingress
- [x] VPC isolation (private subnets for databases)
- [x] Security group restrictions
- [x] S3 bucket encryption + versioning
- [x] IAM least privilege (role-based)
- [x] Secret management (AWS Secrets Manager)
- [x] Audit logging (CloudTrail)
- [ ] WAF on ALB (future)
- [ ] GuardDuty threat detection (future)
- [ ] Secrets rotation (future)

---

## Cost Estimates

**Monthly Infrastructure**
- EKS cluster: ~$73
- Compute: ~$200-400
- RDS: ~$50-100
- **Total:** ~$350-600/month

**Optimization Opportunities**
- Use Fargate for sporadic workloads
- Reserved instances for baseline compute
- RDS read replicas for high traffic
- CloudFront caching for static assets

---

## Troubleshooting

### Network Policy Issues
- **Pod can't reach external service:** Check egress policy allows destination (443/80)
- **Pod can't resolve DNS:** Verify allow-dns policy includes kube-system namespace

### OIDC Issues
- **"invalid_grant" error:** Verify trust policy StringEquals subject matches exactly
- **AssumeRoleWithWebIdentity fails:** Check IAM role exists and trust policy is correct

### Ingress Issues
- **ALB not routing:** Verify backend service exists, replicas ready, ingress rules match
- **HTTPS certificate fails:** Verify secret `auto-shop-tls-cert` exists in auto-shop namespace

---

## Related Documentation

- **Architecture:** docs/architecture.md
- **Deployment:** docs/deployment.md
- **Hardening:** docs/hardening-review.md
- **Issues Status:** docs/ISSUES-01-05-COMPLETION-STATUS.md

---

**Last Updated:** 2026-10-31T20:30Z  
**Status:** 🟢 LIVE  
**Workflow:** #41239161719
