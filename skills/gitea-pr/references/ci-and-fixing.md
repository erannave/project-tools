# Diagnosing and Fixing Gitea CI Failures

Read this when a PR has failing checks and the job is to fix them — "fix the PR",
"fix CI failures", "why is this PR failing". `../SKILL.md` covers setup (transport,
token, owner/repo); this file is only the diagnose-and-fix loop.

The ordering below is deliberate: each step is cheaper than the one after it, and
most failures are solved before the expensive steps.

**Without `tea`.** The examples use `tea api '<path>'` for brevity. Every one of
them translates mechanically to the curl form from `../SKILL.md` — same path, with
the base URL and auth header spelled out:

```bash
curl -s 'BASE_URL/api/v1<path>' -H "Authorization: token $TOKEN"
```

Substitute `{owner}`/`{repo}` yourself, since only `tea` fills those in.

The one command with **no** direct equivalent is `tea actions runs logs <run-id>`.
Gitea's REST API exposes logs per *job* only — there is no run-scoped endpoint —
so `tea` is fanning out client-side. Without it, do the same in two steps: list
the run's jobs, then fetch each job's log. Step 2 spells this out.

## 1. Get the check list

```bash
python3 scripts/pr_checks.py <owner/repo> <pr>
```

One line per check across both mechanisms, then the run ids and job ids of
anything failing. Exit 0 = nothing failing, 1 = failures, 2 = transport error.

Read the output before drilling in:

- **Nothing failing** — stop. Say so. Do not go hunting.
- **Checks still running** — stop and wait. Fixing against a partial result means
  fixing a failure that may not exist, and you will push a commit that restarts
  everything anyway.
- **`superseded by a later run`** — ignore that run. Pushing to a PR branch cancels
  the in-flight run; the cancellation is bookkeeping, not a failure.
- **Combined state `failure` with no failing entry** — a `warning` status (often a
  CI gate) rolls up to `failure`. Read the warning's description; it usually tells
  you exactly what to do, e.g. `gated-off: CI not run - add the CI/Run label`.
  That is a label to add, not code to fix.

## 2. Read the logs before touching artifacts

Job logs are one request and land as plain text. Artifacts are a list call, a
download, an unzip, and often a second unzip. Start with logs.

```bash
tea actions runs logs <run-id>                 # every job in the run
tea actions runs logs <run-id> --job <job-id>  # one job
```

`-f` on this command is `--follow`, **not** `--fields`. `-r owner/repo` and
`-l login` work as usual.

Straight from the API — one job at a time, which is what you want when piping:

```bash
tea api '/repos/OWNER/REPO/actions/jobs/JOB_ID/logs' > /tmp/job.log
# or, without tea:
curl -s 'BASE_URL/api/v1/repos/OWNER/REPO/actions/jobs/JOB_ID/logs' \
  -H "Authorization: token $TOKEN" > /tmp/job.log
```

There is no run-scoped logs endpoint, so to cover a whole run without `tea`, list
its jobs first and loop:

```bash
curl -s "BASE_URL/api/v1/repos/OWNER/REPO/actions/runs/RUN_ID/jobs" \
  -H "Authorization: token $TOKEN" \
  | python3 -c "import sys,json; [print(j['id']) for j in json.load(sys.stdin)['jobs']]" \
  | while read -r jid; do
      echo "=== job $jid ==="
      curl -s "BASE_URL/api/v1/repos/OWNER/REPO/actions/jobs/$jid/logs" \
        -H "Authorization: token $TOKEN" | tail -100
    done
```

`pr_checks.py` already prints the failing job ids, so you can usually skip the
listing step and fetch just the jobs that failed.

Logs are long and the failure is at the **end**. Never `head -c` them:

```bash
tail -200 /tmp/job.log
grep -n -iE 'error|failed|✗|assertion|Traceback|npm ERR' /tmp/job.log | tail -40
```

For a failing *status* rather than a run, the payload is the `description` plus
`target_url`. The description is frequently the whole answer.

## 3. Fetch the PR's own context in parallel

Only once you know which checks failed, and only what you need:

```bash
tea api '/repos/OWNER/REPO/pulls/PR.diff'  > /tmp/pr.diff &
tea api '/repos/OWNER/REPO/pulls/PR/files' > /tmp/pr_files.json &
wait

# without tea:
curl -s 'BASE_URL/api/v1/repos/OWNER/REPO/pulls/PR.diff' \
  -H "Authorization: token $TOKEN" > /tmp/pr.diff &
curl -s 'BASE_URL/api/v1/repos/OWNER/REPO/pulls/PR/files' \
  -H "Authorization: token $TOKEN" > /tmp/pr_files.json &
wait
```

The diff is what tells you whether a failure is *yours*. A test that fails on
files this PR never touched is usually a flake or a pre-existing break on the base
branch — check the base branch's own runs before editing anything.

## 4. Artifacts, when logs are not enough

Structured reports (JUnit XML, ESLint JSON, coverage) are more actionable than log
scraping when a suite has many failures.

```bash
# tea api '...' — or: curl -s 'BASE_URL/api/v1/...' -H "Authorization: token $TOKEN"
tea api '/repos/OWNER/REPO/actions/runs/RUN_ID/artifacts' | python3 -c "
import sys, json
d = json.load(sys.stdin)
for a in d.get('artifacts', d if isinstance(d, list) else []):
    flag = ' EXPIRED' if a.get('expired') else ''
    print(f\"{a['id']:8} {a['size_in_bytes']:>10}  {a['name']}{flag}\")
"
```

Skip anything marked expired — it 404s. Then download; the endpoint is always
`/actions/artifacts/{id}/zip` and always yields a zip, even for one file:

