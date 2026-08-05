#!/usr/bin/env python3
"""Summarise every CI check on a Gitea pull request in one pass.

    python3 pr_checks.py <owner/repo> <pr> [options]

Gitea reports CI through two independent, coexisting mechanisms:

  * commit statuses   (/commits/{sha}/status)      — external CI, gates, bots
  * Actions runs      (/actions/runs?head_sha=)    — Gitea Actions workflows

Either can be empty while the other is populated. A gated PR typically has
statuses and few or no runs; a repo using only external CI has statuses and no
runs at all. Code that reads one source and reports "no checks" is wrong.

Two schema traps this script exists to avoid:

  * entries in `statuses[]` carry their state under the key **`status`**, not
    `state`. `state` only exists at the top level of the combined response.
  * the combined top-level `state` is rolled up: it can read `failure` when no
    individual entry is a failure (a `warning` entry rolls up to failure). Read
    the entries, not just the roll-up.

Transport: uses `tea api` when `tea` is on PATH (it holds the token in
~/.config/tea/config.yml, so there is no environment variable to get wrong).
Falls back to direct HTTP with a token from GITEA_ACCESS_TOKEN,
GITEA_TOKEN, or GITEA_API_TOKEN, in that order.

Exit status: 0 when nothing is failing, 1 when at least one check failed,
2 on a transport or lookup error.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

PAGE_SIZE = 50
MAX_PAGES = 40

# status/conclusion values, bucketed. Anything unrecognised is reported verbatim
# and treated as neither passing nor failing.
FAILED = {"failure", "error", "cancelled", "timed_out", "action_required"}
PASSED = {"success", "skipped"}
PENDING = {"pending", "queued", "waiting", "running", "in_progress", "blocked"}
WARNED = {"warning"}


class TransportError(RuntimeError):
    pass


class Transport:
    """Fetches API paths, preferring `tea api` over raw HTTP."""

    def __init__(self, base_url=None, login=None, use_tea=True):
        self.login = login
        self.base_url = base_url.rstrip("/") if base_url else None
        self.tea = shutil.which("tea") if use_tea else None
        self.token = None
        if not self.tea:
            self.base_url = self.base_url or _base_url_from_git_remote()
            if not self.base_url:
                raise TransportError(
                    "no `tea` on PATH and no base URL — pass --base-url, or run "
                    "from a clone whose origin points at the Gitea instance"
                )
            self.token = _token_from_env()
            if not self.token:
                raise TransportError(
                    "no API token found. Export GITEA_ACCESS_TOKEN (or "
                    "GITEA_TOKEN / GITEA_API_TOKEN), or install and log in "
                    "with `tea login add`"
                )

    def get(self, path):
        """GET an /api/v1-relative path and return parsed JSON."""
        if self.tea:
            cmd = [self.tea, "api"]
            if self.login:
                cmd += ["-l", self.login]
            cmd.append(path if path.startswith("/") else "/" + path)
            # tea writes its login NOTE to stderr, so stdout stays clean JSON.
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                raise TransportError(
                    f"tea api {path} failed: "
                    f"{(proc.stderr or proc.stdout).strip()[:400]}"
                )
            body = proc.stdout
        else:
            url = f"{self.base_url}/api/v1{path if path.startswith('/') else '/' + path}"
            req = urllib.request.Request(
                url, headers={"Authorization": f"token {self.token}"}
            )
            try:
                with urllib.request.urlopen(req) as resp:
                    body = resp.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:400]
                raise TransportError(f"HTTP {exc.code} on {url}: {detail}") from None
            except urllib.error.URLError as exc:
                raise TransportError(f"cannot reach {url}: {exc.reason}") from None
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            raise TransportError(
                f"non-JSON response for {path}: {body.strip()[:300]}"
            ) from None
        # `tea api` exits 0 on a 4xx and prints Gitea's error envelope, so a 404
        # would otherwise sail through as a valid object. No real payload
        # consists solely of these keys.
        if (
            isinstance(data, dict)
            and "message" in data
            and set(data) <= {"message", "url", "errors"}
        ):
            raise TransportError(f"{path}: {data['message']}")
        return data


def _token_from_env():
    for name in ("GITEA_ACCESS_TOKEN", "GITEA_TOKEN", "GITEA_API_TOKEN"):
        raw = os.environ.get(name)
        if raw:
            # Env vars picked up from sourced shell configs often carry a
            # trailing \r or stray whitespace; both break the auth header.
            cleaned = raw.strip().strip("\r\n")
            if cleaned:
                return cleaned
    return None


def _base_url_from_git_remote():
    try:
        remote = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    m = re.match(r"^ssh://git@([^/:]+)(?::\d+)?/", remote) or re.match(
        r"^git@([^:]+):", remote
    )
    if m:
        return f"https://{m.group(1)}"
    m = re.match(r"^(https?://)(?:[^@/]+@)?([^/]+)/", remote)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    return None


def _bucket(value):
    v = (value or "").lower()
    if v in FAILED:
        return "fail"
    if v in WARNED:
        return "warn"
    if v in PASSED:
        return "pass"
    if v in PENDING:
        return "pending"
    return "other"


MARK = {
    "pass": "ok  ",
    "fail": "FAIL",
    "warn": "warn",
    "pending": "....",
    "other": "?   ",
    "superseded": "--  ",
}


def fetch_statuses(api, owner_repo, sha):
    """Combined status for a commit: latest entry per context, already deduped."""
    data = api.get(f"/repos/{owner_repo}/commits/{sha}/status")
    entries = data.get("statuses") or []
    total = data.get("total_count")
    if isinstance(total, int) and total > len(entries):
        # Combined status is not paginated by Gitea, but say so rather than
        # silently reporting a short list.
        print(
            f"note: combined status reports {total} entries but returned "
            f"{len(entries)}; see /commits/{sha}/statuses for the full history",
            file=sys.stderr,
        )
    return data.get("state"), entries


def fetch_runs(api, owner_repo, sha):
    """Every Actions run for this exact commit, paged rather than limit-bombed."""
    runs, page = [], 1
    while page <= MAX_PAGES:
        data = api.get(
            f"/repos/{owner_repo}/actions/runs"
            f"?head_sha={urllib.parse.quote(sha)}&page={page}&limit={PAGE_SIZE}"
        )
        batch = data.get("workflow_runs") or []
        runs.extend(batch)
        total = data.get("total_count")
        if not batch or len(batch) < PAGE_SIZE:
            break
        if isinstance(total, int) and len(runs) >= total:
            break
        page += 1
    return runs


def fetch_failed_jobs(api, owner_repo, run_id):
    """Job ids for a non-passing run — the input to /actions/jobs/{id}/logs."""
    try:
        data = api.get(f"/repos/{owner_repo}/actions/runs/{run_id}/jobs")
    except TransportError as exc:
        print(f"    (could not list jobs for run {run_id}: {exc})", file=sys.stderr)
        return []
    jobs = data.get("jobs") if isinstance(data, dict) else data
    return [j for j in (jobs or []) if _bucket(j.get("conclusion") or j.get("status")) != "pass"]


def main():
    parser = argparse.ArgumentParser(
        description="Summarise all CI checks on a Gitea pull request."
    )
    parser.add_argument("repo", help="owner/repo, exactly as it appears in the remote")
    parser.add_argument("pr", type=int, help="pull request index")
    parser.add_argument("--base-url", help="Gitea base URL (curl path only)")
    parser.add_argument("--login", help="tea login name, when more than one is configured")
    parser.add_argument("--no-tea", action="store_true", help="force the direct-HTTP path")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    if "/" not in args.repo:
        parser.error("repo must be owner/repo, e.g. batalyse/batalyse")

    try:
        api = Transport(args.base_url, args.login, use_tea=not args.no_tea)
        pr = api.get(f"/repos/{args.repo}/pulls/{args.pr}")
    except TransportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        if "404" in str(exc) or "not found" in str(exc).lower():
            print(
                "hint: PR indices are per-repo — confirm index %d belongs to %s "
                "and not to another repo. Then check the repo name, and that the "
                "token can see it (Gitea returns 404, not 403, for private repos "
                "it will not reveal). Owner/repo casing is NOT the problem; "
                "Gitea matches those case-insensitively."
                % (args.pr, args.repo),
                file=sys.stderr,
            )
        return 2

    sha = (pr.get("head") or {}).get("sha")
    if not sha:
        print(f"error: PR {args.pr} has no head SHA (deleted branch?)", file=sys.stderr)
        return 2

    try:
        combined, statuses = fetch_statuses(api, args.repo, sha)
        runs = fetch_runs(api, args.repo, sha)
    except TransportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    checks = []
    for s in sorted(statuses, key=lambda s: s.get("context") or ""):
        # `status`, not `state` — `state` is absent from entries.
        state = s.get("status")
        checks.append(
            {
                "source": "status",
                "name": s.get("context") or "(no context)",
                "state": state,
                "bucket": _bucket(state),
                "detail": s.get("description") or "",
                "url": s.get("target_url") or "",
            }
        )
    # Pushing to a PR branch re-triggers the workflow, and Gitea cancels the
    # in-flight run rather than deleting it. Those cancelled runs stay attached
    # to the head SHA on a force-push, so treating every `cancelled` as a
    # failure sends you chasing a run that was simply superseded. Only the
    # highest run_number per workflow path is current.
    latest_per_path = {}
    for r in runs:
        key = r.get("path") or ""
        number = r.get("run_number") or 0
        if number >= latest_per_path.get(key, (-1,))[0]:
            latest_per_path[key] = (number, r.get("id"))
    current_ids = {rid for _, rid in latest_per_path.values()}

    for r in sorted(runs, key=lambda r: r.get("run_number") or 0):
        state = r.get("conclusion") or r.get("status")
        superseded = r.get("id") not in current_ids
        checks.append(
            {
                "source": "run",
                "name": f"{r.get('path') or 'run'} #{r.get('run_number')}",
                "state": state,
                "bucket": "superseded" if superseded else _bucket(state),
                "detail": "superseded by a later run" if superseded else "",
                "run_id": r.get("id"),
                "url": r.get("html_url") or "",
            }
        )

    failing = [c for c in checks if c["bucket"] == "fail"]
    failing_runs = [c for c in failing if c["source"] == "run"]

    if args.json:
        for c in failing_runs:
            c["failed_jobs"] = [
                {"id": j.get("id"), "name": j.get("name")}
                for j in fetch_failed_jobs(api, args.repo, c["run_id"])
            ]
        json.dump(
            {
                "repo": args.repo,
                "pr": args.pr,
                "title": pr.get("title"),
                "draft": pr.get("draft"),
                "head_sha": sha,
                "combined_state": combined,
                "checks": checks,
            },
            sys.stdout,
            indent=2,
        )
        print()
        return 1 if failing else 0

    print(f"{args.repo}#{args.pr}  {pr.get('title', '')}")
    print(f"head {sha[:12]}  combined status: {combined or 'none'}")
    if pr.get("draft"):
        print("draft: true (title carries a WIP prefix)")
    print()

    if not checks:
        print("No checks reported for this commit — no commit statuses and no")
        print("Actions runs. CI may be gated off, not configured, or not yet")
        print("triggered for this head SHA.")
        return 0

    width = max(len(c["name"]) for c in checks)
    for c in checks:
        line = f"  {MARK[c['bucket']]} [{c['source']:6}] {c['name']:<{width}}  {c['state']}"
        if c["detail"] and c["detail"] != c["name"]:
            line += f" — {c['detail']}"
        print(line)

    if combined in FAILED and not any(c["bucket"] == "fail" for c in checks if c["source"] == "status"):
        print(
            f"\nnote: combined state is '{combined}' but no individual status "
            "failed — a 'warning' entry rolls up to failure."
        )

    if not failing:
        pending = [c for c in checks if c["bucket"] == "pending"]
        print(
            f"\n{len(pending)} check(s) still running — re-run before concluding."
            if pending
            else "\nNothing failing."
        )
        return 0

    print(f"\n{len(failing)} failing check(s):")
    for c in failing:
        if c["source"] == "run":
            print(f"  run {c['run_id']}  {c['name']}")
            for j in fetch_failed_jobs(api, args.repo, c["run_id"]):
                print(
                    f"    job {j.get('id')}  {j.get('name')}  "
                    f"({j.get('conclusion') or j.get('status')})"
                )
        else:
            print(f"  status {c['name']}: {c['detail']}")
            if c["url"]:
                print(f"    {c['url']}")

    if failing_runs:
        ids = " ".join(str(c["run_id"]) for c in failing_runs)
        print(f"\nLogs:  tea actions runs logs <run-id>   # run ids: {ids}")
        print("       or GET /repos/%s/actions/jobs/<job-id>/logs" % args.repo)
    return 1


if __name__ == "__main__":
    sys.exit(main())
