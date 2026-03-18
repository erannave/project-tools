# Gitea API Reference for Pull Requests

## Authentication

All requests require: `Authorization: token <GITEA_TOKEN>`

## Pull Request Endpoints

### Create Pull Request

```
POST /api/v1/repos/{owner}/{repo}/pulls
```

**Request Body:**

```json
{
  "title": "string (required)",
  "body": "string (optional, markdown)",
  "head": "string (required, source branch)",
  "base": "string (required, target branch)",
  "assignee": "string (optional)",
  "assignees": ["string"],
  "labels": [1, 2],
  "milestone": 1,
  "due_date": "2024-01-01T00:00:00Z"
}
```

### Get Pull Request

```
GET /api/v1/repos/{owner}/{repo}/pulls/{index}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `number` | int | PR number |
| `title` | string | PR title |
| `body` | string | Description |
| `state` | string | "open", "closed" |
| `html_url` | string | Web URL |
| `mergeable` | bool | Can be merged |
| `merged` | bool | Already merged |
| `head` | object | Source branch |
| `base` | object | Target branch |
| `user` | object | PR author |

### List Pull Requests

```
GET /api/v1/repos/{owner}/{repo}/pulls
```

**Query Parameters:** `state` (open/closed/all), `sort`, `milestone`, `labels`, `page`, `limit`

### Get PR Diff/Patch

```
GET /api/v1/repos/{owner}/{repo}/pulls/{index}.diff
GET /api/v1/repos/{owner}/{repo}/pulls/{index}.patch
```

### List PR Files

```
GET /api/v1/repos/{owner}/{repo}/pulls/{index}/files
```

Response includes: `filename`, `status` (added/modified/removed/renamed), `additions`, `deletions`

### Update Pull Request

```
PATCH /api/v1/repos/{owner}/{repo}/pulls/{index}
```

Body: `title`, `body`, `assignee`, `assignees`, `labels`, `milestone`, `state`, `base`

### Merge Pull Request

```
POST /api/v1/repos/{owner}/{repo}/pulls/{index}/merge
```

**Request Body:**

```json
{
  "do": "merge" | "rebase" | "rebase-merge" | "squash" | "manually-merged",
  "merge_message_field": "string",
  "merge_title_field": "string",
  "delete_branch_after_merge": true,
  "force_merge": false,
  "head_commit_id": "string"
}
```

### Check Merge Status

```
GET /api/v1/repos/{owner}/{repo}/pulls/{index}/merge
```

204 if merged, 404 if not.

## Review Endpoints

### Create Review

```
POST /api/v1/repos/{owner}/{repo}/pulls/{index}/reviews
```

**Request Body:**

```json
{
  "body": "string",
  "event": "APPROVED" | "REQUEST_CHANGES" | "COMMENT",
  "comments": [
    {
      "path": "file path",
      "new_position": 42,
      "body": "comment"
    }
  ]
}
```

### List/Get/Delete Reviews

```
GET /api/v1/repos/{owner}/{repo}/pulls/{index}/reviews
GET /api/v1/repos/{owner}/{repo}/pulls/{index}/reviews/{id}
DELETE /api/v1/repos/{owner}/{repo}/pulls/{index}/reviews/{id}
```

## Comment Endpoints

PRs use issues API for general comments:

```
GET /api/v1/repos/{owner}/{repo}/issues/{index}/comments
POST /api/v1/repos/{owner}/{repo}/issues/{index}/comments  {"body": "..."}
PATCH /api/v1/repos/{owner}/{repo}/issues/comments/{id}
DELETE /api/v1/repos/{owner}/{repo}/issues/comments/{id}
```

## Labels & Assignees

```
POST /api/v1/repos/{owner}/{repo}/issues/{index}/labels  {"labels": [1,2,3]}
DELETE /api/v1/repos/{owner}/{repo}/issues/{index}/labels/{id}
POST /api/v1/repos/{owner}/{repo}/issues/{index}/assignees  {"assignees": [...]}
DELETE /api/v1/repos/{owner}/{repo}/issues/{index}/assignees
```

## Commit Status Endpoints

### Get Combined Status

```
GET /api/v1/repos/{owner}/{repo}/commits/{sha}/status
```

Returns the combined state (`pending`, `success`, `error`, `failure`, `warning`) and all individual statuses.

**Response:**
```json
{
  "state": "failure",
  "statuses": [
    {
      "id": 1,
      "state": "failure",
      "context": "continuous-integration/jenkins",
      "description": "Build failed",
      "target_url": "https://ci.example.com/build/42",
      "created": "...",
      "updated": "..."
    }
  ],
  "sha": "abc123",
  "total_count": 2,
  "commit": { ... },
  "url": "..."
}
```

### List Commit Statuses

```
GET /api/v1/repos/{owner}/{repo}/commits/{sha}/statuses
```

Query params: `sort` (oldest/recentupdate), `state`, `page`, `limit`

### Create Commit Status

```
POST /api/v1/repos/{owner}/{repo}/statuses/{sha}
```

Body: `state`, `target_url`, `description`, `context`

## Gitea Actions Endpoints

### List Workflow Runs

```
GET /api/v1/repos/{owner}/{repo}/actions/runs
```

Query params: `actor`, `branch`, `event`, `status` (queued/in_progress/waiting/success/failure/cancelled/skipped), `head_sha`, `page`, `limit`

**Response fields per run:** `id`, `name`, `run_number`, `status`, `conclusion`, `head_sha`, `head_branch`, `workflow_id`, `created`, `updated`

### Get Workflow Run

```
GET /api/v1/repos/{owner}/{repo}/actions/runs/{run_id}
```

### List Jobs for Run

```
GET /api/v1/repos/{owner}/{repo}/actions/runs/{run_id}/jobs
```

**Response fields per job:** `id`, `name`, `status`, `conclusion`, `started_at`, `completed_at`, `steps[]` (name, status, conclusion, number)

### Get Job Logs

```
GET /api/v1/repos/{owner}/{repo}/actions/jobs/{job_id}/logs
```

Returns raw log text.

### List Artifacts for Run

```
GET /api/v1/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts
```

**Response fields per artifact:** `id`, `name`, `size_in_bytes`, `expired`, `created_at`, `expires_at`, `url`

### Download Artifact

```
GET /api/v1/repos/{owner}/{repo}/actions/artifacts/{artifact_id}/zip
```

Returns a redirect to the zip download. Use `curl -sL` to follow redirects.

### List All Repo Artifacts

```
GET /api/v1/repos/{owner}/{repo}/actions/artifacts
```

Query params: `name`, `page`, `limit`

### Delete Artifact

```
DELETE /api/v1/repos/{owner}/{repo}/actions/artifacts/{artifact_id}
```

## Response Codes

| Code | Meaning |
|------|---------|
| 200/201/204 | Success |
| 401 | Invalid token |
| 403 | Insufficient permissions |
| 404 | Not found |
| 409 | Conflict (e.g., cannot merge) |
| 422 | Validation error |
