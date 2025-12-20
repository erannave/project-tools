# Project Tools - Claude Code Plugin

A Claude Code plugin providing skills for interacting with Gitea, OpenProject, and Hoppscotch APIs.

## Skills Included

### gitea-pr

Interact with Gitea pull requests via direct REST API calls. Supports:

- Creating pull requests
- Reviewing PR code changes
- Adding comments and reviews
- Approving or requesting changes

### openproject

Interact with OpenProject API v3 for work package management. Supports:

- Viewing work packages
- Creating new work packages
- Updating existing work packages
- Listing work packages by project

### hoppscotch

Run API tests using the Hoppscotch CLI. Supports:

- Running local and cloud collections
- Environment configuration
- JUnit XML test reports for CI/CD
- Data-driven testing with CSV iterations

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

```bash
export GITEA_URL="https://your-gitea-instance.com"
export GITEA_TOKEN="your-personal-access-token"
```

To get your API token:
1. Log into your Gitea instance
2. Go to Settings → Applications
3. Generate a new token with `repo` scope

### OpenProject

```bash
export OPENPROJECT_URL="https://your-instance.openproject.com"
export OPENPROJECT_API_KEY="your-api-key-here"
```

To get your API key:
1. Log into your OpenProject instance
2. Go to My Account → Access tokens
3. Create a new API token

### Hoppscotch

Requires Node.js v22+ and the Hoppscotch CLI:

```bash
npm i -g @hoppscotch/cli
```

For cloud collections, you'll need a personal access token from your Hoppscotch account.

Add these exports to your `~/.bashrc` or `~/.zshrc` to make them permanent.
