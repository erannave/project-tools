---
name: gitea-pr
description: |
  Gitea pull request management, CI inspection, and CI failure fixing. Use this skill when:
  - User provides ANY URL containing "gitea" (trigger immediately before responding)
  - User mentions "Gitea" with PRs, code review, or repositories
  - Creating, reviewing, commenting on, or merging pull requests on Gitea
  - User says "create a PR", "submit for review" when working with a Gitea remote
  - User asks about CI status, check results, failed checks, or build artifacts on a PR
  - User says "fix the PR", "fix CI failures", "fix failing checks", or asks why a PR is failing
  Handles the complete PR lifecycle: creation, drafts, review, comments, approvals,
  merging, CI check inspection, and diagnosing and fixing CI failures.
---

# Gitea Pull Requests

## Step 1: Pick a transport

```bash
command -v tea >/dev/null 2>&1 && echo TEA || echo CURL
```

**Prefer `tea`.** It is not just shorter — it removes the two failure modes that
actually bite. `tea` keeps the token in `~/.config/tea/config.yml`, so there is no
environment variable name to guess, and it derives `owner/repo` from the git
remote, so there is nothing to mistype. Use the curl path only when `tea` is
absent.

Either way, identify the target repo the same way:

- **From a Gitea URL** like `https://gitea.example.com/owner/repo/pulls/123` —
  read base URL, owner, repo, and index straight off the URL.
- **From a checkout** — `git remote get-url origin`. Take `owner/repo` verbatim
  from the remote.

PR indices are **per-repo**, not global. Index 1197 exists in several repos and
means something different in each.

## Step 2 (tea path): commands

Run these from inside the repo checkout and `tea` infers login and repo. From
anywhere else, add `-l <login> -r <owner>/<repo>` — written **literally**, not via
a shell variable, because zsh (which the Bash tool runs) does not word-split
unquoted parameters, so `R="-l x -r y"; tea $R ...` fails with
*flag provided but not defined*.

| Operation | Command |
|---|---|
| PR details | `tea pr <n> -o json` |
| Bulk list | `tea pr ls --state all --limit 50 -f index,title,state,head,ci -o tsv` |
| Diff | `tea api '/repos/{owner}/{repo}/pulls/<n>.diff'` |
| Changed files | `tea api '/repos/{owner}/{repo}/pulls/<n>/files'` |
| Create PR | `tea pr create --base main --head <branch> -t "<title>" -d "<body>"` |
| Create **draft** | `tea pr create --draft --base main --head <branch> -t "<title>"` |
| Mark ready | `tea pr edit <n> -t "<title without the WIP: prefix>"` |
| Edit title/body | `tea pr edit <n> -t "..." -d "..."` |
| Comment | `tea comment <n> "$(cat body.md)"` |
| Review comments | `tea pr rc <n> -o tsv` · resolve with `tea pr resolve <comment-id>` |
| Approve / reject | `tea pr approve <n>` · `tea pr reject <n> "<reason>"` |
| Merge | `tea pr merge <n> -s squash` |
| Check out locally | `tea pr checkout <n>` |
| Actions runs | `tea actions runs ls --branch <head-branch> --limit 5 -o tsv` |
| Job logs | `tea actions runs logs <run-id> [--job <job-id>]` |
| Anything else | `tea api [-X POST] '/repos/{owner}/{repo}/...'` |

`tea api` prefixes `/api/v1` for you and substitutes `{owner}`/`{repo}` from the
repo context. Send a body with `-f key=value` (string), `-F key=value` (typed, and
`@file` / `@-` to read from a file or stdin), or `-d '<raw json>'` / `-d @file`.
`-d` cannot be combined with `-f`/`-F`.

**`-f` means three different things in `tea`.** On `tea pr ls` it is `--fields`; on
`tea actions runs logs` it is `--follow`; on `tea api` it is `--field`. Check the
subcommand's `--help` before reusing a flag.

**`tea api` exits 0 on a 404** and prints Gitea's error envelope,
`{"message":"not found","url":"..."}`, on stdout. Never chain it with `&&` and
assume success — check the body for a `message` key. Other `tea` subcommands do
exit non-zero. Outside a Gitea checkout, `tea` reports
`Error: remote repository required: specify id via --repo`; add `-l` and `-r`.

