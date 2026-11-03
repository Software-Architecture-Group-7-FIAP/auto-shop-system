# HML CodeBuild runner webhook

The CodeBuild project `auto-shop-hml-private-runner` is configured in AWS, but this repository has no Terraform or CloudFormation source for its webhook. The project currently listens for `WORKFLOW_JOB_QUEUED` and filters `WORKFLOW_NAME` with `^HML deploy [0-9a-f]{40}$`.

PR #190 routes the Kubernetes deploy jobs in `CD Staging` and `CD Production` to that runner. Those workflows name runs `lifecycle:<hml-or-prd-session>:app-deploy:<dispatch-id>`. The lifecycle coordinator also relies on that title when it verifies the dispatched deployment, so keep the workflow run names unchanged.

The reviewed webhook pattern is anchored to the existing minimal HML run name and the two ledger-validated deployment forms:

```text
^(HML deploy [0-9a-f]{40}|lifecycle:(hml|prd)-[0-9]{4}-[0-9]{2}-[0-9]{2}:app-deploy:([0-9a-f]{32}|[1-9][0-9]{0,19}))$
```

The date session ID and 32-character dispatch ID formats match `.github/scripts/lifecycle_session_ledger.py`. The numeric alternative is GitHub's run ID when no coordinator dispatch ID is supplied. Push run names and other lifecycle jobs do not match. CodeBuild evaluates webhook filter patterns as RE2 regular expressions; see the [CodeBuild GitHub webhook filter documentation](https://docs.aws.amazon.com/codebuild/latest/userguide/github-webhook.html).

Use `.github/scripts/reconcile_codebuild_runner_webhook.py` to inspect and reconcile the AWS-owned configuration. It checks the current AWS account and project, requires a GitHub source (and the exact repository when the source location is repository-bound), requires the exact reviewed legacy or target pattern, changes only the `WORKFLOW_NAME` filter in the `WORKFLOW_JOB_QUEUED` group, and preserves all other groups. It is read-only unless `--apply` is supplied; rerunning after a successful update is a no-op. CodeBuild runner projects may use the documented `CODEBUILD_DEFAULT_WEBHOOK_SOURCE_LOCATION` source sentinel, which the script accepts without changing it.

Set `AWS_PROFILE` and `EXPECTED_AWS_ACCOUNT_ID` from the approved local AWS configuration. The profile needs `sts:GetCallerIdentity`, `codebuild:BatchGetProjects`, and `codebuild:UpdateWebhook`. First review the proposed change:

```bash
python3 .github/scripts/reconcile_codebuild_runner_webhook.py \
  --profile "${AWS_PROFILE}" \
  --region us-east-1 \
  --expected-account-id "${EXPECTED_AWS_ACCOUNT_ID}"
```

After reviewing that read-only result, apply it with the same profile, region, and verified account ID, plus `--apply`:

```bash
python3 .github/scripts/reconcile_codebuild_runner_webhook.py \
  --profile "${AWS_PROFILE}" \
  --region us-east-1 \
  --expected-account-id "${EXPECTED_AWS_ACCOUNT_ID}" \
  --apply
```

This repo change does not update AWS. Do not replace the existing filter groups manually; the script preserves unrelated webhook conditions.
