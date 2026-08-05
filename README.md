# Project Tools - Claude Code Plugin

A Claude Code plugin providing skills for interacting with Gitea and OpenProject APIs.

## Skills Included

### gitea-pr

Interact with Gitea pull requests, preferring the `tea` CLI and falling back to
direct REST API calls. Supports:

- Creating pull requests, including drafts
- Reviewing PR code changes
- Adding comments, reviews, and attachments
- Approving or requesting changes
- Inspecting CI results across both commit statuses and Gitea Actions
- Diagnosing and fixing CI failures (formerly the separate `fix-pr` skill)

Ships `scripts/pr_checks.py`, which summarises every check on a PR in one pass:

```bash
python3 skills/gitea-pr/scripts/pr_checks.py <owner/repo> <pr>
```

### openproject

Interact with OpenProject API v3 for work package management. Supports:

- Viewing work packages
- Creating new work packages
- Updating existing work packages
- Listing work packages by project

## Installation

Add the marketplace and install the plugin:

```
/plugin marketplace add https://github.com/erannave/project-tools.git
/plugin install project-tools
```

Then restart Claude Code to load the plugin.

## Configuration

Both skills require environment variables to be set before use.

### Gitea

#### Recommended: install `tea`

The [Gitea CLI](https://gitea.com/gitea/tea) is the preferred transport. It stores
the token in `~/.config/tea/config.yml` and derives `owner/repo` from the git
remote, which removes the two most common sources of failure — a missing or
misnamed environment variable, and a mistyped repo.

```bash
tea login add --name myinstance --url https://gitea.example.com --token <token>
```

The plugin works without `tea` and falls back to `curl` automatically.

#### Environment variables (fallback path)

```bash
export GITEA_ACCESS_TOKEN="your-personal-access-token"
```

`GITEA_TOKEN` and `GITEA_API_TOKEN` are also accepted, in that order of
preference, but `GITEA_ACCESS_TOKEN` is checked first. You can also put it in a
`.env` file in the working directory.

The Gitea base URL is automatically derived from the PR URL you provide or from `git remote get-url origin`.

To get your API token:
1. Log into your Gitea instance
2. Go to Settings → Applications
3. Generate a token with `write:repository`, `write:issue`, `read:organization`,
   and `read:user`

Modern Gitea uses `<read|write>:<category>` scopes, not the old GitHub-style
`repo`. Add `read:admin` / `write:user` only if you need admin-level reads.

### OpenProject

```bash
export OPENPROJECT_URL="https://your-instance.openproject.com"
export OPENPROJECT_API_KEY="your-api-key-here"
```

To get your API key:
1. Log into your OpenProject instance
2. Go to My Account → Access tokens
3. Create a new API token

Add these exports to your `~/.bashrc` or `~/.zshrc` to make them permanent.
