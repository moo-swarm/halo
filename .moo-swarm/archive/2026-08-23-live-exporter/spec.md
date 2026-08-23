# Spec — Live exporter: make the frozen sections live

**Feature path:** `workspaces/_align-rail_/projects/halo/.moo-swarm/features/2026-08-23-live-exporter/`
**Date:** 2026-08-23/24 · **Author:** requirements-eliciting (from coordinator brief + research `2026-08-23-ideas-research.md`)
**Status:** draft → ready for architecture-planning

---

## 1. Problem

The hourly exporter (`scripts/moo-export-data.py`) is an *enricher*, not an exporter. It refreshes
`updated_at` every hour, so the global badge reads green "updated N minutes ago", while five of seven
dashboard sections display June–July seed data:

| Section | Seed field | Live source available on host |
|---|---|---|
| Issues & PRs | `.issues[]`, `.prs[]` | `gh api` over moo-swarm org repos |
| Pipeline Status | `.pipeline[].last_run` (2026-07-02) | `.moo-swarm/features/*/handoff-log.md` tails |
| Regular Tasks (cron) | `.cron_jobs[]` (2026-06/07) | `cron_jobs` table, `/home/lex/.openclaw/state/openclaw.sqlite` |
| Agent Health | `.agents[].status/last_active/sessions_24h` | `~/.openclaw/agents/<name>/sessions/` file mtimes (metadata only) |
| Active Projects | half-live already | stays; `open_issues` now derived from the same issues fetch |

Research bug B5 ("freshness signal is honest about the file, dishonest about the content") is this
feature's core target. **Spending/cost panels are OUT of scope** — privacy decision F2 unresolved.

## 2. Decisions (carried into architecture)

- **D1 — Cron from SQLite, whitelisted columns only.** The `cron_jobs` table contains private payload
  (`payload_message`, `job_json`, `state_json`) and PII (`delivery_to` = Telegram chat ids). Export a
  fixed whitelist of columns, never a row dump. Open the DB with `file:…?mode=ro`.
  Verified live schema (5 jobs): `name, enabled, schedule_kind ('cron'|'every'), schedule_expr,
  schedule_tz, every_ms, last_run_at_ms, next_run_at_ms, last_run_status ('ok'|'error'),
  last_error, consecutive_errors, last_duration_ms, agent_id`.
- **D2 — Pipeline from handoff-log tails.** Scan `<project>/.moo-swarm/features/*/handoff-log.md`,
  take each file's latest `## HH:MM [worker] [context] [status]` header line; aggregate per worker
  agent: `agent`, `role` (static worker→role map), `status` (done/pass→`pass`, fail→`fail`,
  blocked→`idle`, recent progress→`running`), `last_run` (entry date+HH:MM → ISO, UTC assumed).
  Preserves existing pipeline[] semantics (stages by agent role) with zero API cost.
  Alternative considered and deferred: GitHub Actions runs per repo.
- **D3 — Agents from session-file mtimes only (metadata, never content).**
  `~/.openclaw/agents/*/sessions/*.jsonl` mtimes give `last_active` (max mtime) and `sessions_24h`
  (distinct files touched in trailing 24h). Roster = union of seed agents[] and discovered dirs;
  static `AGENT_META` map supplies emoji/role, unknown dirs get neutral defaults.
  **Honest gaps flagged in output, not invented:** `tokens_24h` not derivable without transcript
  parsing → export as `null`; no running/busy signal exists → status derives from mtime age only
  (`active` <60 min, `idle` <7 d, `dormant` ≥7 d). Investigated and rejected as ground truth:
  `task_runs` (85 rows, ~all attributed to 'moo' cron runs), `acp_sessions` (0 rows),
  `subagent_runs` (0 rows), `cron_run_logs.session_key` (mostly null).
- **D4 — Failure honesty via additive maps.** New optional top-level keys:
  - `sections_updated_at`: `{projects, pipeline, cron_jobs, issues, prs, agents}` → ISO timestamp
    of the *source fetch*, per section.
  - `source_errors`: `{<section>: {error: str, at: ISO}}` present only for sources that failed this run.
  On failure the section keeps its previous values and its old timestamp (truthful staleness); the
  other sections still update; global `updated_at` always advances (it timestamps the *file*).
- **D5 — Repo enumeration dynamic.** One paging call `gh api orgs/moo-swarm/repos?per_page=100`
  gives the scan list; config denylist excludes non-project repos. Budget ≈ 1 + 2·N calls/run
  (17 repos today ⇒ ~35/hour « 5000/hr authenticated).

## 3. Acceptance criteria

### Sources & extraction

- **AC1.** `fetch_issues_and_prs()` enumerates org repos via one paged `gh api orgs/moo-swarm/repos`
  call, then per repo fetches open issues (excluding items with a `pull_request` key) and open PRs.
  Each exported issue has `project, number, title, labels[], created_at, url`; each PR has
  `project, number, title, author, status ('open'|'draft'), created_at, url`. Counts capped
  (default 50 issues / 50 PRs overall, newest first) to bound JSON size.
