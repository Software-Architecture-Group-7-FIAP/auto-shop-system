# New Relic Kubernetes telemetry in HML

The HML application deployer is namespace-scoped. It creates or updates the
`auto-shop-new-relic` Secret in `auto-shop-hml`, but it does not install
cluster-scoped New Relic resources. The official `newrelic/nri-bundle` Helm
release is managed by the privileged Terraform platform stack in
[`k8s-infra/envs/staging/platform`](https://github.com/Software-Architecture-Group-7-FIAP/k8s-infra/tree/main/envs/staging/platform).
This keeps ClusterRoles and ClusterRoleBindings out of the application role.

## HML installation sequence

1. Deploy the application in an approved HML session. The deploy workflow
   materializes `NEW_RELIC_LICENSE_KEY` as the `auto-shop-new-relic` Secret
   without writing the value to manifests, command arguments, logs, or Git.
2. Run [`cluster-ci.yml`](https://github.com/Software-Architecture-Group-7-FIAP/k8s-infra/blob/main/.github/workflows/cluster-ci.yml)
   on `k8s-infra/main` with stack `platform` and review the saved Terraform
   plan. The plan workflow downloads `nri-bundle` version `8.0.39` and
   verifies SHA-256
   `96eb019f7c78e1e746e0ba170b7e656e437ae3f7bfe7203f812e750511db108f`.
3. Apply that exact reviewed plan through
   [`cluster-apply.yml`](https://github.com/Software-Architecture-Group-7-FIAP/k8s-infra/blob/main/.github/workflows/cluster-apply.yml)
   in the same authorized HML session. The platform stack installs the chart in
   the existing `auto-shop-hml` namespace; it does not create or patch the
   namespace.

The plan and apply workflows retain their existing lifecycle authorization,
runner allowlist, saved-plan attestation, plan guard, and explicit apply
confirmation. Do not grant the application deploy role cluster-wide access or
install this chart using that role.

## Collection boundary

The platform values enable the New Relic infrastructure integration and its
bundled `kube-state-metrics`. `global.lowDataMode` increases the
infrastructure scrape interval from 15 to 30 seconds while preserving the
Kubernetes samples used by the New Relic UI. KSM label and annotation metric
allowlists are empty. The self-managed control-plane collector is disabled
because EKS owns the control plane.

Log forwarding, Kubernetes events, Prometheus scraping, metadata injection,
Pixie, eBPF, agent injection, the infrastructure operator, and the New Relic
HPA metrics adapter are explicitly disabled. Application logs remain governed
by the bounded and redacted APM configuration documented in
[`new-relic-fastapi-apm.md`](new-relic-fastapi-apm.md).

The chart reads `NEW_RELIC_LICENSE_KEY` from the existing Secret. The key is
not committed to Helm values, source-controlled manifests, images, or logs.

## Authorized validation

Run these checks only inside an approved HML session, after the platform apply
succeeds. Record the lifecycle session ID, UTC timestamp, Helm release status,
and bounded query results as evidence. Do not record credentials or raw
telemetry payloads.

First confirm the in-cluster heartbeat:

```bash
helm status auto-shop-new-relic --namespace auto-shop-hml
kubectl get pods --namespace auto-shop-hml \
  --selector app.kubernetes.io/instance=auto-shop-new-relic
```

Then use New Relic's query builder with a recent bounded window. Each query
must return at least one current sample for
`clusterName = 'auto-shop-hml'`:

```sql
FROM K8sClusterSample
SELECT latest(timestamp)
WHERE clusterName = 'auto-shop-hml'
SINCE 10 minutes ago

FROM K8sNodeSample
SELECT latest(cpuUsedCores), latest(memoryWorkingSetBytes)
WHERE clusterName = 'auto-shop-hml'
FACET nodeName
SINCE 10 minutes ago

FROM K8sPodSample
SELECT latest(cpuUsedCores), latest(memoryWorkingSetBytes), latest(isReady)
WHERE clusterName = 'auto-shop-hml'
FACET namespaceName, deploymentName, podName
SINCE 10 minutes ago

FROM K8sContainerSample
SELECT latest(restartCount)
WHERE clusterName = 'auto-shop-hml'
FACET namespaceName, deploymentName, podName, containerName
SINCE 10 minutes ago

FROM K8sHpaSample
SELECT latest(currentReplicas), latest(desiredReplicas)
WHERE clusterName = 'auto-shop-hml'
FACET namespaceName, displayName
SINCE 10 minutes ago
```

The node query proves CPU and memory by node. The pod and container queries
provide namespace and workload dimensions, readiness, and restarts. The HPA
query compares current and desired replicas.

## Lifecycle and teardown

The release is installed only in the session-scoped HML cluster. The normal
[`environment-stop.yml`](https://github.com/Software-Architecture-Group-7-FIAP/k8s-infra/blob/main/.github/workflows/environment-stop.yml)
lifecycle destroys the EKS platform stack, including the Helm release,
cluster-scoped RBAC, DaemonSets, Deployments, and Secret. Complete the existing
post-destroy orphan audit before accepting lifecycle evidence. Local tests and
ordinary CI runs must never install the integration into HML.
