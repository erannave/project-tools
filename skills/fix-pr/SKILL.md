---
name: fix-pr
description: |
  Slash command `/fix-pr <PR_URL>` — fetches all CI check results from a Gitea PR and
  automatically fixes every failing issue found. Use this skill whenever the user runs
  `/fix-pr`, mentions "fix the PR", "fix CI failures", "fix failing checks", or asks you
  to look at why a PR is failing and fix it. Works with both traditional commit statuses
  and Gitea Actions workflow runs. Reads failure logs, diffs, and artifacts, then applies
  code fixes and pushes them to the PR branch.
---

# /fix-pr

Fix all CI check failures for a Gitea pull request.

## Usage

```
/fix-pr <PR_URL>
```

Example: `/fix-pr https://gitea.example.com/owner/repo/pulls/42`

---

## Workflow

### Step 1: Parse PR URL

Extract from the URL:
- `BASE_URL` — e.g. `https://gitea.example.com`
- `OWNER`, `REPO` — e.g. `owner`, `repo`
- `PR_NUMBER` — e.g. `42`

### Step 2: Get API Token

```bash
printf '%s' "$GITEA_TOKEN" | tr -d '\r\n '
```

If empty, try sourcing shell configs first. If still empty, tell the user to set `GITEA_TOKEN`.

### Step 3: Gather all PR data in parallel

Run these concurrently (using `&` + `wait`) to minimize round-trips:

```bash
TOKEN=$(printf '%s' "$GITEA_TOKEN" | tr -d '\r\n ')

# PR details (for head SHA, branch name, author)
curl -s 'BASE_URL/api/v1/repos/OWNER/REPO/pulls/PR_NUMBER' \
  -H "Authorization: token $TOKEN" > /tmp/fixpr_pr.json &

# Changed files
curl -s 'BASE_URL/api/v1/repos/OWNER/REPO/pulls/PR_NUMBER/files' \
  -H "Authorization: token $TOKEN" > /tmp/fixpr_files.json &

# Diff
curl -s 'BASE_URL/api/v1/repos/OWNER/REPO/pulls/PR_NUMBER.diff' \
  -H "Authorization: token $TOKEN" > /tmp/fixpr_diff.patch &

wait
```

Then extract the head SHA and branch:

```bash
python3 -c "
import json
pr = json.load(open('/tmp/fixpr_pr.json'))
print('SHA:', pr['head']['sha'])
print('Branch:', pr['head']['ref'])
print('Repo clone URL:', pr['head']['repo']['clone_url'])
"
```

### Step 4: Fetch check results in parallel

```bash
TOKEN=$(printf '%s' "$GITEA_TOKEN" | tr -d '\r\n ')
SHA=<head SHA from step 3>

# Combined commit status (traditional CI like Jenkins, CircleCI)
curl -s "BASE_URL/api/v1/repos/OWNER/REPO/commits/$SHA/status" \
  -H "Authorization: token $TOKEN" > /tmp/fixpr_status.json &

# Gitea Actions runs for this commit
curl -s "BASE_URL/api/v1/repos/OWNER/REPO/actions/runs?head_sha=$SHA" \
  -H "Authorization: token $TOKEN" > /tmp/fixpr_runs.json &

wait
```

### Step 5: Identify all failures

```bash
python3 << 'EOF'
import json, sys

# Traditional statuses
status = json.load(open('/tmp/fixpr_status.json'))
print(f"Combined status: {status.get('state', 'unknown')}")
failures = []
for s in status.get('statuses', []):
    icon = '✓' if s['state'] == 'success' else ('⏳' if s['state'] == 'pending' else '✗')
    print(f"  {icon} [{s['state']:8}] {s['context']}: {s['description']}")
    if s['state'] in ('failure', 'error'):
        failures.append({'type': 'status', 'context': s['context'], 'url': s.get('target_url', '')})

# Actions runs
runs_data = json.load(open('/tmp/fixpr_runs.json'))
for run in runs_data.get('workflow_runs', []):
    icon = '✓' if run['conclusion'] == 'success' else ('⏳' if run['status'] != 'completed' else '✗')
    print(f"  {icon} [{run.get('conclusion', run['status']):8}] {run['name']} #{run['run_number']}")
    if run.get('conclusion') in ('failure', 'cancelled') or run.get('status') == 'failure':
        failures.append({'type': 'actions', 'run_id': run['id'], 'name': run['name']})

print(f"\n{len(failures)} failure(s) to fix")
for f in failures:
    print(f"  - {f}")

# Write summary for commit message use later
with open('/tmp/fixpr_failure_summary.txt', 'w') as out:
    out.write(f"CI failures found: {len(failures)}\n")
    for f in failures:
        out.write(f"- {f.get('context') or f.get('name', str(f))}\n")

if not failures:
    print("\nAll checks are passing — nothing to fix.")
    sys.exit(0)
EOF
```

