output "namespace" {
  description = "Namespace Kubernetes gerenciado."
  value       = kubernetes_namespace_v1.auto_shop.metadata[0].name
}

output "backend_deployment" {
  description = "Nome do Deployment do backend."
  value       = kubernetes_deployment_v1.backend.metadata[0].name
}

output "backend_service" {
  description = "Nome do Service do backend."
  value       = kubernetes_service_v1.backend.metadata[0].name
}

output "backend_hpa" {
  description = "Nome do HPA do backend."
  value       = kubernetes_horizontal_pod_autoscaler_v2.backend.metadata[0].name
}

output "migration_job" {
  description = "Nome do Job de migration associado à imagem implantada."
  value       = kubernetes_job_v1.migration.metadata[0].name
}

output "postgres_service" {
  description = "Nome do Service PostgreSQL quando o banco local está habilitado."
  value       = var.enable_local_database ? kubernetes_service_v1.postgres[0].metadata[0].name : null
}
