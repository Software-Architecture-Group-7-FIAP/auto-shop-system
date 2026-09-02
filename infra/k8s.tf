resource "kubernetes_namespace_v1" "auto_shop" {
  metadata {
    name   = var.namespace
    labels = local.common_labels
  }

  lifecycle {
    precondition {
      condition = (
        (var.environment == "local" && contains(["development", "dev", "local"], var.app_env)) ||
        (var.environment != "local" && var.app_env == var.environment)
      )
      error_message = "app_env deve ser development/dev/local no ambiente local e igual ao ambiente em staging/production."
    }

    precondition {
      condition     = var.environment == "local" || !can(regex("^.+:local([-.a-zA-Z0-9_]+)?$", var.image_reference))
      error_message = "image_reference com tag local sÃ³ pode ser usado no ambiente local."
    }

    precondition {
      condition     = var.environment == "local" || can(regex("^https://", var.app_base_url))
      error_message = "app_base_url deve usar HTTPS fora do ambiente local."
    }

    precondition {
      condition     = var.environment == "local" || can(regex("^https://", var.frontend_public_url))
      error_message = "frontend_public_url deve usar HTTPS fora do ambiente local."
    }

    precondition {
      condition     = var.environment == "local" || !can(regex("http://|localhost|127\\.0\\.0\\.1", var.cors_allowed_origins))
      error_message = "cors_allowed_origins nÃ£o pode apontar para HTTP ou localhost fora do ambiente local."
    }

    precondition {
      condition     = var.environment == "local" || var.security_hsts_enabled
      error_message = "security_hsts_enabled deve ser true fora do ambiente local."
    }

    precondition {
      condition     = var.environment == "local" || lower(var.smtp_host) != "mailhog"
      error_message = "smtp_host nÃ£o pode ser mailhog fora do ambiente local."
    }

    precondition {
      condition     = var.environment == "local" || var.smtp_starttls
      error_message = "smtp_starttls deve ser true fora do ambiente local."
    }

    precondition {
      condition     = var.environment == "local" || var.smtp_require_tls
      error_message = "smtp_require_tls deve ser true fora do ambiente local."
    }

    precondition {
      condition     = var.environment == "local" || !var.skip_cpf_external_validation
      error_message = "A validaÃ§Ã£o externa de CPF nÃ£o pode ser ignorada fora do ambiente local."
    }

    precondition {
      condition     = !var.enable_local_database || var.environment == "local"
      error_message = "enable_local_database=true sÃ³ Ã© permitido quando environment=local."
    }

    precondition {
      condition     = var.environment == "local" || var.ingress_host != null
      error_message = "ingress_host Ã© obrigatÃ³rio fora do ambiente local."
    }
  }
}

resource "kubernetes_config_map_v1" "app" {
  metadata {
    name      = local.config_map_name
    namespace = kubernetes_namespace_v1.auto_shop.metadata[0].name
    labels    = local.common_labels
  }

  data = {
    APP_ENV                      = var.app_env
    APP_BASE_URL                 = var.app_base_url
    FRONTEND_PUBLIC_URL          = var.frontend_public_url
    CORS_ALLOWED_ORIGINS         = var.cors_allowed_origins
    CORS_ALLOWED_METHODS         = var.cors_allowed_methods
    CORS_ALLOWED_HEADERS         = var.cors_allowed_headers
    CORS_ALLOW_CREDENTIALS       = tostring(var.cors_allow_credentials)
    SECURITY_HSTS_ENABLED        = tostring(var.security_hsts_enabled)
    SMTP_HOST                    = var.smtp_host
    SMTP_PORT                    = tostring(var.smtp_port)
    SMTP_FROM                    = var.smtp_from
    SMTP_USE_TLS                 = tostring(var.smtp_use_tls)
    SMTP_STARTTLS                = tostring(var.smtp_starttls)
    SMTP_REQUIRE_TLS             = tostring(var.smtp_require_tls)
    AUTO_CREATE_SCHEMA           = "false"
    SKIP_CPF_EXTERNAL_VALIDATION = tostring(var.skip_cpf_external_validation)
  }
}

