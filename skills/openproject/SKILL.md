---
name: openproject
description: |
  OpenProject work package management via API v3. Use this skill when:
  - User provides ANY URL containing "openproject" (trigger immediately)
  - User mentions work packages, tasks, issues, or projects in OpenProject context
  - Viewing, creating, updating, or listing work packages
  - Interacting with OpenProject project management system
  Handles work package CRUD operations with proper HAL+JSON format and optimistic locking.
---

# OpenProject API

## Step 1: Determine Base URL

**If user provided an OpenProject URL** like `https://openproject.example.com/work_packages/123`:
Parse the base URL directly from it. Use it as a literal value in all subsequent commands.

**Otherwise**, read from environment (with sanitization):

```bash
printf '%s' "$OPENPROJECT_URL" | tr -d '\r\n '
```

If empty, try sourcing shell configs:

```bash
for f in ~/.zshenv ~/.zshrc ~/.bashrc ~/.profile; do [ -f "$f" ] && source "$f" 2>/dev/null; done && printf '%s' "$OPENPROJECT_URL" | tr -d '\r\n '
```

If still empty, tell user to set `OPENPROJECT_URL`.

## Step 2: Get API Key

IMPORTANT: Environment variables in Claude Code may contain invisible characters (`\r`, `\n`) that silently break curl. Always sanitize.

```bash
printf '%s' "$OPENPROJECT_API_KEY" | tr -d '\r\n '
```

If empty, try sourcing shell configs:

```bash
for f in ~/.zshenv ~/.zshrc ~/.bashrc ~/.profile; do [ -f "$f" ] && source "$f" 2>/dev/null; done && printf '%s' "$OPENPROJECT_API_KEY" | tr -d '\r\n '
```

If still empty, tell user to set `OPENPROJECT_API_KEY` (from My Account → Access tokens).

## Step 3: Make API Calls

> **CRITICAL: Never use `${OPENPROJECT_URL}` or `${OPENPROJECT_API_KEY}` shell variable references directly in curl commands.** They cause intermittent failures due to invisible characters in env vars.

Instead, always:
- Use the **literal base URL** obtained in Step 1 — substitute it directly into the curl command
- For the API key, use **inline sanitization**: `$(printf '%s' "$OPENPROJECT_API_KEY" | tr -d '\r\n ')`

In the examples below, replace `BASE_URL` with the actual literal URL from Step 1.

### Get Work Package

```bash
curl -s -u "apikey:$(printf '%s' "$OPENPROJECT_API_KEY" | tr -d '\r\n ')" \
  'BASE_URL/api/v3/work_packages/{id}'
```

Key fields: `subject`, `description.raw`, `lockVersion` (required for updates), `_links.status/assignee/project`

### Find Project by Name

```bash
curl -s -u "apikey:$(printf '%s' "$OPENPROJECT_API_KEY" | tr -d '\r\n ')" \
  'BASE_URL/api/v3/projects?filters=[{"name_and_identifier":{"operator":"~","values":["PROJECT_NAME"]}}]'
```

Project ID in `_embedded.elements[0].id`

### List Work Packages

```bash
curl -s -u "apikey:$(printf '%s' "$OPENPROJECT_API_KEY" | tr -d '\r\n ')" \
  'BASE_URL/api/v3/projects/{project_id}/work_packages'
```

Filter open: `?filters=[{"status":{"operator":"o","values":[]}}]`

### Create Work Package

```bash
curl -s -X POST -u "apikey:$(printf '%s' "$OPENPROJECT_API_KEY" | tr -d '\r\n ')" \
  -H "Content-Type: application/json" \
  'BASE_URL/api/v3/projects/{project_id}/work_packages' \
  -d '{"subject": "...", "description": {"raw": "..."}, "_links": {"type": {"href": "/api/v3/types/{type_id}"}}}'
```

### Update Work Package

**Must include current `lockVersion` from GET response:**

```bash
curl -s -X PATCH -u "apikey:$(printf '%s' "$OPENPROJECT_API_KEY" | tr -d '\r\n ')" \
  -H "Content-Type: application/json" \
  'BASE_URL/api/v3/work_packages/{id}' \
  -d '{"lockVersion": {N}, "subject": "...", "description": {"raw": "..."}}'
```

## Common Fields

| Field | Type | Notes |
|-------|------|-------|
| `subject` | string | Title |
| `description.raw` | string | Plain text |
| `lockVersion` | int | Required for PATCH |
| `startDate` | string | YYYY-MM-DD |
| `dueDate` | string | YYYY-MM-DD |
| `estimatedTime` | string | ISO 8601 (PT2H) |
| `percentageDone` | int | 0-100 |

## Error Handling

- **409 Conflict**: `lockVersion` outdated - refetch and retry
- **403 Forbidden**: Check API key permissions
- **422 Unprocessable**: Invalid data - check error message

## Tips

- Always GET before PATCH to obtain current `lockVersion`
- Use `notify=false` query param to suppress email notifications
- API uses HAL+JSON: related resources in `_links` and `_embedded`