- **AC2.** `extract_cron_jobs(db_path)` opens the SQLite DB read-only (`mode=ro` URI) and returns one
  entry per job: `name`, `schedule_human` (built from `schedule_expr` + `schedule_tz`, or `every_ms`
  rendered human-readable), `schedule` (raw expr/every), `last_run` (ms→ISO 8601 Z), `status`
  (`'disabled'` when `enabled=0`; `'ok'` when `last_run_status='ok'`; `'fail'` otherwise),
  plus new optional fields `next_run` (ISO) and `consecutive_errors` (int).
- **AC3.** No key in exported `cron_jobs` may equal or contain any of: `payload`, `delivery_to`,
  `delivery_channel`, `session_key`, `job_json`, `state_json`, `description`, `last_error`
  (free-text error could carry paths). A guard test asserts these substrings never appear anywhere
  in the serialized output JSON.
- **AC4.** `extract_pipeline(project_dirs)` scans each project's
  `.moo-swarm/features/*/handoff-log.md`, parses entry header lines
  (`## HH:MM [worker] … [context] …`), and emits ≤1 pipeline entry per known worker agent with
  `agent, emoji, role, status ∈ {pass, fail, running, idle}, last_run` (ISO). Malformed or missing
  logs are skipped without failing the run; workers with no log activity in 30 d fall back to
  `idle` with their last recorded `last_run`.
- **AC5.** `extract_agents(agents_dir)` lists `~/.openclaw/agents/*/sessions/` and returns per-agent:
  `name`, `emoji`+`role` from `AGENT_META` (neutral fallbacks for unmapped dirs),
  `last_active` (max session-file mtime, ISO), `sessions_24h` (count of files with mtime within
  trailing 24 h), `status` derived from mtime age (active/idle/dormant per D3), `tokens_24h: null`,
  and the existing enrichment-defaulted `budget_daily` block (unchanged behaviour).
  Missing/unreadable agent dirs are skipped silently.
- **AC6.** Projects section keeps current filesystem logic (specs, owner inference) but `open_issues`
  is set from AC1's fetched counts instead of a separate per-repo integer call.

### Schema discipline

- **AC7.** Output remains schema-v2 compatible: all `SCHEMA.required` keys
  (`updated_at, projects, pipeline, issues, prs, cron_jobs, agents`) present on every successful run;
  `schema_version` stays `"2.0"`; all additions (`sections_updated_at`, `source_errors`,
  cron `next_run`/`consecutive_errors`) are optional fields absent-safe for today's dashboard.js.
- **AC8.** A compat test runs `main()` against a fixture swarm.json (seed-shaped, temp dir) and
  asserts the rendered result satisfies SCHEMA.required and that pre-existing unknown user fields
  (e.g. `custom: "keep"`) survive.

### Failure honesty

- **AC9.** Every successful source fetch stamps its section into `sections_updated_at` with the real
  fetch time; global `updated_at` remains the file-generation time.
- **AC10.** When a source fails (gh non-zero/timeout, SQLite missing/corrupt, agents dir absent),
  the exporter records `source_errors[<section>] = {error, at}`, leaves that section's data and its
  `sections_updated_at` entry untouched (retaining last-good values from the input file), still
  writes the file, and exits 0 (partial success is success; the truth lives in the maps).
- **AC11.** A legitimately empty source (zero open issues/PRs) exports empty arrays with a fresh
  `sections_updated_at` — emptiness is success, never conflated with failure.
- **AC12.** Dashboard renders per-section freshness: each section shows a stale marker when its
  `sections_updated_at[<section>]` is older than 120 min or listed in `source_errors`; sections keep
  rendering their (possibly old) data. Absent `sections_updated_at` (old file) behaves exactly as
  today — no crash, global badge unchanged.
- **AC13.** Smoke test (`tests/smoke.test.js`, node --test, stub-DOM pattern) extended: fixture with
  stale `sections_updated_at` + one `source_errors` entry produces the stale marker on exactly those
  sections; fixture without the maps produces none.

### Secrets & safety

- **AC14.** No tokens/secrets in output or logs: gh invoked read-only through existing credential
  helper; SQLite opened `mode=ro`; exporter never writes outside `data/swarm.json` (plus git push of
  that file via existing wrapper).
- **AC15.** Guard test (extends AC3) greps serialized output for forbidden substrings
  (`payload`, `delivery_to`, `telegram:`, token-like patterns) — must find none.

### Tests & CI

- **AC16.** `tests/test_export_data.py` extended (stdlib unittest, temp-dir isolation, importlib
  load — existing patterns): fixture-based tests for every new extraction function —
  cron mapping incl. disabled/error/ms→ISO (temp SQLite DB built in setUp), readonly-open assertion,
  agents scan with `os.utime`-controlled mtimes + unknown-dir fallback, gh mapping/filtering/caps
  with mocked `subprocess.run`, handoff-tail parsing incl. malformed-log tolerance, full-main
  schema-compat + secrets guard (AC3/AC8/AC15).
- **AC17.** Existing tests keep passing; `node --test tests/` and `python3 -m unittest` both green;
  lint workflow unchanged (`py_compile` covers new module code automatically).

