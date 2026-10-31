# Operational Runbooks

Common procedures for operating the infrastructure.

## Deploying Infrastructure Changes

### Prerequisites
- AWS credentials configured (`aws configure`)
- kubectl configured for EKS cluster
- Terraform 1.0+ installed
- Git access to repository

### Procedure

1. **Create feature branch**
   ```bash
   git checkout -b feat/infrastructure-update
   ```

2. **Make infrastructure changes**
   ```bash
   # Edit k8s/*.yaml files or infra/*.tf files
   # Commit changes
   git commit -m "feat: infrastructure update"
   ```

3. **Validate changes locally**
   ```bash
   # Validate K8s manifests
   kubectl kustomize k8s/base | kubectl diff -f -
   
   # Validate Terraform
   cd infra && terraform plan
   ```

4. **Push and create PR**
   ```bash
   git push origin feat/infrastructure-update
   # Create PR via GitHub UI
   ```

5. **Merge to develop**
   - GitHub Actions runs automatically
   - Build & push image with digest
   - Terraform plan runs in dry-run mode
   - Manual approval required before merge

6. **Deploy via GitHub Actions**
   - Merge PR to develop
   - Workflow: lifecycle:push-*:app-deploy runs
   - Image built, pushed, and deployed
   - Pod replicas transition to new version

---

## Troubleshooting Deployment Failures

### Scenario: Pod not reaching database

**Symptoms**
- Pod logs show "connection refused" to RDS
- `kubectl logs pod-name -n auto-shop` shows DB errors

**Diagnosis**
```bash
# Check pod can reach RDS endpoint
kubectl exec -it pod-name -n auto-shop -- sh
# Inside pod: nslookup rds-endpoint.amazonaws.com
# Try: telnet rds-endpoint.amazonaws.com 5432
```

**Resolution**
1. Verify network policy allows RDS egress
   ```bash
   kubectl get networkpolicies -n auto-shop
   # Look for allow-rds-egress policy
   ```

2. Check security group allows port 5432 from K8s subnet
   ```bash
   aws ec2 describe-security-groups --filters "Name=group-id,Values=sg-xxx"
   # Verify RDS security group has ingress on 5432 from K8s
   ```

3. Restart pod to pick up network changes
   ```bash
   kubectl rollout restart deployment/auto-shop-backend -n auto-shop
   ```

### Scenario: Ingress not routing traffic

**Symptoms**
- `curl api.autoshop.com` times out or connection refused
- Ingress shows no address (no ALB assigned)

**Diagnosis**
```bash
# Check ingress status
kubectl get ingress -n auto-shop -o wide
# Should show ADDRESS (ALB DNS) and PORTS

# Check ALB controller logs
kubectl logs -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller -f
```

**Resolution**
1. Verify backend service is accessible
   ```bash
   kubectl get svc -n auto-shop
   kubectl describe svc auto-shop-backend -n auto-shop
   # Check Endpoints: should list pod IPs
   ```

2. Check pod is ready
   ```bash
   kubectl get pods -n auto-shop -o wide
   # All should be Running and 1/1 Ready
   ```

3. Restart ALB controller
   ```bash
   kubectl rollout restart deployment -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller
   ```

### Scenario: Certificate error on HTTPS

**Symptoms**
- `curl https://api.autoshop.com` shows certificate error
- Browser shows "untrusted certificate"

**Diagnosis**
```bash
# Check certificate secret
kubectl get secret -n auto-shop
kubectl describe secret auto-shop-tls-cert -n auto-shop
# Verify cert-tls.crt and key are present

# Test certificate
openssl s_client -connect api.autoshop.com:443
```

**Resolution**
1. Verify certificate secret exists
   ```bash
   kubectl get secret auto-shop-tls-cert -n auto-shop -o yaml
   # Should have tls.crt and tls.key
   ```

2. If missing, create from AWS Secrets Manager
   ```bash
   aws secretsmanager get-secret-value --secret-id auto-shop/tls | jq -r '.SecretString' | kubectl create secret tls auto-shop-tls-cert --cert=- --key=- -n auto-shop
   ```

3. Restart ingress controller
   ```bash
   kubectl rollout restart deployment -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller
   ```

---

## Scaling Operations

### Increase backend replicas

```bash
# View current replicas
kubectl get deployment auto-shop-backend -n auto-shop

# Scale to 5 replicas
kubectl scale deployment auto-shop-backend --replicas=5 -n auto-shop

# Watch rollout
kubectl rollout status deployment/auto-shop-backend -n auto-shop --watch
```

