# PR47-12 — Operations Guide & Runbooks

**Status:** 🚀 Final PR  
**Date:** 2026-11-01  
**Purpose:** Complete operations documentation for production-safe Kubernetes deployment

---

## Table of Contents

1. [Environment Matrix](#environment-matrix)
2. [Secret Provisioning](#secret-provisioning)
3. [Deployment Procedures](#deployment-procedures)
4. [Troubleshooting](#troubleshooting)
5. [Rollback Procedures](#rollback-procedures)
6. [Disaster Recovery](#disaster-recovery)
7. [Monitoring & Alerts](#monitoring--alerts)
8. [Runbook Templates](#runbook-templates)

---

## Environment Matrix

### Comparison Table

| Aspect | Local | Staging | Production |
|--------|-------|---------|------------|
| **Infrastructure** | Docker Desktop / Kind | EKS cluster | EKS cluster (dedicated) |
| **Database** | Embedded PostgreSQL pod | External RDS | External RDS (Multi-AZ) |
| **Replicas** | 1 (CPU limited) | 2–3 (HPA 2–5) | 3–5 (HPA 3–10) |
| **Image Registry** | Local docker daemon | GHCR.io | GHCR.io |
| **Secret Source** | Generated locally | AWS Secrets Manager | AWS Secrets Manager |
| **TLS** | Optional (ingress-nginx) | Enforced (ALB + cert manager) | Enforced (ALB + cert manager) |
| **Access** | localhost:8000 | admin.hml.auto-shop.tech | admin.auto-shop.tech |
| **Logs** | kubectl logs | CloudWatch | CloudWatch |
| **Metrics** | Metrics Server | Prometheus + Grafana | Prometheus + Grafana |
| **Cost** | Free | ~$500/month (RDS + EKS) | ~$1500/month (RDS + EKS + HA) |

### Overlay Structure

```
k8s/overlays/
├── local/              # Development (Kind + embedded DB)
│   ├── foundation/     # Namespace, ConfigMap, PostgreSQL pod
│   ├── migration/      # Alembic migration Job
│   ├── seed/           # Sample data Job
│   ├── app/            # API Deployment (1 replica, no resource limits)
│   └── ingress/        # Ingress (HTTP, localhost)
├── staging/            # QA (EKS + external RDS)
│   ├── foundation/     # Namespace, ConfigMap, ServiceAccount
│   ├── migration/      # Alembic migration Job
│   ├── seed/           # Sample data Job
│   ├── app/            # API Deployment (2–3 replicas, resource requests)
│   └── ingress/        # Ingress (HTTPS redirect, ALB)
└── production/         # Prod (EKS + external RDS Multi-AZ)
    ├── foundation/     # Namespace, ConfigMap, ServiceAccount
    ├── migration/      # Alembic migration Job
    ├── seed/           # Disabled (no synthetic data)
    ├── app/            # API Deployment (3–5 replicas, high HA)
    └── ingress/        # Ingress (HTTPS, ALB, SSL termination)
```

---

## Secret Provisioning

### Pre-Deployment Checklist

Before ANY deployment, verify secrets are provisioned:

#### Local Development
```bash
# Secrets auto-generated per deployment
# Script: k8s/scripts/deploy.ps1 (ephemeral generation)

./deploy.ps1 -Environment local
# Auto-generates:
# - DATABASE_URL (postgres service)
# - SECRET_KEY (random hex-32)
# - DEMO_ADMIN_PASSWORD (random hex-32)
```

**No manual setup required** — secrets are generated at deployment time.

#### Staging

```bash
# 1. Verify AWS Secrets Manager secret exists
aws secretsmanager get-secret-value \
  --secret-id auto-shop-staging-secrets \
  --region us-east-1

# Expected output:
# {
#   "SecretString": "{...}"
# }

# 2. Validate secret structure
aws secretsmanager get-secret-value \
  --secret-id auto-shop-staging-secrets \
  --region us-east-1 \
  --query 'SecretString' \
  --output text | jq '.DATABASE_URL, .SECRET_KEY, .DEMO_ADMIN_PASSWORD'

# Expected:
# "postgresql://oficina:PASSWORD@rds-staging.xyz.us-east-1.rds.amazonaws.com:5432/oficina"
# "hex-string-length-32"
# "hex-string-length-32"
```

#### Production

```bash
# 1. Verify AWS Secrets Manager secret exists
aws secretsmanager get-secret-value \
  --secret-id auto-shop-production-secrets \
  --region us-east-1

# 2. Verify NO SYNTHETIC seed data enabled
aws secretsmanager get-secret-value \
  --secret-id auto-shop-production-secrets \
  --region us-east-1 \
  --query 'SecretString' \
  --output text | jq '.ALLOW_SYNTHETIC_SEED_IN_PRD'

# Expected: null or "false"
# If "true": ❌ FAIL — do not deploy without fixing

# 3. Run validation script
./scripts/validate-secrets.ps1 -Environment production
# Should exit 0 (no placeholder values, all keys present)
```

### Creating Secrets in AWS Secrets Manager

#### Staging Template

```bash
aws secretsmanager create-secret \
  --name auto-shop-staging-secrets \
  --region us-east-1 \
  --secret-string '{
    "DATABASE_URL": "postgresql://oficina:STRONG_PASSWORD_MIN_24_CHARS@staging-rds.xyz.us-east-1.rds.amazonaws.com:5432/oficina",
    "SECRET_KEY": "RANDOM_HEX_32_CHARS_HERE",
    "DEMO_ADMIN_PASSWORD": "RANDOM_HEX_32_CHARS_HERE",
    "ALLOW_SYNTHETIC_SEED_IN_PRD": "false"
  }'
```

#### Production Template

```bash
aws secretsmanager create-secret \
  --name auto-shop-production-secrets \
  --region us-east-1 \
  --secret-string '{
    "DATABASE_URL": "postgresql://oficina:STRONG_PASSWORD_MIN_24_CHARS@prod-rds-multi-az.xyz.us-east-1.rds.amazonaws.com:5432/oficina",
    "SECRET_KEY": "RANDOM_HEX_32_CHARS_HERE",
    "DEMO_ADMIN_PASSWORD": "DISABLED_IN_PRODUCTION",
    "ALLOW_SYNTHETIC_SEED_IN_PRD": "false"
  }'
```

### Rotating Secrets

**Procedure:**

1. **Update value in Secrets Manager:**
   ```bash
   aws secretsmanager update-secret \
     --secret-id auto-shop-staging-secrets \
     --secret-string '{...updated JSON...}'
   ```

2. **Restart API pods** (forces re-read of secret):
   ```bash
   kubectl rollout restart deployment/auto-shop-backend \
     --namespace auto-shop
   ```

3. **Verify rollout:**
   ```bash
   kubectl rollout status deployment/auto-shop-backend \
     --namespace auto-shop --timeout=300s
   ```

4. **Smoke test health endpoints:**
   ```bash
   curl -f http://auto-shop-backend/health/ready
   # Should return 200 OK
   ```

---

## Deployment Procedures

### Local Development

**Prerequisites:**
- Docker Desktop or Kind installed
- kubectl configured
- PowerShell 5.1+

**Procedure:**

```bash
# 1. Navigate to repo root
cd /path/to/auto-shop-system

# 2. Run deployment
./k8s/scripts/deploy.ps1 -Environment local

# 3. Watch deployment progress
kubectl get pods -n auto-shop -w

# 4. Port-forward to access API
kubectl port-forward service/auto-shop-backend-service 8000:80 -n auto-shop

# 5. Verify health
curl http://localhost:8000/health/ready
# Expected: 200 OK + {"status":"ok"}
```

**Expected Output:**
```
Auto Shop local deployment completed successfully.
```

**Cleanup:**
```bash
# Delete all local resources
kubectl delete namespace auto-shop
```

### Staging Deployment

**Prerequisites:**
- AWS credentials configured (Staging assume role)
- EKS cluster accessible (kubeconfig)
- Image tag: `ghcr.io/auto-shop-system:sha-{commit-sha}`
- Secrets provisioned in AWS Secrets Manager

**Procedure:**

```bash
# 1. Assume staging IAM role (from ops account)
aws sts assume-role \
  --role-arn arn:aws:iam::STAGING-ACCOUNT:role/DeploymentRole \
  --role-session-name staging-deploy

# 2. Export credentials from response
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...

# 3. Update kubeconfig
aws eks update-kubeconfig \
  --name auto-shop-staging \
  --region us-east-1

# 4. Verify kubectl context
kubectl config current-context
# Expected: arn:aws:eks:us-east-1:STAGING-ACCOUNT:cluster/auto-shop-staging

# 5. Run deployment
./k8s/scripts/deploy.ps1 \
  -Environment staging \
  -ImageReference ghcr.io/auto-shop-system:sha-abc123def \
  -SkipIngress  # Optional: for debugging

# 6. Watch rollout
kubectl get deployment -n auto-shop -w

# 7. Verify smoke tests
curl -f https://admin.hml.auto-shop.tech/health/ready
curl -f https://admin.hml.auto-shop.tech/docs
```

**Expected Duration:** 5–10 minutes

**Rollback (if needed):**
```bash
# Revert to previous image
./k8s/scripts/deploy.ps1 \
  -Environment staging \
  -ImageReference ghcr.io/auto-shop-system:sha-previous-sha
```

### Production Deployment

**Prerequisites:**
- AWS credentials configured (Production assume role)
- EKS cluster accessible (kubeconfig)
- Image tag: `ghcr.io/auto-shop-system:sha-{commit-sha}`
- Secrets provisioned in AWS Secrets Manager
- **Approval from Engineering Lead**
- Change request created in Jira

**Pre-Flight Checks:**

```bash
# 1. Verify no ongoing incidents
# Check: Jira Incident board, PagerDuty

# 2. Verify database backups
aws rds describe-db-snapshots \
  --db-instance-identifier auto-shop-prod \
  --query 'DBSnapshots[0].[DBSnapshotIdentifier,SnapshotCreateTime]'
# Expected: Recent snapshot (< 24 hours)

# 3. Verify cluster health
kubectl get nodes -o wide
# Expected: All nodes Ready

# 4. Verify app health
kubectl get deployment -n auto-shop
# Expected: auto-shop-backend available

# 5. Verify no active alerts
# Check: Prometheus/Grafana dashboard
```

**Procedure:**

```bash
# 1. Create change request (Jira)
# Title: "Deploy auto-shop-system:sha-abc123 to production"
# Description: List the commits included, any schema changes, breaking changes

# 2. Assume production IAM role
aws sts assume-role \
  --role-arn arn:aws:iam::PROD-ACCOUNT:role/DeploymentRole \
  --role-session-name prod-deploy

# 3. Export credentials
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...

# 4. Update kubeconfig
aws eks update-kubeconfig \
  --name auto-shop-production \
  --region us-east-1

# 5. Verify production context
kubectl config current-context
# Expected: arn:aws:eks:us-east-1:PROD-ACCOUNT:cluster/auto-shop-production

# 6. **PRODUCTION ONLY:** Require explicit confirmation
./k8s/scripts/deploy.ps1 \
  -Environment production \
  -ImageReference ghcr.io/auto-shop-system:sha-abc123def \
  -ConfirmProduction

# 7. Monitor deployment
kubectl get deployment -n auto-shop -w

# 8. Verify health (5 minute window)
for i in {1..5}; do
  curl -f https://admin.auto-shop.tech/health/ready
  curl -f https://admin.auto-shop.tech/docs
  sleep 60
done

# 9. Update change request
# Status: Deployed
# Duration: ~10 minutes
# Result: Success / Rollback details
```

**Expected Duration:** 10–15 minutes

---

## Troubleshooting

### API Pod Failing to Start

**Symptoms:**
```
$ kubectl get pods -n auto-shop
NAME                               READY   STATUS             RESTARTS
auto-shop-backend-xxxxx            0/1     CrashLoopBackOff   3
```

**Investigation:**

```bash
# 1. Check pod logs
kubectl logs deployment/auto-shop-backend -n auto-shop --tail=50

# Common errors:
# "FATAL: password authentication failed" → DATABASE_URL incorrect
# "ModuleNotFoundError: No module named 'src'" → Image not built correctly
# "Connection timeout" → Database unreachable

# 2. Check environment variables
kubectl set env pod/auto-shop-backend-xxxxx --list -n auto-shop

# 3. Check secret
kubectl get secret auto-shop-secrets -n auto-shop -o yaml
# Verify: DATABASE_URL, SECRET_KEY present

# 4. Check startup probe
kubectl describe pod auto-shop-backend-xxxxx -n auto-shop | grep -A 5 "Startup"
```

**Resolution:**

| Error | Action |
|-------|--------|
| Database URL incorrect | Re-deploy with correct secret (see Secret Provisioning) |
| Image not found | Verify image tag: `kubectl describe pod ... \| grep Image:` |
| Database unreachable | Check: network policy, security group, RDS endpoint |
| Memory exceeded | Increase resource limit: `kubectl set resources deployment/auto-shop-backend --limits=memory=512Mi` |

### Migration Job Failing

**Symptoms:**
```
$ kubectl get jobs -n auto-shop
NAME                        COMPLETIONS   DURATION   STATUS
auto-shop-migrate-xxxxx     0/1            5m         Failed
```

**Investigation:**

```bash
# 1. Check migration logs
kubectl logs job/auto-shop-migrate-xxxxx -n auto-shop --tail=100

# Common errors:
# "FATAL: database ... does not exist" → Database not created
# "relation ... already exists" → Idempotency issue (rerun Alembic)
# "Connection timeout" → PostgreSQL not ready yet

# 2. Check database connection
kubectl exec -it pod/postgres-xxxxx -n auto-shop -- psql -U oficina -d oficina -c "\dt"

# 3. Check migration status
kubectl describe job auto-shop-migrate-xxxxx -n auto-shop
```

**Resolution:**

```bash
# Option 1: Retry migration (if transient failure)
kubectl delete job auto-shop-migrate-xxxxx -n auto-shop
./k8s/scripts/deploy.ps1 -Environment local -SkipIngress
# Re-runs migration with new job

# Option 2: Reset database (DEV ONLY)
kubectl exec -it pod/postgres-xxxxx -n auto-shop -- psql -U oficina -d oficina -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
# Then re-deploy

# Option 3: Check Alembic history
kubectl exec -it pod/postgres-xxxxx -n auto-shop -- psql -U oficina -d oficina -c "SELECT version_num, description FROM alembic_version;"
```

### Readiness Probe Failing

**Symptoms:**
```
$ kubectl get pods -n auto-shop
auto-shop-backend-xxxxx    0/1     Running    0        2m

# curl returns 503
curl http://localhost:8000/health/ready
# {"status":"unavailable"}
```

**Investigation:**

```bash
# 1. Check readiness probe configuration
kubectl get pod auto-shop-backend-xxxxx -n auto-shop -o yaml | grep -A 10 "readinessProbe"

# 2. Check database connectivity
kubectl exec -it pod/auto-shop-backend-xxxxx -n auto-shop -- python -c "from src.infrastructure.database import check_database_connection; print(check_database_connection())"

# 3. Check rate limit storage (Redis)
kubectl logs deployment/auto-shop-backend -n auto-shop | grep -i "rate.limit\|redis"
```

**Resolution:**

| Cause | Action |
|-------|--------|
| Database down | Check PostgreSQL pod, verify connection string |
| Redis unavailable | Verify rate-limit storage is deployed |
| Network policy | Check: `kubectl get networkpolicies -n auto-shop` |
| DNS resolution | Test: `kubectl exec pod/... -- nslookup postgres-service` |

### HPA Not Scaling

**Symptoms:**
```
$ kubectl get hpa -n auto-shop
NAME              REFERENCE                    TARGETS     MINPODS   MAXPODS   REPLICAS
auto-shop-scale   Deployment/auto-shop-backend 5%/80%      2         5         2
```

**Investigation:**

```bash
# 1. Check HPA status
kubectl get hpa auto-shop-scale -n auto-shop -o wide

# 2. Check metrics
kubectl top pods -n auto-shop
# If metrics unavailable: Metrics Server not working

# 3. Verify HPA configuration
kubectl describe hpa auto-shop-scale -n auto-shop

# 4. Check events
kubectl get events -n auto-shop --sort-by='.lastTimestamp' | tail -20
```

**Resolution:**

```bash
# If metrics unavailable: reinstall Metrics Server
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Verify metrics available (wait 1–2 minutes)
kubectl get metrics nodes
kubectl get metrics pods -n auto-shop
```

---

## Rollback Procedures

### Rollback from Previous Image

**When to use:** API deployment failed, tests failing, security issue found

**Procedure:**

```bash
# 1. Identify previous known-good image
git log --oneline -10
# Example: abc123d "fix: auth handler"

# 2. Determine image tag
IMAGE_TAG="sha-abc123d"

# 3. Trigger rollback deployment
./k8s/scripts/deploy.ps1 \
  -Environment staging \
  -ImageReference ghcr.io/auto-shop-system:${IMAGE_TAG}

# 4. Verify health
kubectl rollout status deployment/auto-shop-backend -n auto-shop --timeout=300s
curl -f https://admin.hml.auto-shop.tech/health/ready

# 5. Update change request
# Status: Rolled back
# Reason: [incident description]
# Commit: abc123d
```

### Database Rollback

**When to use:** Migration caused data corruption, schema change caused app failure

**Procedure:**

```bash
# 1. Identify backup point
aws rds describe-db-snapshots \
  --db-instance-identifier auto-shop-staging \
  --query 'DBSnapshots[*].[DBSnapshotIdentifier,SnapshotCreateTime]'

# 2. Create new instance from snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier auto-shop-staging-rollback \
  --db-snapshot-identifier rds:auto-shop-staging-YYYY-MM-DDTHH:MM:SS.sssZ \
  --publicly-accessible false

# 3. Wait for restore (5–10 minutes)
aws rds describe-db-instances \
  --db-instance-identifier auto-shop-staging-rollback \
  --query 'DBInstances[0].DBInstanceStatus'

# 4. Update connection string in secret
aws secretsmanager update-secret \
  --secret-id auto-shop-staging-secrets \
  --secret-string '{"DATABASE_URL":"new_rds_endpoint",...}'

# 5. Restart API deployment
kubectl rollout restart deployment/auto-shop-backend -n auto-shop

# 6. Verify health
curl -f https://admin.hml.auto-shop.tech/health/ready

# 7. Delete old instance (after verification)
aws rds delete-db-instance \
  --db-instance-identifier auto-shop-staging \
  --skip-final-snapshot

# 8. Rename restored instance
# (manual step via AWS Console or CLI)
```

---

## Disaster Recovery

### Complete Environment Loss

**Scenario:** Cluster destroyed, all resources lost

**Recovery Time Objective (RTO):** 30 minutes  
**Recovery Point Objective (RPO):** Last automated backup

**Procedure:**

```bash
# 1. Verify backups available
aws rds describe-db-snapshots \
  --db-instance-identifier auto-shop-production \
  --query 'DBSnapshots[0].SnapshotCreateTime'

# 2. Recreate EKS cluster (Terraform)
cd terraform/aws-k8s
terraform apply -target=module.eks_cluster -var=environment=production

# 3. Update kubeconfig
aws eks update-kubeconfig \
  --name auto-shop-production \
  --region us-east-1

# 4. Restore database from snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier auto-shop-production \
  --db-snapshot-identifier rds:auto-shop-production-YYYY-MM-DD...

# 5. Wait for database ready (5–10 minutes)
# 6. Deploy app with previous image
./k8s/scripts/deploy.ps1 \
  -Environment production \
  -ImageReference ghcr.io/auto-shop-system:sha-LAST_KNOWN_GOOD \
  -ConfirmProduction

# 7. Verify health
curl -f https://admin.auto-shop.tech/health/ready

# 8. Post-incident review
# Create Jira incident ticket documenting timeline
```

### Database Corruption

**Scenario:** Data corruption detected, need to restore from backup

**Procedure:**

See "Database Rollback" section above

### Data Loss in Migration

**Scenario:** Migration dropped a column, data lost

**Procedure:**

```bash
# 1. IMMEDIATELY stop deployment
# Kill running migration job
kubectl delete job auto-shop-migrate-xxxxx -n auto-shop

# 2. Revert API to previous image
./k8s/scripts/deploy.ps1 \
  -Environment production \
  -ImageReference ghcr.io/auto-shop-system:sha-PREVIOUS \
  -ConfirmProduction

# 3. Verify API is healthy
curl -f https://admin.auto-shop.tech/health/ready

# 4. Restore database from backup (before migration)
# Follow Database Rollback procedure

# 5. Investigation phase
# - Review migration script
# - Identify data loss scope
# - Determine recovery method

# 6. Create safe migration
# - Add column back if dropped
# - Preserve remaining data
# - Test in staging first
```

---

## Monitoring & Alerts

### Key Metrics

| Metric | Alert Threshold | Action |
|--------|-----------------|--------|
| Pod CPU | > 80% | Scale up (HPA) |
| Pod Memory | > 85% | Investigate memory leak |
| API Latency | > 500ms p99 | Check database, trace request |
| Error Rate | > 1% | Check logs, identify issue |
| Database CPU | > 75% | Scale RDS instance |
| Database Connections | > 80 | Check connection pool |

### Dashboard

Access Grafana: https://monitoring.auto-shop.tech/grafana

**Key dashboards:**
- API Performance
- Database Health
- Pod Resource Usage
- Error Rate Trends

### PagerDuty Integration

**On-call rotation:** Check https://auto-shop.pagerduty.com/schedules

**Alert channels:**
- Critical: PagerDuty + Slack #incidents
- Warning: Slack #alerts
- Info: CloudWatch Logs

---

## Runbook Templates

### Incident Runbook Template

```markdown
# Incident: [Title]

**Start Time:** [UTC]  
**Severity:** Critical / High / Medium / Low  
**Impact:** [# users affected, services affected]

## Investigation

- [ ] Check API logs: `kubectl logs -f deployment/auto-shop-backend`
- [ ] Check database: `kubectl exec pod/postgres -- psql -c "SELECT COUNT(*) FROM ..."`
- [ ] Check metrics: Grafana dashboard
- [ ] Check recent deployments: `git log -5`

## Diagnosis

[Write findings here]

## Resolution

[Describe actions taken]

## Timeline

- HH:MM UTC: Issue detected
- HH:MM UTC: Root cause identified
- HH:MM UTC: Fix deployed / Rollback initiated
- HH:MM UTC: Verified healthy

## Post-Incident

- [ ] Update runbook
- [ ] Create Jira ticket for prevention
- [ ] Schedule retrospective
```

### Deployment Runbook Template

```markdown
# Deployment: [Version] → [Environment]

**Change Request:** JIRA-XXXX  
**Image:** ghcr.io/auto-shop-system:sha-abc123def  
**Started:** [UTC]

## Pre-Flight Checks

- [ ] Database backups available
- [ ] Cluster health good (`kubectl get nodes`)
- [ ] No active incidents
- [ ] Secrets validated
- [ ] Code review complete

## Deployment

```bash
./k8s/scripts/deploy.ps1 \
  -Environment staging \
  -ImageReference ghcr.io/auto-shop-system:sha-abc123def
```

## Verification

- [ ] Health check: `/health/ready` → 200 OK
- [ ] Smoke test: `/docs` loads
- [ ] HPA scaling works
- [ ] No error rate spike

## Completion

**Completed:** [UTC]  
**Duration:** X minutes  
**Issues:** None / [describe issues]
```

---

## Summary

✅ **Complete Operations Documentation:**
- Environment matrix with specs and costs
- Secret provisioning workflow
- Deployment procedures (local, staging, production)
- Comprehensive troubleshooting guide
- Rollback procedures
- Disaster recovery runbooks
- Monitoring and alerting
- Incident response templates

✅ **Ready for Production:**
- All PRs 0–12 complete
- Comprehensive test coverage
- Security hardening
- Full operational documentation

**🎯 PR47 IMPLEMENTATION COMPLETE**