If the script exits with 0 and prints "All checks are passing", stop here and tell the user.

### Step 6: Get failure details

For each failing **Actions run**, fetch jobs and logs:

```bash
TOKEN=$(printf '%s' "$GITEA_TOKEN" | tr -d '\r\n ')

# Get jobs with step-level detail
curl -s 'BASE_URL/api/v1/repos/OWNER/REPO/actions/runs/RUN_ID/jobs' \
  -H "Authorization: token $TOKEN" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for job in data.get('jobs', data if isinstance(data, list) else []):
    if job.get('conclusion') not in ('success', 'skipped'):
        print(f'Job: {job[\"name\"]} ({job.get(\"conclusion\", job[\"status\"])})')
        for step in job.get('steps', []):
            if step.get('conclusion') not in ('success', 'skipped', None):
                print(f'  Step failed: {step[\"name\"]}')
"

# Get artifacts (test reports, coverage, etc.)
curl -s 'BASE_URL/api/v1/repos/OWNER/REPO/actions/runs/RUN_ID/artifacts' \
  -H "Authorization: token $TOKEN" | python3 -c "
import sys, json
data = json.load(sys.stdin)
artifacts = data.get('artifacts', data if isinstance(data, list) else [])
for a in artifacts:
    print(f'Artifact: {a[\"name\"]} ({a[\"size_in_bytes\"]} bytes) — id={a[\"id\"]}')
"
```

Download and inspect relevant artifacts (test results, lint reports). Artifacts are always served as zip files — even if the artifact contains a single file:

```bash
TOKEN=$(printf '%s' "$GITEA_TOKEN" | tr -d '\r\n ')

# Download — always a zip, follow the redirect
curl -sL 'BASE_URL/api/v1/repos/OWNER/REPO/actions/artifacts/ARTIFACT_ID/zip' \
  -H "Authorization: token $TOKEN" \
  -o /tmp/fixpr_artifact_NAME.zip

# Unzip into its own directory
unzip -o /tmp/fixpr_artifact_NAME.zip -d /tmp/fixpr_artifact_NAME/

# List all contents recursively so you know what you're working with
find /tmp/fixpr_artifact_NAME/ -type f | sort
```

Then read each relevant file. Common patterns and how to handle them:

```bash
# JUnit XML (most CI test runners)
python3 << 'EOF'
import os, xml.etree.ElementTree as ET
root_dir = '/tmp/fixpr_artifact_NAME'
for dirpath, _, files in os.walk(root_dir):
    for fname in files:
        if fname.endswith('.xml'):
            path = os.path.join(dirpath, fname)
            try:
                tree = ET.parse(path)
                for tc in tree.iter('testcase'):
                    failure = tc.find('failure') or tc.find('error')
                    if failure is not None:
                        print(f"FAIL: {tc.get('classname')}.{tc.get('name')}")
                        print(f"  {failure.get('message', '')}")
                        if failure.text:
                            print(f"  {failure.text[:500]}")
            except ET.ParseError:
                pass  # not a JUnit file
EOF

# Plain text / log files
find /tmp/fixpr_artifact_NAME/ -type f \( -name "*.log" -o -name "*.txt" \) \
  | xargs grep -l -i "error\|fail\|FAILED" 2>/dev/null \
  | while read f; do
      echo "=== $f ==="; grep -i "error\|fail\|FAILED" "$f" | head -30; echo
    done

# JSON reports (eslint, coverage, etc.)
find /tmp/fixpr_artifact_NAME/ -name "*.json" -type f | while read f; do
  echo "=== $f ==="
  python3 -c "
import json, sys
try:
    data = json.load(open('$f'))
    # ESLint format
    if isinstance(data, list) and data and 'messages' in data[0]:
        for file_result in data:
            errors = [m for m in file_result.get('messages', []) if m.get('severity') == 2]
            if errors:
                print(file_result['filePath'])
                for e in errors:
                    print(f\"  Line {e.get('line')}: {e.get('message')} ({e.get('ruleId')})\")
    else:
        print(json.dumps(data, indent=2)[:1000])
except: pass
"
done
```

