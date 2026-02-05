---
name: gitea-pr
description: |
  Gitea pull request management via REST API. Use this skill when:
  - User provides ANY URL containing "gitea" (trigger immediately before responding)
  - User mentions "Gitea" with PRs, code review, or repositories
  - Creating, reviewing, commenting on, or merging pull requests on Gitea
  - User says "create a PR", "submit for review" when working with a Gitea remote
  Handles complete PR lifecycle: creation, review, comments, approvals, and merging.
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

IMPORTANT: Environment variables in Claude Code may contain invisible characters (`\r`, `\n`) that silently break curl. Always sanitize.

```bash
printf '%s' "$GITEA_TOKEN" | tr -d '\r\n '
```

If output is empty, try sourcing shell configs:

```bash
for f in ~/.zshenv ~/.zshrc ~/.bashrc ~/.profile; do [ -f "$f" ] && source "$f" 2>/dev/null; done && printf '%s' "$GITEA_TOKEN" | tr -d '\r\n '
```

If still empty, tell user to set `GITEA_TOKEN` (Settings → Applications, `repo` scope).

## Step 3: Make API Calls

> **CRITICAL: Never use `${GITEA_URL}` or `${GITEA_TOKEN}` shell variable references directly in curl commands.** They cause intermittent "No host part in URL" failures due to invisible characters in env vars.

Instead, always:
- Use the **literal base URL** obtained in Step 1 (from user URL or git remote) — substitute it directly into the curl command
- For the token, use **inline sanitization**: `$(printf '%s' "$GITEA_TOKEN" | tr -d '\r\n ')`

In the examples below, replace `BASE_URL`, `OWNER`, `REPO`, and `PR_NUMBER` with the actual literal values from Step 1.

### Get PR Details

```bash
curl -s 'BASE_URL/api/v1/repos/OWNER/REPO/pulls/PR_NUMBER' \
  -H "Authorization: token $(printf '%s' "$GITEA_TOKEN" | tr -d '\r\n ')"
```

### Get Diff

```bash
curl -s 'BASE_URL/api/v1/repos/OWNER/REPO/pulls/PR_NUMBER.diff' \
  -H "Authorization: token $(printf '%s' "$GITEA_TOKEN" | tr -d '\r\n ')"
```

### List Changed Files

```bash
curl -s 'BASE_URL/api/v1/repos/OWNER/REPO/pulls/PR_NUMBER/files' \
  -H "Authorization: token $(printf '%s' "$GITEA_TOKEN" | tr -d '\r\n ')"
```

### Create PR

```bash
curl -s -X POST 'BASE_URL/api/v1/repos/OWNER/REPO/pulls' \
  -H "Authorization: token $(printf '%s' "$GITEA_TOKEN" | tr -d '\r\n ')" \
  -H "Content-Type: application/json" \
  -d '{"title": "...", "body": "...", "head": "feature-branch", "base": "main"}'
```

### Add Comment

```bash
curl -s -X POST 'BASE_URL/api/v1/repos/OWNER/REPO/issues/PR_NUMBER/comments' \
  -H "Authorization: token $(printf '%s' "$GITEA_TOKEN" | tr -d '\r\n ')" \
  -H "Content-Type: application/json" \
  -d '{"body": "..."}'
```

### Submit Review

```bash
curl -s -X POST 'BASE_URL/api/v1/repos/OWNER/REPO/pulls/PR_NUMBER/reviews' \
  -H "Authorization: token $(printf '%s' "$GITEA_TOKEN" | tr -d '\r\n ')" \
  -H "Content-Type: application/json" \
  -d '{"body": "...", "event": "APPROVED"}'
```

Event values: `APPROVED`, `REQUEST_CHANGES`, `COMMENT`

### Merge PR

```bash
curl -s -X POST 'BASE_URL/api/v1/repos/OWNER/REPO/pulls/PR_NUMBER/merge' \
  -H "Authorization: token $(printf '%s' "$GITEA_TOKEN" | tr -d '\r\n ')" \
  -H "Content-Type: application/json" \
  -d '{"do": "merge"}'
```

Merge strategies: `merge`, `rebase`, `squash`

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

For complete API docs including request/response schemas, see [references/gitea-api.md](references/gitea-api.md).
