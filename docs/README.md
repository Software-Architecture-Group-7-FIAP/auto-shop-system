# Documentation Index

Auto Shop System documentation organized by topic.

## Infrastructure & Deployment

- **INFRASTRUCTURE.md** — Complete infrastructure guide (Issues #01-#05)
  - OIDC security foundation
  - AWS bootstrap & state management
  - Private GitHub runners & lifecycle automation
  - Digest-based deployment validation
  - Kubernetes network policies & HTTPS ingress
  
- **ISSUES-01-05-COMPLETION-STATUS.md** — Issue completion checklist & validation criteria

- **architecture.md** — System design and architecture overview

- **deployment.md** — CI/CD pipeline and deployment procedures

## Development

- **development_guidelines.md** — Code style, testing, and development standards

- **pr_review_guidelines.md** — Pull request review criteria and process

## Security & Compliance

- **hardening-review.md** — Security audit findings and hardening tasks

- **relatorio-vulnerabilidades-sast.md** — SAST vulnerability report

## Historical & Phase-Specific

- **prd-revisao-professor-fase-2.md** — Phase 2 review notes

- **archived/** — Temporary documentation from issues (reference only)
  - INFRASTRUCTURE-DEPLOYMENT-COMPLETE.md
  - ISSUE-04-HML-RUNTIME-TEST.md
  - ISSUE-05-RUNTIME-DEPLOYMENT.md

---

## Quick Start

1. **New to the project?** Start with `architecture.md`
2. **Deploying infrastructure?** See `INFRASTRUCTURE.md`
3. **Making code changes?** Read `development_guidelines.md`
4. **Submitting PR?** Check `pr_review_guidelines.md`
5. **Security concerns?** Review `hardening-review.md`

---

## Status Dashboard

| Component | Status | Reference |
|-----------|--------|-----------|
| OIDC Security | ✅ Deployed | INFRASTRUCTURE.md |
| AWS Bootstrap | ✅ Deployed | INFRASTRUCTURE.md |
| GitHub Runners | ✅ Deployed | INFRASTRUCTURE.md |
| Digest Deployment | ✅ Validated | INFRASTRUCTURE.md |
| K8s Infrastructure | ✅ Deployed | INFRASTRUCTURE.md |
| Network Policies | ✅ Strict Mode | INFRASTRUCTURE.md |
| HTTPS Ingress | ✅ Configured | INFRASTRUCTURE.md |

---

**Last Updated:** 2026-10-31
