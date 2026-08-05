# Gitea API Reference for Pull Requests

Verified against Gitea **1.27.1** (`/swagger.v1.json`). All paths are relative to
`{base_url}/api/v1`.

## Authentication

Header: `Authorization: token <TOKEN>`

Token scopes are `<read|write>:<category>` on modern Gitea — **not** the old
GitHub-style `repo`. Categories: `activitypub`, `admin`, `issue`, `misc`,
`notification`, `organization`, `package`, `repository`, `user`. `all` grants
everything.

For PR work you want `write:repository`, `write:issue`, `read:organization`,
`read:user`. A missing scope produces `403` with the required scope named in the
message, e.g. `... required=[read:organization]` — read that list rather than
regenerating the token blindly.

`404 {"message":"not found"}` is the most common failure. It does **not** mean a
casing problem: owner and repo names are case-insensitive (`Batalyse/batalyse`,
`batalyse/dataanalysis`, and `batalyse/dataAnalysis` all resolve). See the 404
triage section in `../SKILL.md`.

## Pull Request Endpoints

### Create Pull Request

```
POST /repos/{owner}/{repo}/pulls
```

`CreatePullRequestOption` — the complete field list, verified from swagger:

```json
{
  "title": "string (required)",
  "body": "string (markdown)",
  "head": "string (required, source branch)",
  "base": "string (required, target branch)",
  "assignee": "string",
  "assignees": ["string"],
  "labels": [1, 2],
  "milestone": 1,
  "reviewers": ["username"],
  "team_reviewers": ["team"],
  "due_date": "2024-01-01T00:00:00Z",
  "allow_maintainer_edit": true
}
```

#### Drafts are a title convention, not a field

There is **no `draft` field** on create or edit — the list above is exhaustive,
and `EditPullRequestOption` has no `draft` either. `PullRequest.draft` exists in
*responses* only ("Whether the pull request is a draft") and is derived from the
title.

A PR is a draft iff its title starts with a configured WIP prefix — `WIP:` or
`[WIP]` by default. So:

- **Create a draft:** title it `WIP: <real title>`, or use `tea pr create --draft`,
  which prepends the prefix for you.
- **Mark it ready:** `PATCH .../pulls/{index}` with `title` set to the title minus
  the prefix. There is no "ready for review" endpoint.

Prefixes are server-configurable (`[repository.pull-request] WORK_IN_PROGRESS_PREFIXES`)
and are not exposed through the API. If `draft` comes back `false` on a PR you
titled `WIP:`, that instance uses different prefixes.

### Get Pull Request

```
GET /repos/{owner}/{repo}/pulls/{index}
```

| Field | Type | Description |
|-------|------|-------------|
| `number` | int | PR index (per-repo, not global) |
| `title` | string | PR title |
| `body` | string | Description |
| `state` | string | `open`, `closed` |
| `draft` | bool | Derived from the title prefix — read-only |
| `html_url` | string | Web URL |
| `mergeable` | bool | Can be merged |
| `merged` | bool | Already merged |
| `head` | object | Source branch — `head.sha` is what CI is keyed on |
| `base` | object | Target branch |
| `user` | object | PR author |

### List Pull Requests

```
GET /repos/{owner}/{repo}/pulls
```

Query: `state` (open/closed/all), `sort`, `milestone`, `labels`, `page`, `limit`.

Page with `page=1,2,3…` rather than pushing `limit` past the server cap — a large
`limit` is silently clamped, so a single oversized request looks complete while
quietly dropping the tail.

### Get PR Diff/Patch

```
GET /repos/{owner}/{repo}/pulls/{index}.diff
GET /repos/{owner}/{repo}/pulls/{index}.patch
```

### List PR Files

```
GET /repos/{owner}/{repo}/pulls/{index}/files
```

Response: `filename`, `status` (added/modified/removed/renamed), `additions`, `deletions`.

### List PR Commits

```
GET /repos/{owner}/{repo}/pulls/{index}/commits
```

Query: `page`, `limit`, `verification`, `files`. Use this instead of diffing
branches locally when you only need the commit list.

### Update Pull Request

```
PATCH /repos/{owner}/{repo}/pulls/{index}
```

`EditPullRequestOption`: `title`, `body`, `assignee`, `assignees`, `labels`,
`milestone`, `state`, `base`, `due_date`, `unset_due_date`,
`allow_maintainer_edit`, `content_version`. No `draft` (see above), and no `head`
— the source branch cannot be changed after creation.

### Merge Pull Request

```
POST /repos/{owner}/{repo}/pulls/{index}/merge
```

