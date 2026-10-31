# Issue #04 - HML Runtime Test

**Date:** 2026-10-31  
**Objective:** Validate digest-based release workflow with OIDC authentication

## Test Execution

This commit tests:
1. OIDC token exchange (GitHub Actions → AWS)
2. Digest-pinned image validation (not tag-based)
3. Deploy with AWS_DEPLOY_ROLE_ARN (hml environment)
4. Rollback to previous digest

## Expected Workflow

1. GitHub Actions requests JWT from OIDC provider
2. JWT exchanged for temporary AWS credentials
3. Assume role: `gh-deploy-auto-shop-system-hml`
4. Deploy script validates image digest
5. Image deployed by digest reference
6. Rollback available via digest reference

## Verification

- [ ] Workflow runs successfully
- [ ] GitHub Actions logs show OIDC token exchange
- [ ] AWS CloudTrail shows AssumeRoleWithWebIdentity
- [ ] Deploy uses digest, not tag
- [ ] Rollback command works

---

**Test Status:** Pending workflow execution
