# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is **project-tools**, a Claude Code plugin that provides skills for interacting with:
- **Gitea** - Pull request management via REST API
- **OpenProject** - Work package management via API v3

## Repository Structure

```
.claude-plugin/
  plugin.json        # Plugin metadata and configuration
  marketplace.json   # Marketplace registration for plugin discovery
skills/
  gitea-pr/
    SKILL.md         # Main skill definition for Gitea PR operations
    references/
      gitea-api.md   # Complete Gitea API reference documentation
  openproject/
    SKILL.md         # Skill definition for OpenProject work packages
```

## Plugin Architecture

Skills are defined in SKILL.md files with YAML frontmatter containing:
- `name`: Skill identifier
- `description`: Trigger conditions for when the skill should activate

The skill body contains markdown documentation that guides Claude on how to perform operations (prerequisites, API calls, workflows).

## Adding or Modifying Skills

1. Create/edit `skills/<skill-name>/SKILL.md`
2. Include YAML frontmatter with `name` and `description` fields
3. Document prerequisites (environment variables), API endpoints, and workflows
4. For API-heavy skills, consider adding a `references/` subdirectory with detailed API docs

## Environment Variables Required by Skills

**Gitea:**
- `GITEA_URL` - Base URL of the Gitea instance
- `GITEA_TOKEN` - Personal access token with repo scope

**OpenProject:**
- `OPENPROJECT_URL` - Base URL of the OpenProject instance
- `OPENPROJECT_API_KEY` - API token from My Account > Access tokens

## Installation (for users)

```bash
/plugin marketplace add https://github.com/erannave/project-tools.git
/plugin install project-tools
```
