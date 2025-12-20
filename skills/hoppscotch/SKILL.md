---
name: hoppscotch
description: |
  Hoppscotch CLI for API testing and collection management. Use this skill when:
  - User mentions "Hoppscotch", "hopp", or API collection testing
  - Running API tests from collection files
  - Managing API request collections with environments
  - Generating test reports (JUnit XML) for CI/CD pipelines
  - User wants to iterate over test data with CSV files
  Handles: running collections, environment configuration, test reports, and iterations.
---

# Hoppscotch CLI

## Prerequisites

```bash
# Check if hopp is installed
which hopp || echo "NOT INSTALLED"
```

If NOT INSTALLED:
```bash
npm i -g @hoppscotch/cli
```

Requires Node.js v22+ (v20 supported until April 2026).

## Core Command: `hopp test`

Run API tests against collections. Processes requests sequentially, validates responses using embedded test scripts.

### Basic Usage

```bash
# Run local collection
hopp test collection.json

# With environment file
hopp test -e environment.json collection.json

# With delay between requests (ms)
hopp test -d 1000 collection.json

# Combined
hopp test -e env.json -d 500 collection.json
```

### Remote Collections (Hoppscotch Cloud)

```bash
# Cloud collection with token
hopp test <collection_id> --token <access_token>

# Self-hosted instance
hopp test <collection_id> --token <token> --server https://hoppscotch.example.com
```

### Test Reports

```bash
# Generate JUnit XML report
hopp test collection.json --reporter-junit report.xml

# With path
hopp test collection.json --reporter-junit ./reports/api-tests.xml
```

### Iterations with Data

```bash
# Run collection N times
hopp test collection.json --iteration-count 3

# With CSV data (each row = one iteration)
hopp test collection.json --iteration-count 3 --iteration-data data.csv
```

## Options Reference

| Option | Description |
|--------|-------------|
| `-e, --env <file>` | Environment file (JSON) or ID |
| `-d, --delay <ms>` | Delay between requests |
| `--token <token>` | Personal access token for cloud |
| `--server <url>` | Self-hosted instance URL |
| `--reporter-junit [path]` | Generate JUnit XML report |
| `--iteration-count <n>` | Run collection N times |
| `--iteration-data <csv>` | CSV file with iteration variables |
| `--legacy-sandbox` | Disable experimental scripting sandbox |
| `-h` | Show help |
| `-v` | Show version |

## Environment File Formats

### Standard Format (Recommended)

```json
{
  "name": "production",
  "variables": [
    {"key": "base_url", "value": "https://api.example.com"},
    {"key": "auth_token", "value": "Bearer xyz"}
  ]
}
```

### Legacy Format

```json
{
  "base_url": "https://api.example.com",
  "auth_token": "Bearer xyz"
}
```

## Iteration Data (CSV)

```csv
user_id,email,expected_status
1,user1@example.com,200
2,user2@example.com,200
3,invalid,400
```

Each row replaces environment variables for that iteration.

## Exit Codes

- `0` - All tests passed
- Non-zero - One or more tests failed

## Common Workflows

### CI/CD Pipeline

```bash
# Run tests and generate report for CI
hopp test -e ci-env.json collection.json --reporter-junit test-results.xml
```

### Load Testing with Iterations

```bash
# Run 10 iterations with 500ms delay
hopp test -e env.json -d 500 --iteration-count 10 collection.json
```

### Data-Driven Testing

```bash
# Test with different user scenarios
hopp test collection.json --iteration-data users.csv --reporter-junit results.xml
```
