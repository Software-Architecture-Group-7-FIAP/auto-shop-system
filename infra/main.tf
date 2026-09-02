terraform {
  required_version = ">= 1.6.0"

  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.35"
    }
  }
}

provider "kubernetes" {
  config_path    = var.kubeconfig_path
  config_context = var.kube_context
}

locals {
  common_labels = {
    "app.kubernetes.io/name"        = "auto-shop-system"
    "app.kubernetes.io/part-of"     = "auto-shop-platform"
    "app.kubernetes.io/environment" = var.environment
  }

  backend_labels = merge(local.common_labels, {
    "app.kubernetes.io/component" = "backend"
    app                           = "auto-shop-backend"
  })

  migration_labels = merge(local.common_labels, {
    "app.kubernetes.io/component" = "migrate"
    app                           = "auto-shop-migrate"
  })

  database_labels = merge(local.common_labels, {
    "app.kubernetes.io/component" = "database"
    app                           = "postgres"
  })

  backend_name       = "auto-shop-backend"
  backend_service    = "auto-shop-backend-service"
  config_map_name    = "auto-shop-config"
  migration_job_name = "auto-shop-migrate-${substr(sha256(var.image_reference), 0, 12)}"
}