### Ops

- **AC18.** External paths configurable via env with current defaults:
  `HALO_OPENCLAW_DB=/home/lex/.openclaw/state/openclaw.sqlite`,
  `HALO_AGENTS_DIR=/home/lex/.openclaw/agents`, `HALO_PROJECTS_DIR=…/_align-rail_/projects`,
  `HALO_REPO_DENYLIST` (comma-separated; default excludes `.github`).
- **AC19.** Total `gh api` calls per hourly run documented and asserted ≤ 40 (comment + test-time
  counter on the mocked calls).
- **AC20.** README exporter section updated: per-section source table, staleness contract
  (what green/amber/red/stale mean per section vs globally), env vars, rate-limit note, "what you
  see when a source fails".

## 4. Architecture & test implications (for architecture-planning)

- **Dependencies:** stdlib-only Python (sqlite3, json, subprocess, pathlib, os, re) — preserves the
  no-pip host constraint (tech-plan DR-2 precedent). `gh` CLI assumed authenticated (verified).
- **Module shape:** extraction functions pure/injectable (path + runner params or module-level
  constants patched in tests, matching existing `DATA_FILE`/`PROJECTS_DIR` patch style). Suggest
  splitting `moo-export-data.py` into small functions per source with a `SOURCES` registry driving
  fetch → stamp → error-catch, so failure isolation (AC10) is structural, not ad-hoc if/else.
- **Storage/API surface:** reads openclaw.sqlite read-only (external system contract — gateway owns
  it; concurrent access expected, so short-lived connections, no locks). Writes only
  `data/swarm.json`. New public JSON surface: `sections_updated_at`, `source_errors`, cron
  `next_run`/`consecutive_errors` — consumed by dashboard.js and future badges/heartbeats.
- **Dashboard surface touched:** per-section freshness markers (AC12–13) — small, additive render +
  one helper; must pass the runtime smoke harness (P0 work already landed in `tests/smoke.test.js`).
- **Constraints:** host-cron runner required (SQLite + agents-dir live only on this host — a future
  GH-Actions runner would lose cron/agents sections; see Deferred). Rate budget AC19. Timestamps
  ms→UTC ISO consistently (`Z` suffix), handoff-log HH:MM treated as UTC (kit convention).
- **Test strategy:** extend the two existing suites only; fixtures over mocks where cheap (real temp
  SQLite, real temp trees), `mock.patch` for `subprocess.run` (gh). No new test frameworks.

## 5. Documentation implications (for Mokash)

README "Data & export" section rewrite per AC20: source table (section → source → refreshed),
per-section staleness semantics, env-var configuration, gh rate-limit note, failure behaviour
("a red/stale chip means that source failed; the rest of the page is still live"). Also note that
spending panels remain seeded pending privacy decision F2, so readers don't mistake them for live.

## 6. Open questions

1. **Agent roster presentation:** discovered dirs include `main`, `damavik`, `yaga` beyond the seed
   six. Fold `main` into `moo` (same operator session)? Show unmapped dirs with neutral emoji/role?
   *(Recommendation: show all discovered, neutral meta; fold decision to owner.)*
2. **Repo denylist contents:** default excludes `.github` only — should non-bus repos like
   `brain-runtime`, `team-identity` be scanned in Issues & PRs? *(Recommendation: scan everything
   public in the org; it is a public transparency page.)*
3. **Pipeline supplement:** should GitHub Actions run results also feed pipeline statuses later
   (badge_url/workflow_url currently point at Actions pages)? Deferred for now (D2 alternative).
4. **`sessions_24h` definition:** distinct transcript files touched (recommended) vs run-count from
   `task_runs` (rejected — cron-attributed noise). Confirm with owner if the number becomes public-facing.
5. **Disabled cron jobs:** shown with grey `disabled` status (recommended) or hidden?

## 7. Deferred decisions

Managed via `deferred.md` in this feature folder (defer.sh unavailable for non-`.tlk` feature paths —
entries recorded manually):

- **DEF-1 — Live spending/cost panels.** Blocked by privacy decision F2 (are real dollar/token figures
  publishable?). Revisit when F2 resolved; ccusage-style transcript parse or OpenRouter activity pull
  are the candidate sources. Cmok: implement nothing here for now.
- **DEF-2 — Cron heartbeat math (late/missed classification, uptime strips).** Groundwork ships in
  this feature (`next_run`, `consecutive_errors`); the healthchecks-style "on-time/late/missed"
  panel is a follow-up once real `next_run` history accumulates.
- **DEF-3 — GH-Actions export runner evaluation.** Would remove host dependency but lose SQLite +
  agents-dir sources; needs a decision before any runner migration.
- **DEF-4 — Shields.io badges + OG meta tags from swarm.json** (research C1/C4) — cheap follow-up
  once sections are live and trustworthy.
- **DEF-5 — Talaka `.tlk/features` projects.** Projects outside `_align-rail_` using talaka instead of
  `.moo-swarm` are invisible to the projects/pipeline scan; revisit if such projects appear.
