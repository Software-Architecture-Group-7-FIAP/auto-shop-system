#!/usr/bin/env bash
# Apply issue #91 branch protection on main and develop.
# Required checks are the jobs shared by security.yml and the upcoming ci.yml (#89).
set -euo pipefail

repo="${1:-Software-Architecture-Group-7-FIAP/auto-shop-system}"

payload="$(cat <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "test-and-security",
      "manifests",
      "cluster-smoke",
      "frontend"
    ]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": false,
    "require_code_owner_reviews": false,
    "require_last_push_approval": false
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": false,
  "lock_branch": false,
  "allow_fork_syncing": false
}
EOF
)"

for branch in develop main; do
  echo "Updating protection for ${repo}@${branch}"
  gh api --method PUT "repos/${repo}/branches/${branch}/protection" --input - <<<"${payload}" >/dev/null
done

echo "Enabling delete branch on merge for ${repo}"
gh api --method PATCH "repos/${repo}" --input - <<<'{"delete_branch_on_merge": true}' >/dev/null

echo "Branch protection applied for main and develop."
