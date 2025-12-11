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

## Prerequisites (Always Check First)

```bash
# Verify environment variables
echo "GITEA_URL: ${GITEA_URL:-NOT SET}" && echo "GITEA_TOKEN: ${GITEA_TOKEN:-NOT SET}"
```

If NOT SET, try sourcing shell configs:

```bash
for f in ~/.zshenv ~/.zshrc ~/.bashrc; do [ -f "$f" ] && source "$f"; done
```

If still missing, tell user to set `GITEA_URL` and `GITEA_TOKEN` (token from Settings → Applications with `repo` scope).

## Get Owner/Repo

```bash
git remote get-url origin  # Extract owner/repo from URL
```

## Core Operations

### Create PR

```bash
curl -X POST "${GITEA_URL}/api/v1/repos/${OWNER}/${REPO}/pulls" \
  -H "Authorization: token ${GITEA_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"title": "...", "body": "...", "head": "feature-branch", "base": "main"}'
```

### Get PR Details

```bash
curl "${GITEA_URL}/api/v1/repos/${OWNER}/${REPO}/pulls/${PR_NUMBER}" \
  -H "Authorization: token ${GITEA_TOKEN}"
```

### Get Diff

```bash
curl "${GITEA_URL}/api/v1/repos/${OWNER}/${REPO}/pulls/${PR_NUMBER}.diff" \
  -H "Authorization: token ${GITEA_TOKEN}"
```

### Add Comment

```bash
curl -X POST "${GITEA_URL}/api/v1/repos/${OWNER}/${REPO}/issues/${PR_NUMBER}/comments" \
  -H "Authorization: token ${GITEA_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"body": "..."}'
```

### Submit Review

```bash
curl -X POST "${GITEA_URL}/api/v1/repos/${OWNER}/${REPO}/pulls/${PR_NUMBER}/reviews" \
  -H "Authorization: token ${GITEA_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"body": "...", "event": "APPROVED"}'  # or REQUEST_CHANGES, COMMENT
```

### Merge PR

```bash
curl -X POST "${GITEA_URL}/api/v1/repos/${OWNER}/${REPO}/pulls/${PR_NUMBER}/merge" \
  -H "Authorization: token ${GITEA_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"do": "merge"}'  # or rebase, squash
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

For complete API docs including request/response schemas, see [references/gitea-api.md](references/gitea-api.md).