```json
{
  "do": "merge" | "rebase" | "rebase-merge" | "squash" | "fast-forward-only" | "manually-merged",
  "merge_message_field": "string",
  "merge_title_field": "string",
  "delete_branch_after_merge": true,
  "force_merge": false,
  "head_commit_id": "string",
  "merge_when_checks_succeed": false
}
```

`head_commit_id` guards against merging a stale head — pass the SHA you reviewed
and the merge fails rather than silently taking newer commits.

### Check Merge Status

```
GET /repos/{owner}/{repo}/pulls/{index}/merge
```

204 if merged, 404 if not.

### Requested Reviewers

```
POST   /repos/{owner}/{repo}/pulls/{index}/requested_reviewers  {"reviewers": ["user"], "team_reviewers": ["team"]}
DELETE /repos/{owner}/{repo}/pulls/{index}/requested_reviewers  {"reviewers": ["user"]}
```

## Review Endpoints

### Create Review

```
POST /repos/{owner}/{repo}/pulls/{index}/reviews
```

```json
{
  "body": "string",
  "event": "APPROVED" | "REQUEST_CHANGES" | "COMMENT" | "PENDING",
  "commit_id": "string",
  "comments": [
    {
      "path": "file path",
      "body": "comment",
      "new_position": 42,
      "old_position": 0
    }
  ]
}
```

`new_position` is the line number in the **new** file, `old_position` in the old
one. Give exactly one; a line comment on an unchanged line is rejected.

### List/Get/Delete Reviews

```
GET    /repos/{owner}/{repo}/pulls/{index}/reviews
GET    /repos/{owner}/{repo}/pulls/{index}/reviews/{id}
POST   /repos/{owner}/{repo}/pulls/{index}/reviews/{id}        # submit a PENDING review
DELETE /repos/{owner}/{repo}/pulls/{index}/reviews/{id}
```

### List Review Comments

```
GET /repos/{owner}/{repo}/pulls/{index}/reviews/{id}/comments
```

The per-line comments attached to one review. The review object itself carries
only the summary `body`, so this is the endpoint that actually returns the
feedback — list reviews first, then fetch comments per review id.

### Dismiss / Undismiss a Review

```
POST /repos/{owner}/{repo}/pulls/{index}/reviews/{id}/dismissals    {"message": "..."}
POST /repos/{owner}/{repo}/pulls/{index}/reviews/{id}/undismissals
```

## Comment Endpoints

PRs use the issues API for general (non-line) comments:

```
GET    /repos/{owner}/{repo}/issues/{index}/comments
POST   /repos/{owner}/{repo}/issues/{index}/comments  {"body": "..."}
PATCH  /repos/{owner}/{repo}/issues/comments/{id}     {"body": "..."}
DELETE /repos/{owner}/{repo}/issues/comments/{id}
```

### Issue/PR Timeline

```
GET /repos/{owner}/{repo}/issues/{index}/timeline
```

Query: `since`, `before`, `page`, `limit`. Comments *and* events (label changes,
review requests, force-pushes, closes) in one ordered stream — cheaper than
correlating several endpoints when reconstructing what happened to a PR.

### Attachments (how images get into a comment)

```
GET    /repos/{owner}/{repo}/issues/{index}/assets
POST   /repos/{owner}/{repo}/issues/{index}/assets?name=<filename>
PATCH  /repos/{owner}/{repo}/issues/{index}/assets/{attachment_id}
DELETE /repos/{owner}/{repo}/issues/{index}/assets/{attachment_id}
GET    /repos/{owner}/{repo}/issues/comments/{id}/assets
POST   /repos/{owner}/{repo}/issues/comments/{id}/assets
```

The POST is **`multipart/form-data`** with the file in the `attachment` field —
not JSON:

```bash
curl -s -X POST 'BASE/api/v1/repos/OWNER/REPO/issues/42/assets?name=screenshot.png' \
  -H "Authorization: token $TOKEN" \
  -F 'attachment=@/path/to/screenshot.png'
```

The response carries `browser_download_url`. Embed that in a comment body as
`![screenshot](<browser_download_url>)` — uploading alone does not make the image
appear in any comment.

## Labels