If the artifact itself contains nested zips (e.g. test suites that bundle sub-reports), unzip recursively:

```bash
find /tmp/fixpr_artifact_NAME/ -name "*.zip" | while read nested; do
  dest="${nested%.zip}"
  unzip -o "$nested" -d "$dest/"
  echo "Unpacked: $nested → $dest/"
done
find /tmp/fixpr_artifact_NAME/ -type f | sort  # re-list after unpacking
```

For failing **traditional statuses**, visit `target_url` if it points to an internal system, or note the description as a hint.

### Step 7: Understand the failures and fix the code

With the diff, changed files, and failure logs in hand:

1. **Read the relevant source files** from the local repo (run `git status` first to confirm which repo you're in; if the PR branch isn't checked out, clone or switch to it)
2. **Identify root causes** — map each failure message to the specific file/line
3. **Apply fixes** — edit the files directly using your tools
4. **Verify locally if possible** — run the relevant test/lint command to confirm the fix

If you're not in the correct local repo, clone it first:
```bash
# Get clone URL from /tmp/fixpr_pr.json
CLONE_URL=$(python3 -c "import json; print(json.load(open('/tmp/fixpr_pr.json'))['head']['repo']['clone_url'])")
BRANCH=$(python3 -c "import json; print(json.load(open('/tmp/fixpr_pr.json'))['head']['ref'])")
git clone "$CLONE_URL" /tmp/fixpr_repo --branch "$BRANCH" --depth 1
cd /tmp/fixpr_repo
```

### Step 8: Commit and push fixes

Stage specific files you changed (not `git add .` — only what you intentionally modified):

```bash
git add path/to/file1 path/to/file2
git commit -m "fix: resolve CI failures

$(cat /tmp/fixpr_failure_summary.txt)"

git push origin HEAD
```

### Step 9: Comment on the PR with a summary

Build the JSON body safely with Python to avoid breakage from quotes or newlines in the summary text:

```bash
TOKEN=$(printf '%s' "$GITEA_TOKEN" | tr -d '\r\n ')
python3 -c "
import json, urllib.request
summary = '''Fixes applied for CI failures:
- <describe what you fixed>

Failures addressed:
$(cat /tmp/fixpr_failure_summary.txt)'''
body = json.dumps({'body': summary})
req = urllib.request.Request(
    'BASE_URL/api/v1/repos/OWNER/REPO/issues/PR_NUMBER/comments',
    data=body.encode(),
    headers={'Authorization': 'token $(printf '%s' "\$GITEA_TOKEN" | tr -d '\r\n ')', 'Content-Type': 'application/json'},
    method='POST'
)
urllib.request.urlopen(req)
print('Comment posted.')
"
```

Or equivalently with curl and a temp file (simpler for multiline bodies):

```bash
TOKEN=$(printf '%s' "$GITEA_TOKEN" | tr -d '\r\n ')
python3 -c "
import json
summary = open('/tmp/fixpr_failure_summary.txt').read()
print(json.dumps({'body': 'CI fix applied.\n\n' + summary}))
" > /tmp/fixpr_comment.json

curl -s -X POST 'BASE_URL/api/v1/repos/OWNER/REPO/issues/PR_NUMBER/comments' \
  -H "Authorization: token $TOKEN" \
  -H "Content-Type: application/json" \
  -d @/tmp/fixpr_comment.json
```

---

## Tips

- **Check if you're already in the right repo** before cloning — `git remote get-url origin` may already point to the same Gitea repo. If so, just checkout the branch.
- **Parallel fetching** is essential — always batch the initial requests so you get PR data, statuses, and runs in one round of I/O.
- **Artifacts often contain the clearest failure info** — a `test-results.xml` or `lint-report.json` from an artifact is more actionable than a truncated log line.
- **If checks are still pending**, wait a moment and re-fetch; don't attempt to fix something that hasn't finished running.
- **If the failure is in a dependency or CI config** (not fixable code), explain this clearly to the user instead of making incorrect source edits.
