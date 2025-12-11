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

## Response Codes

| Code | Meaning |
|------|---------|
| 200/201/204 | Success |
| 401 | Invalid token |
| 403 | Insufficient permissions |
| 404 | Not found |
| 409 | Conflict (e.g., cannot merge) |
| 422 | Validation error |
