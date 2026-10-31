locals {
  cloudfront_cache_policy_ids = {
    caching_optimized = "658327ea-f89d-4fab-a63d-7e88639e58f6"
    caching_disabled  = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
  }

  frontend_api_paths = toset([
    "api/*",
    "auth/*",
    ".well-known/*",
  ])

  api_origin_domain = var.enable_custom_domains ? var.api_domain_name : "${aws_api_gateway_rest_api.main.id}.execute-api.${data.aws_region.current.region}.amazonaws.com"
}

resource "aws_s3_bucket" "frontend" {
  for_each = local.api_stages

  bucket = "${local.name_prefix}-${each.key}-frontend-${data.aws_caller_identity.current.account_id}"

  tags = merge(local.common_tags, {
    Name        = "${local.name_prefix}-${each.key}-frontend"
    ApiStage    = each.key
    Environment = each.key
  })
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  for_each = local.api_stages

  bucket                  = aws_s3_bucket.frontend[each.key].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "frontend" {
  for_each = local.api_stages

  bucket = aws_s3_bucket.frontend[each.key].id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_versioning" "frontend" {
  for_each = local.api_stages

  bucket = aws_s3_bucket.frontend[each.key].id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "frontend" {
  for_each = local.api_stages

  bucket = aws_s3_bucket.frontend[each.key].id

  rule {
    id     = "expire-replaced-frontend-assets"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 7
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  depends_on = [aws_s3_bucket_versioning.frontend]
}

resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  for_each = local.api_stages

  bucket = aws_s3_bucket.frontend[each.key].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${local.name_prefix}-frontend-oac"
  description                       = "Private S3 access for the Auto Shop Angular frontends."
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_response_headers_policy" "security" {
  name    = "${local.name_prefix}-frontend-security-headers"
  comment = "Browser security headers for the Auto Shop frontend and proxied API."

  security_headers_config {
    content_security_policy {
      content_security_policy = "default-src 'self'; base-uri 'self'; connect-src 'self'; font-src 'self' data:; frame-ancestors 'none'; img-src 'self' data:; object-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'"
      override                = true
    }

    content_type_options {
      override = true
    }

    frame_options {
      frame_option = "DENY"
      override     = true
    }

    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }

    strict_transport_security {
      access_control_max_age_sec = 31536000
      include_subdomains         = true
      preload                    = true
      override                   = true
    }
  }
}

resource "aws_cloudfront_function" "spa_rewrite" {
  name    = "${local.name_prefix}-frontend-spa-rewrite"
  runtime = "cloudfront-js-1.0"
  publish = true
  code    = <<-EOT
    function handler(event) {
      var request = event.request;
      var uri = request.uri;
      var lastSegment = uri.substring(uri.lastIndexOf("/") + 1);

      if (uri === "/" || lastSegment.indexOf(".") === -1) {
        request.uri = "/index.html";
      }

      return request;
    }
  EOT
}

resource "aws_cloudfront_distribution" "frontend" {
  for_each = local.api_stages

  enabled             = true
  is_ipv6_enabled     = true
  comment             = "${local.name_prefix} ${each.key} Angular application"
  default_root_object = "index.html"
  aliases             = var.enable_custom_domains ? [var.frontend_domains[each.key]] : []
  price_class         = "PriceClass_100"
  web_acl_id          = aws_wafv2_web_acl.cloudfront.arn

  origin {
    domain_name              = aws_s3_bucket.frontend[each.key].bucket_regional_domain_name
    origin_id                = "frontend-s3-${each.key}"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id

    s3_origin_config {
      origin_access_identity = ""
    }
  }

  origin {
    domain_name = local.api_origin_domain
    origin_id   = "api-gateway-${each.key}"
    origin_path = "/${each.key}"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD"]
    target_origin_id           = "frontend-s3-${each.key}"
    viewer_protocol_policy     = "redirect-to-https"
    compress                   = true
    cache_policy_id            = local.cloudfront_cache_policy_ids.caching_optimized
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.spa_rewrite.arn
    }
  }

  dynamic "ordered_cache_behavior" {
    for_each = local.frontend_api_paths

    content {
      path_pattern               = ordered_cache_behavior.value
      allowed_methods            = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
      cached_methods             = ["GET", "HEAD"]
      target_origin_id           = "api-gateway-${each.key}"
      viewer_protocol_policy     = "redirect-to-https"
      compress                   = true
      cache_policy_id            = local.cloudfront_cache_policy_ids.caching_disabled
      origin_request_policy_id   = "b689b0a8-53d0-40ab-baf2-68738e2966ac"
      response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn            = var.enable_custom_domains ? aws_acm_certificate_validation.public_domains[0].certificate_arn : null
    cloudfront_default_certificate = !var.enable_custom_domains
    minimum_protocol_version       = var.enable_custom_domains ? "TLSv1.2_2021" : null
    ssl_support_method             = var.enable_custom_domains ? "sni-only" : null
  }

  tags = merge(local.common_tags, {
    Name     = "${local.name_prefix}-frontend-${each.key}"
    ApiStage = each.key
  })
}

data "aws_iam_policy_document" "frontend_bucket" {
  for_each = local.api_stages

  statement {
    sid       = "AllowCloudFrontReadOnly"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.frontend[each.key].arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.frontend[each.key].arn]
    }
  }


  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.frontend[each.key].arn,
      "${aws_s3_bucket.frontend[each.key].arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "frontend" {
  for_each = local.api_stages

  bucket = aws_s3_bucket.frontend[each.key].id
  policy = data.aws_iam_policy_document.frontend_bucket[each.key].json
}

resource "aws_ssm_parameter" "frontend_bucket_name" {
  for_each = local.api_stages

  name  = "${trimsuffix(var.upstream_ssm_prefix, "/")}/frontend/${each.key}/bucket-name"
  type  = "String"
  value = aws_s3_bucket.frontend[each.key].bucket

  tags = local.common_tags
}

resource "aws_ssm_parameter" "frontend_distribution_id" {
  for_each = local.api_stages

  name  = "${trimsuffix(var.upstream_ssm_prefix, "/")}/frontend/${each.key}/distribution-id"
  type  = "String"
  value = aws_cloudfront_distribution.frontend[each.key].id

  tags = local.common_tags
}

output "frontend_deploy_targets" {
  description = "Non-sensitive SSM parameter names for the stage-specific static frontend deployments."
  value = {
    for stage in local.api_stages : stage => {
      bucket_parameter          = aws_ssm_parameter.frontend_bucket_name[stage].name
      distribution_id_parameter = aws_ssm_parameter.frontend_distribution_id[stage].name
      distribution_domain       = aws_cloudfront_distribution.frontend[stage].domain_name
    }
  }
}