resource "kubernetes_job_v1" "migration" {
  metadata {
    name      = local.migration_job_name
    namespace = kubernetes_namespace_v1.auto_shop.metadata[0].name
    labels    = local.migration_labels
  }

  wait_for_completion = true

  spec {
    backoff_limit           = 1
    active_deadline_seconds = 300

    template {
      metadata {
        labels = local.migration_labels
      }

      spec {
        restart_policy                   = "OnFailure"
        termination_grace_period_seconds = 30

        security_context {
          run_as_non_root = true
          run_as_user     = 10001
          run_as_group    = 10001
          fs_group        = 10001

          seccomp_profile {
            type = "RuntimeDefault"
          }
        }

        container {
          name              = "alembic"
          image             = var.image_reference
          image_pull_policy = "IfNotPresent"
          command           = ["sh", "-c"]
          args = [
            "set -eu; attempt=1; until python -c 'import os, psycopg2; connection=psycopg2.connect(os.environ[\"DATABASE_URL\"], connect_timeout=2); connection.close()'; do if [ \"$attempt\" -ge 5 ]; then echo \"migration preflight failed: database unavailable\"; exit 10; fi; echo \"migration preflight: database unavailable, retry $attempt/4\"; attempt=$((attempt + 1)); sleep 5; done; echo \"migration preflight complete\"; migration_status=0; python -m src.scripts.run_migrations || migration_status=$?; if [ \"$migration_status\" -eq 10 ]; then echo \"migration failed: database unavailable while acquiring lock\"; exit 10; fi; if [ \"$migration_status\" -ne 0 ]; then echo \"migration failed\"; exit 20; fi"
          ]

          env_from {
            config_map_ref {
              name = kubernetes_config_map_v1.app.metadata[0].name
            }
          }

          env_from {
            secret_ref {
              name = var.secret_name
            }
          }

          security_context {
            allow_privilege_escalation = false
            read_only_root_filesystem  = true

            capabilities {
              drop = ["ALL"]
            }
          }

          volume_mount {
            name       = "tmp"
            mount_path = "/tmp"
          }
        }

        volume {
          name = "tmp"

          empty_dir {}
        }
      }
    }
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    kubernetes_config_map_v1.app,
    kubernetes_deployment_v1.postgres,
  ]
}

resource "kubernetes_deployment_v1" "backend" {
  metadata {
    name      = local.backend_name
    namespace = kubernetes_namespace_v1.auto_shop.metadata[0].name
    labels    = local.backend_labels
  }

  spec {
    replicas                  = var.replicas
    revision_history_limit    = 5
    min_ready_seconds         = 5
    progress_deadline_seconds = 600

    selector {
      match_labels = {
        app = "auto-shop-backend"
      }
    }

    strategy {
      type = "RollingUpdate"

      rolling_update {
        max_unavailable = "0"
        max_surge       = "1"
      }
    }

    template {
      metadata {
        labels = local.backend_labels
      }

      spec {
        restart_policy                   = "Always"
        termination_grace_period_seconds = 30

        security_context {
          run_as_non_root = true
          run_as_user     = 10001
          run_as_group    = 10001
          fs_group        = 10001

          seccomp_profile {
            type = "RuntimeDefault"
          }
        }

        container {
          name              = "backend-api"
          image             = var.image_reference
          image_pull_policy = "IfNotPresent"
          command           = ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

          port {
            name           = "http"
            container_port = 8000
            protocol       = "TCP"
          }

          env_from {
            config_map_ref {
              name = kubernetes_config_map_v1.app.metadata[0].name
            }
          }

          env_from {
            secret_ref {
              name = var.secret_name
            }
          }

          resources {
            requests = {
              cpu    = "250m"
              memory = "256Mi"
            }

            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
          }

          startup_probe {
            http_get {
              path = "/health/live"
              port = "http"
            }

            period_seconds    = 5
            timeout_seconds   = 3
            failure_threshold = 30
          }

          liveness_probe {
            http_get {
              path = "/health/live"
              port = "http"
            }

            period_seconds    = 15
            timeout_seconds   = 3
            failure_threshold = 3
          }

          readiness_probe {
            http_get {
              path = "/health/ready"
              port = "http"
            }

            period_seconds    = 5
            timeout_seconds   = 3
            success_threshold = 1
            failure_threshold = 3
          }

          security_context {
            allow_privilege_escalation = false
            read_only_root_filesystem  = true

            capabilities {
              drop = ["ALL"]
            }
          }

          volume_mount {
            name       = "tmp"
            mount_path = "/tmp"
          }
        }

        volume {
          name = "tmp"

          empty_dir {}
        }
      }
    }
  }

  depends_on = [kubernetes_job_v1.migration]
}

