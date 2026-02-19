# cos — AI Chief of Staff

A CLI-first AI agent for morning briefings, email triage, and schedule management. Designed for a single user juggling multiple roles across one Google account.

---

## Prerequisites

- Python 3.12+
- macOS (Apple Notes integration requires AppleScript)
- A Google Cloud project with the Gmail and Google Calendar APIs enabled
- An Anthropic API key (`ANTHROPIC_API_KEY`)
- Optionally a Google AI API key (`GOOGLE_API_KEY`) for the Gemini summarizer model

---

## Quick Start

### 1. Install

```bash
# From the repo root
pip install -e .
```

This installs the `cos` command via the entry point defined in `pyproject.toml`.

### 2. Set up Google OAuth

Download your OAuth client credentials from Google Cloud Console:

1. Go to [console.cloud.google.com](https://console.cloud.google.com) > APIs & Services > Credentials
2. Create an OAuth 2.0 Client ID (type: Desktop app)
3. Download the JSON file and save it as `~/.cos/client_secret.json`

Then run the initialization command:

```bash
cos config init
```

This creates a default `~/.cos/config.yaml` and runs the browser OAuth flow to store credentials in the macOS Keychain.

### 3. Run your first briefing

```bash
cos briefing daily
```

Use `--cost-report` to see token usage and estimated cost, and `--dry-run` to verify which data sources are reachable without calling any LLM.

---

## CLI Command Reference

```
cos briefing daily              Generate today's morning briefing
cos briefing daily --dry-run    Show data that would be fetched, no LLM call
cos briefing daily --context <name>   Use a specific context

cos notes list                  List notes from the configured Apple Notes folder
cos notes search <query>        Search notes by content

cos config init                 Create config and run Google OAuth flow
cos config show                 Print current config as YAML
cos config contexts             List all configured contexts
cos config test                 Health-check all registered integrations

cos status health               Check integration and memory health
cos status memory               Show memory store path and iCloud status
```

Global flags available on most commands:
- `--verbose / -v` — enable structured debug logging
- `--cost-report` — print token counts and estimated USD cost (briefing only)
- `--dry-run` — skip LLM calls and show what would happen

---

## Configuration

Config lives at `~/.cos/config.yaml`. Run `cos config init` to create a starter file, or copy `configs/example.yaml` from this repo.

The config is a YAML file with one or more named **contexts**. A context groups an email account, a calendar, and optional third-party integrations (GitHub, Slack, Asana) that share a role/identity. The `active_context` key controls which context is used by default.

Switch context for a single command:

```bash
cos briefing daily --context advisory
```

Secrets (Google OAuth tokens, API keys) are never stored in the config file. They live in the macOS Keychain under the service name `cos-chief-of-staff`, managed automatically by `cos config init` and the `keyring` library.

### Config file location

| Path | Purpose |
|------|---------|
| `~/.cos/config.yaml` | Main configuration |
| `~/.cos/client_secret.json` | Google OAuth client credentials (you provide this) |

### Memory / data store

By default, the knowledge graph and vector store are written to iCloud Drive so they sync across machines:

```
~/Library/Mobile Documents/com~apple~CloudDocs/cos-data/
```

You can override this path with `sync.memory_path` in your config. Check status with `cos status memory`.

---

## Development

### Run tests

```bash
pytest
```

Tests live in `tests/` and use `pytest-asyncio` for async test cases.

### Lint and format

```bash
ruff check src/ tests/
ruff format src/ tests/
```

### Project layout

```
src/cos/
  cli/          Typer command groups (app, briefing, config, notes, status)
  agents/       LLM agent classes (base, briefer, router, comms, scheduler, tracker, judge)
  config/       Settings, secrets, context management
  core/         Errors, types, logging, approval hooks
  integrations/ Google (Gmail, Calendar, OAuth), Apple Notes, GitHub, Slack, Asana
  memory/       Cognee engine wrapper, dataset names, iCloud sync helpers
  models/       LLM providers (Anthropic, Google), model router, cost estimation
```

See [docs/architecture.md](docs/architecture.md) for a detailed description of the agent pipeline, memory system, and multi-context design.
