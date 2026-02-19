# AI Chief of Staff (`cos`) - Architecture

## Overview

`cos` is a CLI-first, local-first AI agent that acts as a Chief of Staff for a VP of Data Science who juggles multiple email accounts, calendars, and task streams across day job, startup advisory, and VC advisory contexts.

## System Architecture

```
            cos briefing daily
                    |
             +------v------+
             | ROUTER       |  (Haiku - cheap, fast)
             | Classify     |
             | Fan out      |
             +------+------+
                    |
       +------------+------------+
       |            |            |
  +----v----+  +----v----+  +---v-----+
  | COMMS   |  | SCHED   |  | TRACKER |  (Sonnet - balanced)
  | Agent   |  | Agent   |  | Agent   |
  +----+----+  +----+----+  +---+-----+
       |            |            |
       +------------+------------+
                    |
             +------v------+
             | JUDGE        |  (Sonnet/Opus - synthesis)
             | Merge        |
             | Prioritize   |
             | Format       |
             +------+------+
                    |
             +------v------+
             | APPROVAL     |  (Human reviews)
             | HOOK         |
             +--------------+
```

**Model tiers**: Haiku for routing, Sonnet for worker agents, Sonnet/Opus for judge, Gemini Flash for bulk summarization.

## Agent Design

### BaseAgent
All agents share a common interface: `AgentInput` -> `AgentOutput`. Each agent:
- Receives structured input with context and data
- Calls an LLM with a system prompt specific to its role
- Returns structured output with results and metadata (tokens, cost)

### Agent Types
- **Router**: Intent classification, fan-out to worker agents (Haiku)
- **Comms**: Email triage, drafting, priority classification (Sonnet)
- **Scheduler**: Calendar analysis, conflict detection, focus time (Sonnet)
- **Tracker**: Task aggregation from Asana + GitHub (Sonnet)
- **Briefer**: Cross-domain briefing synthesis (Sonnet)
- **Judge**: Multi-agent output synthesis and prioritization (Sonnet/Opus)

## Memory System: Cognee

