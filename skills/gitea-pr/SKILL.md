---
name: gitea-pr
description: |
  Gitea pull request management via REST API. Use this skill when:
  - User provides ANY URL containing "gitea" (trigger immediately before responding)
  - User mentions "Gitea" with PRs, code review, or repositories
  - Creating, reviewing, commenting on, or merging pull requests on Gitea
  - User says "create a PR", "submit for review" when working with a Gitea remote
  - User asks about CI status, check results, failed checks, or build artifacts on a PR
  Handles complete PR lifecycle: creation, review, comments, approvals, merging, and CI check inspection.
---

# Gitea Pull Requests

## Step 1: Parse URL and Identify Target

**If user provided a Gitea URL** like `https://gitea.example.com/owner/repo/pulls/123`:
Parse directly — extract base URL, owner, repo, and PR number from the URL structure. Use these as literal values in all subsequent commands. Skip to Step 2.

**If working from a git repository** (no URL provided):

```bash
git remote get-url origin
```

Parse the remote URL to extract base URL, owner, and repo:
- HTTPS: `https://gitea.example.com/owner/repo.git` → base=`https://gitea.example.com`, owner=`owner`, repo=`repo`
- SSH: `git@gitea.example.com:owner/repo.git` → base=`https://gitea.example.com`, owner=`owner`, repo=`repo`

Store these as literal strings for use in curl commands.

## Step 2: Get API Token

**Always source shell configs first** — ctx_execute and similar sandboxes run in a clean environment where `$GITEA_TOKEN` is not inherited. Sourcing upfront avoids silent empty-token failures:

```bash
for f in ~/.zshenv ~/.zshrc ~/.bashrc ~/.profile; do [ -f "$f" ] && source "$f" 2>/dev/null; done
TOKEN=$(printf '%s' "$GITEA_TOKEN" | tr -d '\r\n ')
echo "Token length: ${#TOKEN}"
```

If token is still empty, tell the user to set `GITEA_TOKEN` (Gitea → Settings → Applications, `repo` scope).

Use `$TOKEN` (already sanitized) in all subsequent curl commands — no need to re-sanitize inline.

## Step 3: Make API Calls

> **CRITICAL: Never use `${GITEA_URL}` or `${GITEA_TOKEN}` shell variable references directly in curl commands.** They cause intermittent "No host part in URL" failures due to invisible characters in env vars.

Instead, always:
- Use the **literal base URL** obtained in Step 1 (from user URL or git remote) — substitute it directly into the curl command
- Use `$TOKEN` — the sanitized variable set in Step 2 (already has `\r\n` stripped)

In the examples below, replace `BASE_URL`, `OWNER`, `REPO`, and `PR_NUMBER` with the actual literal values from Step 1.

### Get PR Details

```bash
curl -s 'BASE_URL/api/v1/repos/OWNER/REPO/pulls/PR_NUMBER' \
  -H "Authorization: token $TOKEN"
```

### Get Diff

```bash
curl -s 'BASE_URL/api/v1/repos/OWNER/REPO/pulls/PR_NUMBER.diff' \
  -H "Authorization: token $TOKEN"
```

### List Changed Files

```bash
curl -s 'BASE_URL/api/v1/repos/OWNER/REPO/pulls/PR_NUMBER/files' \
  -H "Authorization: token $TOKEN"
```

### Create PR

```bash
curl -s -X POST 'BASE_URL/api/v1/repos/OWNER/REPO/pulls' \
  -H "Authorization: token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "...", "body": "...", "head": "feature-branch", "base": "main"}'
```

### Add Comment

```bash
curl -s -X POST 'BASE_URL/api/v1/repos/OWNER/REPO/issues/PR_NUMBER/comments' \
  -H "Authorization: token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"body": "..."}'
```

### Submit Review

```bash
curl -s -X POST 'BASE_URL/api/v1/repos/OWNER/REPO/pulls/PR_NUMBER/reviews' \
  -H "Authorization: token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"body": "...", "event": "APPROVED"}'
```

Event values: `APPROVED`, `REQUEST_CHANGES`, `COMMENT`

### Merge PR

```bash
curl -s -X POST 'BASE_URL/api/v1/repos/OWNER/REPO/pulls/PR_NUMBER/merge' \
  -H "Authorization: token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"do": "merge"}'
```