`tea pr <n>` **ignores `--fields`** and renders the full PR body as markdown —
which is a lot of tokens. Use `-o json` for a single PR and pipe it, or use
`tea pr ls -f ...` when you want columns.

## Drafts are a title convention, not a flag

Gitea has **no `draft` field** on PR create or edit — it is absent from both
`CreatePullRequestOption` and `EditPullRequestOption`. `PullRequest.draft` appears
in *responses* only and is derived from the title.

A PR is a draft iff its title starts with a configured WIP prefix — `WIP:` or
`[WIP]` by default. So:

- **Create a draft:** title it `WIP: <title>`, or let `tea pr create --draft`
  prepend the prefix.
- **Mark it ready:** PATCH the title with the prefix stripped
  (`tea pr edit <n> -t "<title>"`). There is no "ready for review" endpoint.

Prefixes are server-configurable and not exposed via the API. If `draft` comes
back `false` on a PR you titled `WIP:`, that instance uses different prefixes.

## Step 2 (curl path): token and calls

Only when `tea` is unavailable.

```bash
for f in ~/.zshenv ~/.zshrc ~/.bashrc ~/.profile; do [ -f "$f" ] && source "$f" 2>/dev/null; done
[ -f .env ] && export $(grep -v '^#' .env | xargs) 2>/dev/null
TOKEN=$(printf '%s' "${GITEA_ACCESS_TOKEN:-${GITEA_TOKEN:-$GITEA_API_TOKEN}}" | tr -d '\r\n ')
echo "Token length: ${#TOKEN}"
```

Probe all three names — `GITEA_ACCESS_TOKEN` is the most common, and reading only
`GITEA_TOKEN` is the single largest source of `401`/`NO_TOKEN` failures. Sandboxes
start with a clean environment, which is why the sourcing comes first. Use
`$TOKEN` as-is afterwards; it is already stripped.

If it is still empty, tell the user to set `GITEA_ACCESS_TOKEN` in their shell
environment or a local `.env` (Gitea → Settings → Applications). Scopes are
`<read|write>:<category>` on modern Gitea, **not** the old `repo` — you want
`write:repository`, `write:issue`, `read:organization`, `read:user`, plus
`read:admin` / `write:user` for admin-ish reads. A `403` names the scope it wanted.

Substitute the literal base URL, owner, repo, and index into each call:

```bash
curl -s 'BASE_URL/api/v1/repos/OWNER/REPO/pulls/PR_NUMBER' -H "Authorization: token $TOKEN"
```

If a call ever fails with `curl: (3) URL rejected: No host part in the given URL`,
an env var carried an invisible character — substitute the base URL literally
instead of interpolating a variable.

### Triaging `404 {"message":"not found"}`

This is the most common error. Check in this order:

1. **Wrong repo for this index.** PR indices are per-repo; an index copied from
   another repo's URL 404s. Confirm the PR belongs to the repo you are calling.
2. **Repo name typo, or a private repo the token cannot see.** Gitea returns 404
   rather than 403 for invisible repos, so this looks identical to nonexistent.
3. **Endpoint path.** e.g. `actions/jobs/{id}/rerun` does not exist; the real path
   is `actions/runs/{run}/jobs/{id}/rerun`.

**Casing is not the problem.** Owner and repo names are case-insensitive —
`Batalyse/batalyse`, `BATALYSE/batalyse`, and `batalyse/dataanalysis` all resolve
identically. Do not spend a turn "fixing" capitalisation.

## Step 3: CI checks

Gitea reports CI through two independent mechanisms that **coexist**: commit
statuses (`/commits/{sha}/status`) and Actions runs (`/actions/runs?head_sha=`).
Either can be empty while the other is populated. Reading one and reporting "no
checks" is wrong.

Run the bundled summariser — it covers both, and handles the schema traps:

```bash
python3 scripts/pr_checks.py <owner/repo> <pr>
```

