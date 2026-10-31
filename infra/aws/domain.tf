resource "aws_acm_certificate" "public_domains" {
  domain_name               = var.api_domain_name
  subject_alternative_names = values(var.frontend_domains)
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-public-domains"
  })
}

resource "aws_acm_certificate_validation" "public_domains" {
  count = var.enable_custom_domains ? 1 : 0

  certificate_arn = aws_acm_certificate.public_domains.arn
  validation_record_fqdns = [
    for option in aws_acm_certificate.public_domains.domain_validation_options :
    option.resource_record_name
  ]
}

resource "aws_api_gateway_domain_name" "main" {
  count = var.enable_custom_domains ? 1 : 0

  domain_name              = var.api_domain_name
  regional_certificate_arn = aws_acm_certificate_validation.public_domains[0].certificate_arn
  security_policy          = "TLS_1_2"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = local.common_tags
}

resource "aws_api_gateway_base_path_mapping" "main" {
  for_each = var.enable_custom_domains ? local.api_stages : toset([])

  api_id      = aws_api_gateway_rest_api.main.id
  stage_name  = aws_api_gateway_stage.main[each.key].stage_name
  domain_name = aws_api_gateway_domain_name.main[0].domain_name
  base_path   = each.key
}

output "acm_dns_validation_records" {
  description = "CNAME records to publish in Registro.br before enabling custom domains."
  value = [
    for option in aws_acm_certificate.public_domains.domain_validation_options : {
      domain = option.domain_name
      name   = option.resource_record_name
      type   = option.resource_record_type
      value  = option.resource_record_value
    }
  ]
}