### Adjust HPA settings

```bash
# View current HPA
kubectl get hpa -n auto-shop
kubectl describe hpa auto-shop-backend -n auto-shop

# Edit HPA (vi editor)
kubectl edit hpa auto-shop-backend -n auto-shop
# Modify minReplicas, maxReplicas, targetCPUUtilizationPercentage
```

---

## Emergency Procedures

### Rollback to previous image

```bash
# View rollout history
kubectl rollout history deployment/auto-shop-backend -n auto-shop

# Rollback one version
kubectl rollout undo deployment/auto-shop-backend -n auto-shop

# Wait for pods to restart
kubectl rollout status deployment/auto-shop-backend -n auto-shop --watch
```

### Emergency pod restart

```bash
# Delete pod (immediately creates new one)
kubectl delete pod pod-name -n auto-shop

# Or restart entire deployment
kubectl rollout restart deployment/auto-shop-backend -n auto-shop
```

### Isolate pod for debugging

```bash
# Remove from load balancer
kubectl label pod pod-name -n auto-shop debug=true

# Update ingress to exclude debug pods (or use manual routing)

# Restart pod after debugging
kubectl label pod pod-name -n auto-shop debug-
```

---

## Network Policy Debugging

### Test pod can reach service

```bash
# Create debug pod
kubectl run -it debug --image=busybox --rm -n auto-shop -- sh

# Inside pod:
nslookup auto-shop-backend  # Should resolve
telnet auto-shop-backend 8000  # Should connect
```

### Verify network policies

```bash
# List all policies
kubectl get networkpolicies -n auto-shop

# Check specific policy
kubectl get networkpolicy allow-alb-ingress -n auto-shop -o yaml

# View pod network policy status
kubectl describe pod pod-name -n auto-shop
# Look for NetworkPolicy annotations
```

### Temporarily disable network policies

```bash
# Delete specific policy (WARNING: security risk)
kubectl delete networkpolicy allow-dns -n auto-shop

# Or delete all policies
kubectl delete networkpolicies --all -n auto-shop

# Re-apply policies
kubectl apply -f k8s/base/network/network-policy-strict.yaml
```

---

## OIDC Authentication Debugging

### Verify OIDC trust policy

```bash
# Check IAM role trust policy
aws iam get-role --role-name auto-shop-staging-github-pipeline --query 'Role.AssumeRolePolicyDocument'

# Should show StringEquals condition on OIDC subject
```

### Test OIDC token exchange

```bash
# In GitHub Actions workflow, add debug step:
- name: Debug OIDC
  env:
    ACTIONS_STEP_DEBUG: true
  run: |
    aws sts get-caller-identity

# Check logs for AssumeRoleWithWebIdentity calls
aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=AssumeRoleWithWebIdentity --max-results 5
```

---

## Monitoring & Observability

### Check pod resource usage

```bash
kubectl top nodes  # Node CPU/memory
kubectl top pods -n auto-shop  # Pod CPU/memory
```

### View pod logs

```bash
# Current logs
kubectl logs pod-name -n auto-shop

# Follow logs (tail -f)
kubectl logs -f pod-name -n auto-shop

# Previous pod logs (crashed pod)
kubectl logs pod-name -n auto-shop --previous

# All pods in deployment
kubectl logs -l app=auto-shop-backend -n auto-shop
```

### Check pod events

```bash
kubectl describe pod pod-name -n auto-shop
# Look for Events section for errors/warnings
```

---

## Session Lifecycle Management

### Manual session cleanup (if automatic fails)

```bash
# List active sessions in DynamoDB
aws dynamodb scan --table-name auto-shop-staging-lifecycle-sessions --filter-expression "session_scope = :scope" --expression-attribute-values '{":scope":{"S":"infrastructure-only"}}'

# Delete specific session
aws dynamodb delete-item --table-name auto-shop-staging-lifecycle-sessions --key '{"session_id":{"S":"hml-2026-10-31"}}'

# Trigger cleanup workflow manually
gh workflow run lifecycle-cleanup.yml --repo Software-Architecture-Group-7-FIAP/auto-shop-system
```

---

## Cost Monitoring

### Check current spend

```bash
aws ce get-cost-and-usage --time-period Start=2026-10-01,End=2026-10-31 --granularity DAILY --metrics "BlendedCost" --group-by Type=DIMENSION,Key=SERVICE
```

### Set up billing alerts

```bash
aws budgets create-budget --account-id 035611741563 --budget file://budget.json --notifications-with-subscribers file://notifications.json
```

---

**Last Updated:** 2026-10-31