```
GET    /repos/{owner}/{repo}/labels                        # id ↔ name mapping for this repo
POST   /repos/{owner}/{repo}/labels                        {"name": "...", "color": "#rrggbb", "description": "..."}
GET    /repos/{owner}/{repo}/labels/{id}
PATCH  /repos/{owner}/{repo}/labels/{id}
DELETE /repos/{owner}/{repo}/labels/{id}

GET    /repos/{owner}/{repo}/issues/{index}/labels
POST   /repos/{owner}/{repo}/issues/{index}/labels         {"labels": [1,2,3]}   # add
PUT    /repos/{owner}/{repo}/issues/{index}/labels         {"labels": [1,2,3]}   # replace all
DELETE /repos/{owner}/{repo}/issues/{index}/labels         # clear all
DELETE /repos/{owner}/{repo}/issues/{index}/labels/{id}    # remove one
```

`labels` accepts label **ids**, so fetch `/labels` first to resolve names. (Recent
Gitea also accepts names as strings in the array, but ids always work.)

Note POST-adds versus PUT-replaces — using PUT when you meant POST silently drops
every other label on the PR.

## Assignees

```
POST   /repos/{owner}/{repo}/issues/{index}/assignees  {"assignees": ["user"]}
DELETE /repos/{owner}/{repo}/issues/{index}/assignees  {"assignees": ["user"]}
```

## Commit & Git Data Endpoints

### Get Combined Status

```
GET /repos/{owner}/{repo}/commits/{ref}/status
```

**The two-key trap.** The top-level object uses `state`; each entry in
`statuses[]` uses **`status`**. They are different schemas:

```
CombinedStatus : commit_url, repository, sha, state, statuses, total_count, url
CommitStatus   : context, created_at, creator, description, id, status,
                 target_url, updated_at, url
```

`s['state']` on an entry raises `KeyError`. Read `s['status']`.

```json
{
  "state": "failure",
  "sha": "abc123",
  "total_count": 5,
  "statuses": [
    {
      "id": 1,
      "status": "warning",
      "context": "ci/gate",
      "description": "gated-off: CI not run - add the CI/Run label",
      "target_url": "https://ci.example.com/build/42"
    }
  ]
}
```

Values: `pending`, `success`, `error`, `failure`, `warning`. The top-level `state`
is a roll-up and a single `warning` entry rolls the whole thing up to `failure` —
so a PR can report `failure` with no failing check. Report the entries, not just
the roll-up.

Combined status returns the latest entry per `context`, already deduped.

### List Commit Statuses

```
GET /repos/{owner}/{repo}/commits/{ref}/statuses
```

Query: `sort` (oldest/recentupdate/leastupdate/highestindex/lowestindex), `state`,
`page`, `limit`. Full history including superseded entries — use the combined
endpoint unless you specifically want the history.

### Create Commit Status

```
POST /repos/{owner}/{repo}/statuses/{sha}
```

Body: `state`, `target_url`, `description`, `context`. This is how a bot posts its
own gate result.

### Get Commit

```
GET /repos/{owner}/{repo}/git/commits/{sha}
GET /repos/{owner}/{repo}/git/commits/{sha}.diff
GET /repos/{owner}/{repo}/git/commits/{sha}.patch
```

Query on the base form: `stat`, `verification`, `files`. Set `stat=false&files=false`
when you only need the message and parents — the default response embeds the full
file list and is large.

### Get Tree

```
GET /repos/{owner}/{repo}/git/trees/{sha}
```

Query: `recursive` (bool), `page`, **`per_page`** (not `limit`). The response has a
`truncated` boolean — check it; a truncated tree that you treat as complete makes
"file does not exist" conclusions wrong.

## Gitea Actions Endpoints

Actions and commit statuses coexist. Either may be empty independently. A gated PR
often has statuses and few or no runs; a repo on external CI has statuses and no
runs at all.

### List Workflow Runs

```
GET /repos/{owner}/{repo}/actions/runs
```

Query: `event`, `branch`, `status` (pending/queued/in_progress/failure/success/skipped/…),
`actor`, `head_sha`, `exclude_pull_requests`, `page`, `limit`.

Always scope with `head_sha=<pr head sha>` — `status=failure` alone returns
failures from every branch. `exclude_pull_requests=true` empties the bulky
`pull_requests` field on each run.

**Response fields per run:** `id`, `path` (`workflow.yml@ref`), `run_number`,
`run_attempt`, `status`, `conclusion`, `head_sha`, `display_title`, `html_url`,
`started_at`, `completed_at`, `previous_attempt_url`.

`display_title` is the triggering commit's message and can differ from the PR
title — don't use it to identify the PR. Prefer `path` + `run_number`.

Pushing to a PR branch cancels the in-flight run and starts a new one. Both stay
attached to the head SHA, so a `cancelled` run is usually **superseded, not
broken**. Only the highest `run_number` per `path` is current.

### Get / Delete Workflow Run