`scripts/pr_checks.py` sits next to this file; resolve it against **this skill's
own directory**, not the current working directory. When installed as a plugin
that directory is version-pinned, so do not hardcode it — if the relative path
does not resolve, locate it once:

```bash
PR_CHECKS=$(find "${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins}" \
  -name pr_checks.py -path '*gitea-pr*' 2>/dev/null | sort -V | tail -1)
```

It prefers `tea api` and falls back to direct HTTP with the token probe above, so
it works on either transport. Exit 0 = nothing failing, 1 = failures, 2 =
transport error. Failing runs come with their run ids and job ids, ready for
`tea actions runs logs <run-id>` or, without `tea`,
`GET /repos/{owner}/{repo}/actions/jobs/{job_id}/logs`.

Do not hand-roll this summary inline. Three things go wrong every time:

- **`s['state']` on a status entry raises `KeyError`.** The combined response uses
  `state` at the top level but **`status`** on each entry in `statuses[]`.
- **The top-level `state` is a roll-up.** A single `warning` entry rolls it up to
  `failure`, so a fully-green gated PR reports `failure`. The same applies to
  `tea pr ls -f ci`, which reads that roll-up — treat `failure` there as "look
  closer", not "broken". Only `pr_checks.py` distinguishes them.
- **A `cancelled` run is usually superseded, not broken.** Pushing to a PR branch
  cancels the in-flight run; both stay attached to the head SHA.

Never `head -c` an API response or a log to trim it — that cuts mid-JSON and mid
stack-trace. Select fields, or `tail` the log; the failure is at the end.

Page with `page=1,2,3…` rather than pushing `limit` to 300. An oversized `limit` is
silently clamped, so the request looks complete while dropping the tail.

**When checks are failing and the job is to fix them**, follow
[references/ci-and-fixing.md](references/ci-and-fixing.md).

## Quick Reference

Paths are relative to `{base_url}/api/v1`.

| Operation | Endpoint | Method |
|-----------|----------|--------|
| Create PR | `/repos/{owner}/{repo}/pulls` | POST |
| Get PR | `/repos/{owner}/{repo}/pulls/{index}` | GET |
| Update PR (incl. draft→ready) | `/repos/{owner}/{repo}/pulls/{index}` | PATCH |
| Get diff | `/repos/{owner}/{repo}/pulls/{index}.diff` | GET |
| List files | `/repos/{owner}/{repo}/pulls/{index}/files` | GET |
| PR commits | `/repos/{owner}/{repo}/pulls/{index}/commits` | GET |
| Add comment | `/repos/{owner}/{repo}/issues/{index}/comments` | POST |
| Upload attachment | `/repos/{owner}/{repo}/issues/{index}/assets` | POST (multipart) |
| Submit review | `/repos/{owner}/{repo}/pulls/{index}/reviews` | POST |
| Review's line comments | `/repos/{owner}/{repo}/pulls/{index}/reviews/{id}/comments` | GET |
| Merge PR | `/repos/{owner}/{repo}/pulls/{index}/merge` | POST |
| Labels (repo / on PR) | `/repos/{owner}/{repo}/labels` · `/issues/{index}/labels` | GET / POST |
| Combined status | `/repos/{owner}/{repo}/commits/{sha}/status` | GET |
| Get commit | `/repos/{owner}/{repo}/git/commits/{sha}` | GET |
| Get tree | `/repos/{owner}/{repo}/git/trees/{sha}` | GET |
| Actions runs | `/repos/{owner}/{repo}/actions/runs?head_sha={sha}` | GET |
| Run jobs | `/repos/{owner}/{repo}/actions/runs/{run}/jobs` | GET |
| Job logs | `/repos/{owner}/{repo}/actions/jobs/{job_id}/logs` | GET |
| Rerun failed jobs | `/repos/{owner}/{repo}/actions/runs/{run}/rerun-failed-jobs` | POST |
| Artifact download | `/repos/{owner}/{repo}/actions/artifacts/{id}/zip` | GET |

Full schemas, the rerun family, timeline, branch protections, and the remaining
endpoints: [references/gitea-api.md](references/gitea-api.md).
