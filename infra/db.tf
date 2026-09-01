resource "kubernetes_persistent_volume_claim_v1" "postgres" {
  count = var.enable_local_database ? 1 : 0

  metadata {
    name      = "postgres-pvc"
    namespace = kubernetes_namespace_v1.auto_shop.metadata[0].name
    labels    = local.database_labels
  }

  spec {
    access_modes = ["ReadWriteOnce"]

    resources {
      requests = {
        storage = var.postgres_storage
      }
    }
  }
}

resource "kubernetes_deployment_v1" "postgres" {
  count = var.enable_local_database ? 1 : 0

  metadata {
    name      = "postgres"
    namespace = kubernetes_namespace_v1.auto_shop.metadata[0].name
    labels    = local.database_labels
  }

  spec {
    replicas = 1

    strategy {
      type = "Recreate"
    }

    selector {
      match_labels = {
        app = "postgres"
      }
    }

    template {
      metadata {
        labels = local.database_labels
      }

      spec {
        termination_grace_period_seconds = 60

        container {
          name              = "postgres"
          image             = var.postgres_image
          image_pull_policy = "IfNotPresent"

          port {
            name           = "postgres"
            container_port = 5432
          }

          env {
            name = "POSTGRES_DB"

            value_from {
              secret_key_ref {
                name = var.secret_name
                key  = "DB_NAME"
              }
            }
          }

          env {
            name = "POSTGRES_USER"

            value_from {
              secret_key_ref {
                name = var.secret_name
                key  = "DB_USER"
              }
            }
          }

          env {
            name = "POSTGRES_PASSWORD"

            value_from {
              secret_key_ref {
                name = var.secret_name
                key  = "DB_PASSWORD"
              }
            }
          }

          volume_mount {
            name       = "postgres-data"
            mount_path = "/var/lib/postgresql/data"
          }

          resources {
            requests = {
              cpu    = "100m"
              memory = "256Mi"
            }

            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
          }

          startup_probe {
            exec {
              command = ["sh", "-c", "pg_isready -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\""]
            }

            period_seconds    = 5
            timeout_seconds   = 3
            failure_threshold = 30
          }

          readiness_probe {
            exec {
              command = ["sh", "-c", "pg_isready -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\""]
            }

            period_seconds    = 5
            timeout_seconds   = 3
            failure_threshold = 3
          }

          liveness_probe {
            exec {
              command = ["sh", "-c", "pg_isready -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\""]
            }

            initial_delay_seconds = 15
            period_seconds        = 15
            timeout_seconds       = 3
            failure_threshold     = 3
          }
        }

        volume {
          name = "postgres-data"

          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim_v1.postgres[0].metadata[0].name
          }
        }
      }
    }
  }

  depends_on = [kubernetes_persistent_volume_claim_v1.postgres]
}

resource "kubernetes_service_v1" "postgres" {
  count = var.enable_local_database ? 1 : 0

  metadata {
    name      = "postgres-service"
    namespace = kubernetes_namespace_v1.auto_shop.metadata[0].name
    labels    = local.database_labels
  }

  spec {
    type = "ClusterIP"

    selector = {
      app = "postgres"
    }

    port {
      name        = "postgres"
      port        = 5432
      target_port = "postgres"
    }
  }
}