resource "kubernetes_service_v1" "backend" {
  metadata {
    name      = local.backend_service
    namespace = kubernetes_namespace_v1.auto_shop.metadata[0].name
    labels    = local.backend_labels
  }

  spec {
    type = "ClusterIP"

    selector = {
      app = "auto-shop-backend"
    }

    port {
      name        = "http"
      port        = 80
      target_port = "http"
    }
  }
}

resource "kubernetes_horizontal_pod_autoscaler_v2" "backend" {
  metadata {
    name      = "auto-shop-backend-hpa"
    namespace = kubernetes_namespace_v1.auto_shop.metadata[0].name
    labels    = local.backend_labels
  }

  spec {
    min_replicas = 2
    max_replicas = 10

    scale_target_ref {
      api_version = "apps/v1"
      kind        = "Deployment"
      name        = kubernetes_deployment_v1.backend.metadata[0].name
    }

    metric {
      type = "Resource"

      resource {
        name = "cpu"

        target {
          type                = "Utilization"
          average_utilization = 70
        }
      }
    }

    metric {
      type = "Resource"

      resource {
        name = "memory"

        target {
          type                = "Utilization"
          average_utilization = 80
        }
      }
    }

    behavior {
      scale_up {
        stabilization_window_seconds = 0
        select_policy                = "Max"

        policy {
          type           = "Percent"
          value          = 100
          period_seconds = 15
        }

        policy {
          type           = "Pods"
          value          = 2
          period_seconds = 15
        }
      }

      scale_down {
        stabilization_window_seconds = 300
        select_policy                = "Min"

        policy {
          type           = "Percent"
          value          = 10
          period_seconds = 60
        }
      }
    }
  }
}

resource "kubernetes_ingress_v1" "backend" {
  count = var.enable_ingress ? 1 : 0

  metadata {
    name      = "auto-shop-ingress"
    namespace = kubernetes_namespace_v1.auto_shop.metadata[0].name
    labels    = merge(local.common_labels, { "app.kubernetes.io/component" = "ingress" })
    annotations = var.environment == "local" ? {
      "nginx.ingress.kubernetes.io/ssl-redirect" = "false"
      } : {
      "nginx.ingress.kubernetes.io/ssl-redirect"       = "true"
      "nginx.ingress.kubernetes.io/force-ssl-redirect" = "true"
    }
  }

  spec {
    ingress_class_name = var.ingress_class_name

    dynamic "tls" {
      for_each = var.environment == "local" ? [] : [true]

      content {
        hosts       = [var.ingress_host]
        secret_name = var.ingress_tls_secret_name
      }
    }

    rule {
      host = var.ingress_host

      http {
        path {
          path      = "/"
          path_type = "Prefix"

          backend {
            service {
              name = kubernetes_service_v1.backend.metadata[0].name

              port {
                number = 80
              }
            }
          }
        }
      }
    }
  }
}
