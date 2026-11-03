# New Relic Kubernetes telemetry in HML

The HML deployment installs the official `newrelic/nri-bundle` Helm chart at the
version pinned in `k8s/scripts/deploy.sh`. It runs only during an approved HML
session and uses the stable cluster identity `auto-shop-hml`.

## Collection boundary

The bundle enables the New Relic infrastructure integration and its bundled
`kube-state-metrics`. `global.lowDataMode` increases the infrastructure scrape
interval from 15 to 30 seconds while preserving the Kubernetes samples used by
the New Relic UI. KSM label and annotation metric allowlists are empty. The
self-managed control-plane collector is disabled because EKS owns the control
plane.

Log forwarding, Kubernetes events, Prometheus scraping, metadata injection,
Pixie, eBPF, agent injection, the infrastructure operator, and the New Relic HPA
metrics adapter are explicitly disabled. Application logs remain governed by
the bounded and redacted APM configuration documented in
[`new-relic-fastapi-apm.md`](new-relic-fastapi-apm.md).

The chart reads `NEW_RELIC_LICENSE_KEY` from the existing
`auto-shop-new-relic` Secret. The key is not committed to Helm values,
source-controlled manifests, images, or logs, and is removed from the deploy
process environment immediately after Secret creation. The official chart
archive and Helm setup action are pinned by cryptographic hashes. Deployment
uses `--atomic`, `--wait`, and a bounded timeout, so a failed installation is
rolled back.

## Authorized validation

Run these checks only inside the approved HML session, after the application
deployment succeeds. Record the lifecycle session ID, UTC timestamp, Helm
release status and query results as evidence. Do not record credentials or raw
telemetry payloads.

First confirm the in-cluster heartbeat:

```bash
helm status auto-shop-new-relic --namespace auto-shop-hml
kubectl get pods --namespace auto-shop-hml \
  --selector app.kubernetes.io/instance=auto-shop-new-relic
```

Then use New Relic's query builder with a recent bounded window. Each query must
return at least one current sample for `clusterName = 'auto-shop-hml'`:

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

The release is installed only in the session-scoped HML cluster and namespace.
The normal `.github/workflows/environment-stop.yml` lifecycle destroys the EKS
platform stack; therefore the Helm release, cluster-scoped RBAC, DaemonSets,
Deployments, and Secrets cannot remain after the session. Complete the existing
post-destroy orphan audit before accepting the lifecycle evidence. A local test
or ordinary CI run must never install the integration into HML.
