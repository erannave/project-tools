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

## Prerequisites (Always Check First)

```bash
echo "OPENPROJECT_URL: ${OPENPROJECT_URL:-NOT SET}" && echo "OPENPROJECT_API_KEY: ${OPENPROJECT_API_KEY:-NOT SET}"
```

If NOT SET, try sourcing shell configs:

```bash
for f in ~/.zshenv ~/.zshrc ~/.bashrc; do [ -f "$f" ] && source "$f"; done
```

If still missing, tell user to set `OPENPROJECT_URL` and `OPENPROJECT_API_KEY` (from My Account → Access tokens).

## Core Operations

### Get Work Package

```bash
curl -u "apikey:$OPENPROJECT_API_KEY" "$OPENPROJECT_URL/api/v3/work_packages/{id}"
```

Key fields: `subject`, `description.raw`, `lockVersion` (required for updates), `_links.status/assignee/project`

### Find Project by Name

```bash
curl -u "apikey:$OPENPROJECT_API_KEY" \
  "$OPENPROJECT_URL/api/v3/projects?filters=[{\"name_and_identifier\":{\"operator\":\"~\",\"values\":[\"PROJECT_NAME\"]}}]"
```

Project ID in `_embedded.elements[0].id`

### List Work Packages

```bash
curl -u "apikey:$OPENPROJECT_API_KEY" "$OPENPROJECT_URL/api/v3/projects/{project_id}/work_packages"
```

Filter open: `?filters=[{"status":{"operator":"o","values":[]}}]`

### Create Work Package

```bash
curl -X POST -u "apikey:$OPENPROJECT_API_KEY" \
  -H "Content-Type: application/json" \
  "$OPENPROJECT_URL/api/v3/projects/{project_id}/work_packages" \
  -d '{"subject": "...", "description": {"raw": "..."}, "_links": {"type": {"href": "/api/v3/types/{type_id}"}}}'
```

### Update Work Package

**Must include current `lockVersion` from GET response:**

```bash
curl -X PATCH -u "apikey:$OPENPROJECT_API_KEY" \
  -H "Content-Type: application/json" \
  "$OPENPROJECT_URL/api/v3/work_packages/{id}" \
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
