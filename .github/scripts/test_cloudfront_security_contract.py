import unittest
from pathlib import Path


CLOUDFRONT = (
    Path(__file__).resolve().parents[2] / "infra" / "aws" / "cloudfront.tf"
)


class CloudFrontSecurityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.content = CLOUDFRONT.read_text(encoding="utf-8")

    def test_uses_execute_api_origin_until_custom_domain_is_enabled(self) -> None:
        self.assertIn("var.enable_custom_domains ? var.api_domain_name", self.content)
        self.assertIn("execute-api.${data.aws_region.current.region}.amazonaws.com", self.content)
        self.assertIn("domain_name = local.api_origin_domain", self.content)

    def test_private_buckets_reject_plain_http(self) -> None:
        self.assertRegex(self.content, r'\bsid\s*=\s*"DenyInsecureTransport"')
        self.assertIn('variable = "aws:SecureTransport"', self.content)
        self.assertIn('values   = ["false"]', self.content)

    def test_frontend_objects_are_versioned_and_old_versions_expire(self) -> None:
        self.assertIn('resource "aws_s3_bucket_versioning" "frontend"', self.content)
        self.assertIn('status = "Enabled"', self.content)
        self.assertIn("noncurrent_version_expiration", self.content)

    def test_cloudfront_adds_browser_security_headers(self) -> None:
        self.assertIn(
            'resource "aws_cloudfront_response_headers_policy" "security"',
            self.content,
        )
        self.assertIn("content_security_policy", self.content)
        self.assertIn("strict_transport_security", self.content)
        self.assertGreaterEqual(self.content.count("response_headers_policy_id"), 2)

    def test_health_endpoints_are_not_routed_through_public_edges(self) -> None:
        api_gateway = (
            Path(__file__).resolve().parents[2] / "infra" / "aws" / "api_gateway.tf"
        ).read_text(encoding="utf-8")

        self.assertNotIn('resource "aws_api_gateway_resource" "health"', api_gateway)
        self.assertNotIn('resource "aws_api_gateway_integration" "health_http"', api_gateway)
        self.assertNotIn("/health/", api_gateway)
        self.assertNotIn('"health/*"', self.content)


if __name__ == "__main__":
    unittest.main()