```
GET    /repos/{owner}/{repo}/actions/runs/{run}
DELETE /repos/{owner}/{repo}/actions/runs/{run}
```

### Run Attempts

```
GET /repos/{owner}/{repo}/actions/runs/{run}/attempts/{attempt}
GET /repos/{owner}/{repo}/actions/runs/{run}/attempts/{attempt}/jobs
```

After a rerun, the previous attempt's logs are still reachable here — the run
object only shows the latest.

### List Jobs for Run

```
GET /repos/{owner}/{repo}/actions/runs/{run}/jobs
```

Returns `{"jobs": [...], "total_count": n}`. Per job: `id`, `name`, `status`,
`conclusion`, `started_at`, `completed_at`, `steps[]` (name, status, conclusion,
number). The job `id` is what the logs endpoint takes.

### List Jobs Across the Repo

```
GET /repos/{owner}/{repo}/actions/jobs
GET /repos/{owner}/{repo}/actions/jobs/{job_id}
```

### Get Job Logs

```
GET /repos/{owner}/{repo}/actions/jobs/{job_id}/logs
```

Raw log text, not JSON. This is the cheapest route to a failure message — try it
before downloading artifacts. Pipe through `tail -200` or `grep`; never
`head -c` a log you intend to reason about, because the interesting part is at the
end.

### Rerun

```
POST /repos/{owner}/{repo}/actions/runs/{run}/rerun
POST /repos/{owner}/{repo}/actions/runs/{run}/rerun-failed-jobs
POST /repos/{owner}/{repo}/actions/runs/{run}/jobs/{job_id}/rerun
```

Note the job rerun path is nested **under the run** — `actions/jobs/{id}/rerun`
does not exist. `rerun-failed-jobs` is the right call for a flaky subset; a
full `rerun` re-does the passing jobs too.

### Dispatch a Workflow

```
POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches
```

Body: `{"ref": "branch-or-tag", "inputs": {...}}`. `workflow_id` is the filename,
e.g. `pr-tests.yml`. Requires `workflow_dispatch` in the workflow's `on:`.

### Workflows

```
GET /repos/{owner}/{repo}/actions/workflows
GET /repos/{owner}/{repo}/actions/workflows/{workflow_id}
GET /repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs
PUT /repos/{owner}/{repo}/actions/workflows/{workflow_id}/enable
PUT /repos/{owner}/{repo}/actions/workflows/{workflow_id}/disable
```

### Tasks and Runners

```
GET /repos/{owner}/{repo}/actions/tasks     # queue view: what is running/queued
GET /repos/{owner}/{repo}/actions/runners   # runners registered to THIS repo
```

`actions/runners` commonly returns `{"runners":[],"total_count":0}` even when CI
works fine — that means the runners are registered at org or instance level, not
per-repo. It is not evidence that CI is broken. Instance-level runners live at
`/admin/runners`, which needs `write:admin` and usually returns 403.

### Artifacts

```
GET    /repos/{owner}/{repo}/actions/runs/{run}/artifacts
GET    /repos/{owner}/{repo}/actions/artifacts
GET    /repos/{owner}/{repo}/actions/artifacts/{artifact_id}
GET    /repos/{owner}/{repo}/actions/artifacts/{artifact_id}/zip
DELETE /repos/{owner}/{repo}/actions/artifacts/{artifact_id}
```

Per artifact: `id`, `name`, `size_in_bytes`, `expired`, `created_at`, `expires_at`, `url`.

Download is always **`/actions/artifacts/{artifact_id}/zip`** and always a zip,
even for a single file. It redirects, so use `curl -sL`. Check `expired` first —
an expired artifact 404s.

## Branch Protections

```
GET    /repos/{owner}/{repo}/branch_protections
POST   /repos/{owner}/{repo}/branch_protections
GET    /repos/{owner}/{repo}/branch_protections/{name}
PATCH  /repos/{owner}/{repo}/branch_protections/{name}
DELETE /repos/{owner}/{repo}/branch_protections/{name}
```

Read this when a PR shows all checks green but still will not merge: it names the
required status contexts, required approval count, and whether the branch demands
an up-to-date head.

## Response Codes

| Code | Meaning |
|------|---------|
| 200/201/204 | Success |
| 401 | Invalid or empty token — check the token actually made it into the header |
| 403 | Insufficient scope; the message names the required scope |
| 404 | Not found — wrong repo for this PR index, nonexistent repo, or a private repo the token cannot see (Gitea returns 404, not 403, to avoid leaking existence) |
| 409 | Conflict (e.g. cannot merge) |
| 422 | Validation error — the response body names the offending field |
