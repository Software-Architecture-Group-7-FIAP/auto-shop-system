#!/usr/bin/env bash
# Apply issue #91 branch protection on main and develop.
# Default required checks match .github/workflows/ci.yml in auto-shop-system (#89).
set -euo pipefail

repo="${1:-Software-Architecture-Group-7-FIAP/auto-shop-system}"
default_checks="test-and-security,gateway,manifests,terraform-k8s,terraform-aws,cluster-smoke,frontend"
checks_csv="${2:-$default_checks}"

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required to build the protection payload."
  exit 1
fi

contexts_json="$(
  tr ',' '\n' <<<"${checks_csv}" | sed '/^[[:space:]]*$/d' | jq -R . | jq -s .
)"

payload="$(
  jq -n \
    --argjson contexts "${contexts_json}" \
    '{
      required_status_checks: {strict: true, contexts: $contexts},
      enforce_admins: false,
      required_pull_request_reviews: {
        required_approving_review_count: 1,
        dismiss_stale_reviews: false,
        require_code_owner_reviews: false,
        require_last_push_approval: true
      },
      restrictions: null,
      allow_force_pushes: false,
      allow_deletions: false,
      block_creations: false,
      required_conversation_resolution: false,
      lock_branch: false,
      allow_fork_syncing: false
    }'
)"

echo "Repository: ${repo}"
echo "Required checks: ${checks_csv}"

for branch in develop main; do
  echo "Updating protection for ${repo}@${branch}"
  gh api --method PUT "repos/${repo}/branches/${branch}/protection" --input - <<<"${payload}" >/dev/null
done

echo "Enabling delete branch on merge for ${repo}"
gh api --method PATCH "repos/${repo}" --input - <<<'{"delete_branch_on_merge": true}' >/dev/null

echo "Branch protection applied for main and develop."