Uses [cognee](https://docs.cognee.ai) for knowledge management — combines vector search + knowledge graphs + relational metadata.

### Why Cognee
- **Knowledge graphs**: Entities and relationships (people, projects, decisions) are explicitly modeled
- **13 search modes**: Graph traversal, hybrid retrieval, temporal, chain-of-thought reasoning
- **Local-first**: SQLite + LanceDB (vector) + Kuzu (graph) — zero external services
- **Memory consolidation**: Built-in `memify()` for episodic memory patterns

### Datasets
- **emails** — sender, subject, body, account, priority, thread
- **meetings** — title, attendees, date, calendar, notes, action items
- **tasks** — title, source (asana/github), project, status, assignee, due
- **decisions** — date, context, decision, rationale, participants
- **people** — name, email, org, relationship, last interaction
- **notes** — Apple Notes content, synced periodically

## Integrations

| Integration | Purpose | Auth |
|-------------|---------|------|
| Gmail | Email read/draft/send (multi-account) | Google OAuth |
| Google Calendar | Event read, conflict detection | Google OAuth |
| GitHub | PRs, issues, CI status | PAT via keyring |
| Slack | Channel summaries, mentions | OAuth token |
| Asana | Task management | PAT via keyring |
| Apple Notes | Quick capture from iOS/Mac | AppleScript (local) |
| Google Chat | VC workspace comms | Google OAuth |
| Google Docs/Sheets | Document read access | Google OAuth |

## Cross-Device Sync

### Config + Code: GitHub
- This repo is source of truth for code and config
- `~/.cos/config.yaml` symlinked from repo's `configs/` directory

### Memory + Data: iCloud Drive
- Path: `~/Library/Mobile Documents/com~apple~CloudDocs/cos-data/`
- Contains: SQLite DB, LanceDB files, Kuzu graph files
- iCloud handles transparent sync between machines

### Notes: Apple Notes
- Auto-syncs via iCloud
- Reads notes tagged `#cos` or in "Chief of Staff" folder

## Configuration

Multi-context YAML config at `~/.cos/config.yaml`. Secrets stored in macOS Keychain via `keyring`.

```yaml
active_context: day_job

contexts:
  day_job:
    label: "VP Data Science"
    email_accounts: [{id: work, type: google, address: ...}]
    calendars: [{id: work_cal, type: google, ...}]
    integrations:
      github: {org: ..., repos: [...]}
      slack: {workspace: ..., channels: [...]}
      asana: {workspace_gid: ..., projects: [...]}
    priorities: ["Direct report escalations", "Production incidents"]

  advisory:
    label: "Startup Advisor"
    # ...

  vc:
    label: "VC Advisor"
    # ...

sync:
  memory_path: ~/Library/Mobile Documents/com~apple~CloudDocs/cos-data/
  apple_notes:
    enabled: true
    folder: "Chief of Staff"

models:
  router: {provider: anthropic, model: claude-haiku-4-5}
  worker: {provider: anthropic, model: claude-sonnet-4-6}
  judge: {provider: anthropic, model: claude-sonnet-4-6}
  judge_strategic: {provider: anthropic, model: claude-opus-4-6}
  summarizer: {provider: google, model: gemini-2.0-flash}
```

## Package Structure

```
src/cos/
  __init__.py
  __main__.py
  cli/
    app.py            Root Typer app, registers all sub-commands
    briefing.py       `cos briefing` command group
    config_cmd.py     `cos config` command group
    notes.py          `cos notes` command group
    status.py         `cos status` command group
    formatters.py     Rich console helpers (print_briefing, print_health_table, etc.)
  agents/
    base.py           AgentInput / AgentOutput / BaseAgent ABC
    briefer.py        BriefingAgent — synthesizes email + calendar into morning briefing
    router.py         RouterAgent stub (Phase 2)
    comms.py          CommsAgent stub (Phase 2)
    scheduler.py      SchedulerAgent stub (Phase 2)
    tracker.py        TrackerAgent stub (Phase 3)
    judge.py          JudgeAgent stub (Phase 2/3)
  config/
    settings.py       AppConfig, ContextConfig, and all sub-models; load_config / save_config
    contexts.py       list_contexts, switch_context, get_all_email_accounts helpers
    secrets.py        Keychain wrappers via keyring (store/get/delete credential)
  core/
    errors.py         Exception hierarchy (CosError, AuthError, AgentError, ...)
    types.py          Shared Pydantic models (EmailMessage, CalendarEvent, Note, Briefing, ...)
    logging.py        structlog setup
    hooks.py          require_approval() human-in-the-loop prompt
  integrations/
    registry.py       IntegrationRegistry + IntegrationHealth; global registry singleton
    apple_notes.py    AppleNotesClient (AppleScript via osascript)
    google/
      auth.py         get_credentials, run_oauth_flow, keychain token storage
      gmail.py        GmailClient — unread email fetch
      gcal.py         GCalClient — today's events fetch
      gchat.py        Google Chat stub (Phase 3)
      gdocs.py        Google Docs stub (Phase 3)
    github.py         GitHub integration stub (Phase 2)
    slack.py          Slack integration stub (Phase 2)
    asana.py          Asana integration stub (Phase 3)
  memory/
    engine.py         MemoryEngine — cognee add / cognify / search / memify / reset
    datasets.py       Dataset name constants (emails, meetings, tasks, decisions, people, notes)
    sync.py           iCloud path resolution and sync health checks
  models/
    providers.py      call_anthropic / call_google — raw LLM wrappers returning LLMResponse
    router.py         call_worker / call_router / call_judge — config-driven dispatch
    budget.py         estimate_cost, UsageTracker, MODEL_COSTS table
```

## CLI Commands

### Implemented (Phase 1)

```
cos briefing daily              Generate today's morning briefing
cos briefing daily --dry-run    Show data that would be fetched, no LLM call
cos briefing daily --context <name>

cos notes list                  List notes from the configured Apple Notes folder
cos notes search <query>        Search notes by content

cos config init                 Create config and run Google OAuth flow
cos config show                 Print current config as YAML
cos config contexts             List all configured contexts
cos config test                 Health-check all registered integrations

cos status health               Check integration and memory health
cos status memory               Show memory store path and iCloud status
```

**Global flags**: `--verbose / -v`, `--dry-run`, `--cost-report` (briefing only)

### Planned (Phase 2+)

```
cos triage [inbox|draft <id>|send <id>]      # Email triage & response
cos calendar [today|week|conflicts|focus]    # Schedule management
cos tasks [list|blockers|priorities|sync]    # Task aggregation
cos ask <question>                           # Freeform RAG query
cos briefing weekly                          # Weekly briefing
cos briefing prep <meeting>                  # Meeting prep briefing
```

## Key Dependencies

- **CLI**: typer, rich
- **LLM**: anthropic, google-genai
- **Async**: anyio, httpx
- **Config**: pydantic, pydantic-settings, pyyaml
- **Memory**: cognee
- **Google APIs**: google-auth, google-auth-oauthlib, google-api-python-client
- **GitHub**: pygithub
- **Secrets**: keyring
- **Logging**: structlog

No LangChain/LlamaIndex — direct SDK usage for auditability and control.

## Phased Rollout

### Phase 1: MVP - "Morning Briefing"
Single Google account, `cos briefing daily` end-to-end. Config, Gmail, Calendar, Cognee, single briefing agent, CLI with Rich output, Apple Notes reader, iCloud sync.

### Phase 2: "Multi-Context Triage"
Multi-context config, multi-account Gmail, router + judge agents, email drafting with approval, GitHub + Slack, budget tracking.

### Phase 3: "Full Chief of Staff"
Asana, Google Chat/Docs, tracker + briefer agents, weekly briefings, meeting prep, memify(), freeform RAG, cost dashboard.
