# Issue #05 HML Runtime — HTTPS Edge & K8s Infrastructure Deployment

## Status: Ready for HML Runtime Execution

### Infrastructure Code Generated ✅

**K8s Configuration Files:**
- `k8s/base/network/network-policy-strict.yaml` — Strict default-deny with explicit allow-lists
  - Default deny ingress
  - Allow DNS egress to kube-system
  - Allow ALB ingress on ports 8000, 8080
  - Allow RDS egress on port 5432
  - Allow external HTTPS/HTTP egress
  
- `k8s/base/network/kustomization.yaml` — Network policy kustomize deployment

- `k8s/overlays/production/ingress/ingress-patch.yaml` — HTTPS ingress with TLS
  - Host: api.autoshop.com
  - TLS certificate: auto-shop-tls-cert
  - Backend service routing

- `k8s/overlays/production/ingress/kustomization.yaml` — Production ingress overlay

**Terraform Plan Summary:**
```
Plan: 7 resources to add
- kubernetes_namespace_v1 (auto_shop)
- kubernetes_config_map_v1 (app configuration)
- kubernetes_deployment_v1 (backend with 2 replicas)
- kubernetes_service_v1 (backend service)
- kubernetes_horizontal_pod_autoscaler_v1 (backend HPA)
- kubernetes_job_v1 (database migration)
+ Others defined in k8s.tf
```

### Deployment Sequence

1. **Kubernetes Namespace** → Creates `auto-shop` namespace
2. **Network Policies** → Applies strict default-deny rules
3. **ConfigMaps** → App configuration (environment variables)
4. **Database Migration Job** → Pre-deployment schema setup
5. **Backend Deployment** → 2 replicas with rolling update strategy
6. **Service & Ingress** → ALB integration + HTTPS endpoint
7. **HPA** → Auto-scaling based on CPU/memory metrics

### HML Runtime Validation (GitHub Actions)

Execution path in production:
1. Push to `develop` branch triggers `lifecycle:push-*:app-deploy`
2. Terraform initialized and applied against EKS cluster
3. Digest-based image deployment (Issue #04 validated)
4. OIDC role assumption (Issue #02 validated)
5. NetworkPolicy enforcement active
6. Synthetic tests verify:
   - Pod network isolation
   - DNS resolution within cluster
   - ALB ingress connectivity
   - RDS database connectivity

### Known Constraints

- Local Kubernetes cluster not available (error: localhost:80 refused)
- Full deployment validation occurs in HML environment via GitHub Actions
- Terraform state management via AWS S3 backend (configured in bootstrap)

### Next Steps

1. ✅ Network policies defined
2. ✅ Ingress configuration for HTTPS/edge
3. ✅ Terraform plan generated
4. 🔄 **Deploy to HML**: Triggered automatically via GitHub Actions on develop branch
5. 🔄 **Verify connectivity**: Check pod logs, service endpoints, ingress status
6. 🔄 **Run synthetic tests**: Validate network isolation and routing

### Deployment Readiness Criteria

- [x] K8s namespace configuration defined
- [x] Network policies (strict mode) configured
- [x] Production ingress with HTTPS defined
- [x] Terraform resources ready for EKS deployment
- [x] Database migration job defined
- [x] Deployment replication and HPA configured
- [ ] Deployed to HML EKS cluster (automated via GitHub Actions)
- [ ] Health checks passing
- [ ] Synthetic tests passing

---

**Issue #05 Status:** Ready for HML environment deployment  
**Deployment Method:** GitHub Actions + Terraform (automatic on develop push)  
**Validation:** Live EKS cluster network policy enforcement + pod isolation tests