Merge strategies: `merge`, `rebase`, `squash`

### Get CI Check Results

First get the PR head SHA, then fetch statuses and Actions runs in parallel.

**Get head SHA from PR:**
```bash
curl -s 'BASE_URL/api/v1/repos/OWNER/REPO/pulls/PR_NUMBER' \
  -H "Authorization: token $TOKEN" \
  | python3 -c "import sys,json; pr=json.load(sys.stdin); print(pr['head']['sha'])"
```

**Get combined commit status (traditional CI):**
```bash
curl -s 'BASE_URL/api/v1/repos/OWNER/REPO/commits/HEAD_SHA/status' \
  -H "Authorization: token $TOKEN"
```

Returns: `state` (pending/success/error/failure/warning), `statuses[]` with `context`, `description`, `target_url`, `state`.

**List individual commit statuses:**
```bash
curl -s 'BASE_URL/api/v1/repos/OWNER/REPO/commits/HEAD_SHA/statuses' \
  -H "Authorization: token $TOKEN"
```

**Get Gitea Actions workflow runs for this specific commit:**
```bash
curl -s 'BASE_URL/api/v1/repos/OWNER/REPO/actions/runs?head_sha=HEAD_SHA' \
  -H "Authorization: token $TOKEN"
```

Using `head_sha` scopes results to this PR's commit — `?status=failure` alone would return failures from other branches too.

**Get jobs for a specific run (includes step-level logs):**
```bash
curl -s 'BASE_URL/api/v1/repos/OWNER/REPO/actions/runs/RUN_ID/jobs' \
  -H "Authorization: token $TOKEN"
```

**List artifacts for a run:**
```bash
curl -s 'BASE_URL/api/v1/repos/OWNER/REPO/actions/runs/RUN_ID/artifacts' \
  -H "Authorization: token $TOKEN"
```

**Download an artifact** (get download URL from artifact list, then):
```bash
curl -sL 'ARTIFACT_DOWNLOAD_URL' \
  -H "Authorization: token $TOKEN" \
  -o artifact.zip
```

**Efficient all-checks summary** — run these in parallel (use `&` + `wait`):
```bash
curl -s 'BASE_URL/api/v1/repos/OWNER/REPO/commits/SHA/status' -H "Authorization: token $TOKEN" > /tmp/pr_status.json &
curl -s 'BASE_URL/api/v1/repos/OWNER/REPO/actions/runs?head_sha=SHA' -H "Authorization: token $TOKEN" > /tmp/pr_runs.json &
wait
python3 -c "
import json
status = json.load(open('/tmp/pr_status.json'))
runs = json.load(open('/tmp/pr_runs.json'))
print('Combined status:', status.get('state'))
for s in status.get('statuses', []):
    print(f\"  {s['state']:10} {s['context']}: {s['description']}\")
print()
for run in runs.get('workflow_runs', []):
    print(f\"  {run['status']:10} {run['name']} #{run['run_number']} ({run['conclusion']})\")
"
```

## Quick Reference

| Operation | Endpoint | Method |
|-----------|----------|--------|
| Create PR | `/repos/{owner}/{repo}/pulls` | POST |
| Get PR | `/repos/{owner}/{repo}/pulls/{index}` | GET |
| Get diff | `/repos/{owner}/{repo}/pulls/{index}.diff` | GET |
| List files | `/repos/{owner}/{repo}/pulls/{index}/files` | GET |
| Add comment | `/repos/{owner}/{repo}/issues/{index}/comments` | POST |
| Submit review | `/repos/{owner}/{repo}/pulls/{index}/reviews` | POST |
| Merge PR | `/repos/{owner}/{repo}/pulls/{index}/merge` | POST |
| Combined status | `/repos/{owner}/{repo}/commits/{sha}/status` | GET |
| List statuses | `/repos/{owner}/{repo}/commits/{sha}/statuses` | GET |
| Actions runs | `/repos/{owner}/{repo}/actions/runs` | GET |
| Run jobs | `/repos/{owner}/{repo}/actions/runs/{run_id}/jobs` | GET |
| Run artifacts | `/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts` | GET |

For complete API docs including request/response schemas, see [references/gitea-api.md](references/gitea-api.md).