```bash
NAME=test-results
curl -sL "BASE_URL/api/v1/repos/OWNER/REPO/actions/artifacts/ARTIFACT_ID/zip" \
  -H "Authorization: token $TOKEN" -o "/tmp/$NAME.zip"
unzip -qo "/tmp/$NAME.zip" -d "/tmp/$NAME/"

# Some suites bundle sub-reports as nested zips.
find "/tmp/$NAME/" -name '*.zip' | while read -r z; do
  unzip -qo "$z" -d "${z%.zip}/"
done
find "/tmp/$NAME/" -type f | sort
```

### JUnit XML

```bash
python3 - "/tmp/test-results" << 'EOF'
import os, sys, xml.etree.ElementTree as ET
for dirpath, _, files in os.walk(sys.argv[1]):
    for fname in files:
        if not fname.endswith('.xml'):
            continue
        try:
            tree = ET.parse(os.path.join(dirpath, fname))
        except ET.ParseError:
            continue  # not a JUnit file
        for tc in tree.iter('testcase'):
            bad = tc.find('failure')
            if bad is None:
                bad = tc.find('error')
            if bad is None:
                continue
            print(f"FAIL {tc.get('classname')}.{tc.get('name')}")
            print(f"  {bad.get('message', '')}")
            if bad.text:
                print('  ' + bad.text.strip()[:800].replace('\n', '\n  '))
EOF
```

Note `tc.find('failure') or tc.find('error')` is a bug — an Element with no
children is falsy, so a `<failure>` with no sub-elements gets discarded and the
code silently reports nothing. Compare against `None` explicitly, as above.

### ESLint / Biome JSON

```bash
python3 - "/tmp/lint-report/report.json" << 'EOF'
import json, sys
data = json.load(open(sys.argv[1]))
if isinstance(data, list) and data and 'messages' in data[0]:
    for f in data:
        errs = [m for m in f.get('messages', []) if m.get('severity') == 2]
        if errs:
            print(f['filePath'])
            for e in errs:
                print(f"  {e.get('line')}:{e.get('column')}  {e.get('message')} ({e.get('ruleId')})")
else:
    print(json.dumps(data, indent=2)[:2000])
EOF
```

### Plain logs in an artifact

```bash
grep -rn -iE 'error|failed' /tmp/test-results/ --include='*.log' --include='*.txt' | head -40
```

## 5. Fix

1. Confirm which repo you are in — `git remote get-url origin`. If it already
   points at the PR's repo, just check out the branch; do not clone.
   ```bash
   # with tea: tea pr checkout PR
   BRANCH=$(tea api '/repos/OWNER/REPO/pulls/PR' \
     | python3 -c "import sys,json; print(json.load(sys.stdin)['head']['ref'])")
   # without tea:
   BRANCH=$(curl -s 'BASE_URL/api/v1/repos/OWNER/REPO/pulls/PR' \
     -H "Authorization: token $TOKEN" \
     | python3 -c "import sys,json; print(json.load(sys.stdin)['head']['ref'])")
   git fetch origin "$BRANCH" && git checkout "$BRANCH"
   ```
2. Map each failure message to a specific file and line. If you cannot, you do not
   understand the failure yet — go back to the logs.
3. Edit the source. Fix causes, not symptoms: deleting an assertion or widening a
   timeout to make a test pass is not a fix.
4. Reproduce locally where the project makes that possible — run the same test or
   lint command the workflow ran. The command is in the job log.

**Do not guess at these** — report them to the user instead of editing code:

- Failures in a dependency, a base image, or a registry outage.
- Failures in CI configuration you were not asked to change.
- Failures that also fail on the base branch — that is a pre-existing break, and
  fixing it inside this PR muddies the diff.
- Flakes. If a test fails on code this PR never touched and passes on rerun, say
  so; `POST /actions/runs/{run}/rerun-failed-jobs` reruns only what failed.

## 6. Commit and push

Stage only the files you deliberately changed — never `git add .`, which sweeps up
downloaded artifacts and scratch files.

```bash
git add path/to/file1 path/to/file2
git status --short          # confirm nothing unexpected is staged
git commit -m "fix: <what actually broke, in one line>"
git push origin HEAD
```

Describe the fix, not the ritual. "fix: await the file-list request before
asserting row count" beats "fix: resolve CI failures".

## 7. Comment on the PR

Write the body to a file first, then post the file. Do not try to interpolate a
multi-line summary through nested shell quoting — that is how comment snippets
break.

```bash
cat > /tmp/pr_comment.md << 'EOF'
Fixed the failing checks:

- `static-and-e2e` — the schedule-dialog spec asserted before the file list loaded.
EOF

tea comment add PR "$(cat /tmp/pr_comment.md)"
```

Without `tea`, build the JSON with Python (which escapes correctly) and post the
file with `curl -d @`:

```bash
python3 -c "
import json, sys
print(json.dumps({'body': open('/tmp/pr_comment.md').read()}))
" > /tmp/pr_comment.json

curl -s -X POST 'BASE_URL/api/v1/repos/OWNER/REPO/issues/PR/comments' \
  -H "Authorization: token $TOKEN" \
  -H 'Content-Type: application/json' \
  -d @/tmp/pr_comment.json
```

To include a screenshot, upload it as an attachment first and embed the returned
`browser_download_url` — see the attachments section in `gitea-api.md`.

## 8. Verify

Pushing starts a new run. Re-run the check script after CI settles rather than
declaring victory on the strength of the edit:

```bash
python3 scripts/pr_checks.py <owner/repo> <pr>
```

If checks are still pending, say they are pending. Report what the checks actually
show, including anything you chose not to fix and why.
