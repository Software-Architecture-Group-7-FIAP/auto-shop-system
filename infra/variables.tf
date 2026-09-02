variable "environment" {
  description = "Ambiente Kubernetes gerenciado pelo Terraform."
  type        = string
  default     = "local"

  validation {
    condition     = contains(["local", "staging", "production"], var.environment)
    error_message = "environment deve ser local, staging ou production."
  }
}

variable "namespace" {
  description = "Namespace Kubernetes da aplicação."
  type        = string
  default     = "auto-shop"

  validation {
    condition     = can(regex("^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", var.namespace)) && length(var.namespace) <= 63
    error_message = "namespace deve ser um nome DNS-1123 válido com no máximo 63 caracteres."
  }
}

variable "kubeconfig_path" {
  description = "Caminho opcional para o kubeconfig; nulo usa a configuração padrão do provider."
  type        = string
  default     = null
  nullable    = true
}

variable "kube_context" {
  description = "Contexto Kubernetes usado pelo provider."
  type        = string
  default     = null
  nullable    = true
}

variable "image_reference" {
  description = "Imagem da API com tag SHA hexadecimal ou digest; no ambiente local também aceita a tag local."
  type        = string
  default     = "auto-shop-system:local"

  validation {
    condition = (
      can(regex("^.+@sha256:[0-9a-f]{64}$", var.image_reference)) ||
      can(regex("^.+:[0-9a-f]{7,64}$", var.image_reference)) ||
      (var.environment == "local" && can(regex("^.+:local([-.a-zA-Z0-9_]+)?$", var.image_reference)))
    ) && !can(regex("registry\\.example\\.com", var.image_reference))
    error_message = "image_reference deve usar uma tag SHA, digest sha256 ou, somente em local, uma tag local."
  }
}

variable "secret_name" {
  description = "Secret existente que contém DATABASE_URL e as demais credenciais da aplicação."
  type        = string
  default     = "auto-shop-secrets"
}

variable "app_env" {
  description = "Valor APP_ENV usado no ConfigMap."
  type        = string
  default     = "development"

  validation {
    condition = (
      (var.environment == "local" && contains(["development", "dev", "local"], var.app_env)) ||
      (var.environment != "local" && var.app_env == var.environment)
    )
    error_message = "app_env deve ser development/dev/local no ambiente local e igual ao ambiente em staging/production."
  }
}

variable "app_base_url" {
  description = "URL pública base da API."
  type        = string
  default     = "http://localhost:8000"

  validation {
    condition     = var.environment == "local" || can(regex("^https://", var.app_base_url))
    error_message = "app_base_url deve usar HTTPS fora do ambiente local."
  }
}

variable "frontend_public_url" {
  description = "URL pública do frontend."
  type        = string
  default     = "http://localhost:4200"

  validation {
    condition     = var.environment == "local" || can(regex("^https://", var.frontend_public_url))
    error_message = "frontend_public_url deve usar HTTPS fora do ambiente local."
  }
}

variable "cors_allowed_origins" {
  description = "Origens permitidas pelo CORS, separadas por vírgula."
  type        = string
  default     = "http://localhost:4200"

  validation {
    condition     = var.environment == "local" || !can(regex("http://|localhost|127\\.0\\.0\\.1", var.cors_allowed_origins))
    error_message = "cors_allowed_origins não pode apontar para HTTP ou localhost fora do ambiente local."
  }
}

variable "cors_allowed_methods" {
  description = "Métodos permitidos pelo CORS."
  type        = string
  default     = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
}

variable "cors_allowed_headers" {
  description = "Headers permitidos pelo CORS."
  type        = string
  default     = "Authorization,Content-Type,X-CSRF-Token,X-Request-ID,Accept"
}

variable "cors_allow_credentials" {
  description = "Permite credenciais nas requisições CORS."
  type        = bool
  default     = true
}

variable "security_hsts_enabled" {
  description = "Ativa HSTS na aplicação."
  type        = bool
  default     = false

  validation {
    condition     = var.environment == "local" || var.security_hsts_enabled
    error_message = "security_hsts_enabled deve ser true fora do ambiente local."
  }
}

variable "smtp_host" {
  description = "Host SMTP não sensível; credenciais continuam no Secret."
  type        = string
  default     = "mailhog"

  validation {
    condition     = var.environment == "local" || lower(var.smtp_host) != "mailhog"
    error_message = "smtp_host não pode ser mailhog fora do ambiente local."
  }
}

variable "smtp_port" {
  description = "Porta SMTP."
  type        = number
  default     = 1025
}

variable "smtp_from" {
  description = "Remetente padrão de e-mail."
  type        = string
  default     = "noreply@oficina.local"
}

variable "smtp_use_tls" {
  description = "Ativa TLS SMTP."
  type        = bool
  default     = false
}

variable "smtp_starttls" {
  description = "Ativa STARTTLS SMTP."
  type        = bool
  default     = false

  validation {
    condition     = var.environment == "local" || var.smtp_starttls
    error_message = "smtp_starttls deve ser true fora do ambiente local."
  }
}

variable "smtp_require_tls" {
  description = "Exige TLS SMTP."
  type        = bool
  default     = false

  validation {
    condition     = var.environment == "local" || var.smtp_require_tls
    error_message = "smtp_require_tls deve ser true fora do ambiente local."
  }
}

variable "skip_cpf_external_validation" {
  description = "Ignora a validação externa de CPF no ambiente local."
  type        = bool
  default     = true

  validation {
    condition     = var.environment == "local" || !var.skip_cpf_external_validation
    error_message = "A validação externa de CPF não pode ser ignorada fora do ambiente local."
  }
}

variable "replicas" {
  description = "Réplicas iniciais do Deployment; deve ser compatível com o mínimo do HPA."
  type        = number
  default     = 2

  validation {
    condition     = var.replicas >= 2 && var.replicas <= 10
    error_message = "replicas deve estar entre 2 e 10 para manter a disponibilidade mínima."
  }
}

variable "enable_local_database" {
  description = "Cria PostgreSQL, PVC e Service somente para o ambiente local."
  type        = bool
  default     = false

  validation {
    condition     = !var.enable_local_database || var.environment == "local"
    error_message = "enable_local_database=true só é permitido quando environment=local."
  }
}

variable "postgres_image" {
  description = "Imagem do PostgreSQL usado exclusivamente no ambiente local."
  type        = string
  default     = "postgres:16-alpine"
}

variable "postgres_storage" {
  description = "Storage solicitado para o PostgreSQL local."
  type        = string
  default     = "5Gi"
}

variable "enable_ingress" {
  description = "Cria o Ingress da API."
  type        = bool
  default     = true
}

variable "ingress_class_name" {
  description = "IngressClass usado pelo Ingress."
  type        = string
  default     = "nginx"
}

variable "ingress_host" {
  description = "Host do Ingress; nulo gera uma regra sem host para uso local."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition = (
      (var.environment == "local" && (var.ingress_host == null || can(regex("^[a-z0-9.-]+$", var.ingress_host)))) ||
      (var.environment != "local" && var.ingress_host != null && can(regex("^[a-z0-9.-]+$", var.ingress_host)))
    )
    error_message = "ingress_host é opcional apenas em local e deve ser um hostname válido nos demais ambientes."
  }
}

variable "ingress_tls_secret_name" {
  description = "Secret TLS usado em ambientes com HTTPS."
  type        = string
  default     = "auto-shop-tls"
}
