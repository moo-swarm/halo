# Spec: Halo Dashboard v1 — Moo Swarm Live Status

**Feature:** `dashboard-v1`
**Feature path:** `/home/lex/.openclaw/workspaces/_align-rail_/projects/halo/.moo-swarm/features/2026-07-03-dashboard-v1`
**Repository:** `github.com/moo-swarm/halo`
**Hosted at:** `moo-swarm.github.io/halo`

---

## 1. Purpose

Halo is a **public GitHub Pages dashboard** that shows the current state of the moo-swarm — active projects, pipeline status, issues, regular tasks, and spending. Think of it as the "mission control" for the swarm, visible to anyone who visits the URL.

## 2. Architecture

**Pattern:** Data pushed FROM Moo Swarm, NOT pulled by GitHub Actions.

The majority of data lives inside the Moo Swarm host (OpenClaw sessions, spending, cron jobs, project files). GitHub Actions can't reach it. Therefore:

```
Moo Swarm host (cron, hourly)
  │
  ├── moo-export-data.sh:
  │   ├── read swarm project files (_align-rail/projects/)
  │   ├── query OpenClaw internals (sessions, spending, cron/jobs.json)
  │   ├── fetch GitHub API for issues/PRs/stars (external data)
  │   └── generate data/swarm.json
  │
  └── git push to github.com/moo-swarm/halo (data/export branch, force-with-lease)
       │
       └── GitHub Pages auto-deploys from main branch
            │
            └── index.html renders data/swarm.json
                (vanilla JS, zero API calls at page load)
```

- **Push direction:** Moo Swarm → GitHub (via `gh` CLI + PAT on the host)
- **Frontend:** Pure HTML5 + CSS3 + vanilla JS. Chart.js for graphs (CDN)
- **No framework** — no React, Vue, build step
- **Zero external API calls at page-load** — everything is pre-baked JSON
- **Data age badge** displayed on each section (e.g. "updated 12 min ago")
- **No auth, no backend, no database** — fully static, fully public

### Data export runs as a Moo cron job

A new cron job `halo-data-export` (every hour) will:
1. Run `moo-export-data.sh` on the host
2. Generate `data/swarm.json` and push to the halo repo (`data/export` branch)
3. Trigger a fresh Pages deploy

**Export script pattern (from research):**
- Use `flock -n` for locking — prevents overlapping cron runs
- Force-push to a dedicated `data/export` branch (never `main`) via `--force-with-lease`
- Check `git status --porcelain` — skip commit/push if nothing changed (no-op guard)
- Retry transient push failures: 3 retries with exponential backoff (5s, 10s, 20s)
- Log structured entries with timestamps; separate error log
- Use `git worktree add` for a clean working directory per branch

## 3. Sections (must-have for v1)

### 3.1 Header — Swarm Identity

- Title: **Halo — Moo Swarm Status**
- Subtitle: "Live dashboard of the Moo swarm"
- Last-updated timestamp (from `data/swarm.json`)
- Link to `github.com/moo-swarm`

### 3.2 Active Projects

Shows **swarm projects** (from `_align_rail/PROJECTS.md` and project folders), NOT all GitHub repos. Repos are shown only if linked to a project.

| Column | Source |
|--------|--------|
| Project name | PROJECT.md |
| Description | PROJECT.md |
| Status (active/stalled/archived) | Inferred from feature folders + handoff logs |
| Last feature update | Latest feature folder date |
| Pipeline stage | Handoff log (last known stage) |

Display as a **table** with a **health indicator**:
- 🟢 Active (feature work in last 7d)
- 🟡 Stalled (no activity 7–30d)
- 🔴 Dormant (30d+ no activity)

Repo stats (stars, open issues) shown as secondary info when a repo URL is configured in PROJECT.md.

### 3.3 Pipeline Status

Show the **build chain** — visual flow rendered with **Mermaid.js** (v11, CDN):

```
flowchart LR
    Veles[🐍 Veles\nResearch] --> Moo[🐮 Moo\nRoute]
    Moo --> Cmok[🐉 Cmok\nBuild]
    Cmok --> Bagnik[🚨 Bagnik\nQA]
    Bagnik --> Zlydni[🏚️ Zlydni\nCommit]
```

Each node coloured by status: 🟢 pass, 🔴 fail, 🟡 running, ⚪ idle.

Each stage shows:
- ✅ Last passed / ❌ Last failed / ⏳ Running / ⚪ Idle (node colour)
- Agent emoji + name inline
- Timestamp of last run below the node
- shields.io badge for live status (`https://img.shields.io/github/actions/workflow/status/...`)

**Implementation:**
- Mermaid.js renders **programmatically** from pipeline data in `data/swarm.json`
- On page load: construct Mermaid definition string → call `mermaid.render('pipeline', definition)` → inject SVG into DOM
- Nodes styled by status via Mermaid `themeVariables`
- Dark mode support through Mermaid theme config
- **Fallback:** If Mermaid fails — plain HTML badge row with status indicators

Data source: handoff-log.md files across projects (extracted by export script), plus GitHub Actions status from `gh api` where repos have Actions.

**v1 approach:** Export script reads `.moo-swarm/features/*/handoff-log.md` for last known state. GitHub Actions status fetched via `gh api` for repos where it exists. Repos without Actions — show as ⚪ (no data).

### 3.4 Open Issues & PRs

**Top 10 open issues** across moo-swarm project repos:

| Issue | Project | Age | Labels |
|-------|---------|-----|--------|

**Top 5 open PRs:**

| PR | Project | Author | Status | Age |
|----|---------|--------|--------|-----|

Data from GitHub API (fetched by export script on the host via `gh api`). Filterable by project/label.

### 3.5 Regular Tasks (Cron Jobs)

A **schedule board** showing cron jobs and their last run status:

| Task | Schedule | Last Run | Status |
|------|----------|----------|--------|
| Self-improvement dispatch | 09:00 daily | 2026-07-03 09:00 | ✅ |
| Dream routine | 03:00 daily | 2026-07-03 03:00 | ✅ |
| QMD weekly digest | Sun 02:00 | 2026-06-29 | ✅ |
| Pipeline monitor | hourly | 2026-07-03 00:00 | ✅ |
| Halo data export | hourly | 2026-07-03 01:00 | ✅ |

Data exported by the same cron job — reads `/home/lex/.openclaw/cron/jobs.json` and its run history. **No manual updates.** The export script lives on the Moo Swarm host and has full access.

### 3.6 Spending & Usage

**OpenClaw API usage** — last 7 / 30 days:

| Metric | Value |
|--------|-------|
| Total tokens used (7d) | 1,234,567 |
| Estimated cost (7d) | $2.45 |
| API calls (7d) | 847 |
| Active agents (7d) | 6 / 8 |

**Chart:** Daily token usage — last 14 days (bar or line, Chart.js).

Data source: OpenClaw provider API or session logs. Moo's export script runs on the host and can query OpenClaw internals. If OpenClaw doesn't expose token usage directly, we may need agent instructions to track it.

**v1 approach:** export script queries whatever OpenClaw makes available. If data is unavailable — graceful "data pending" placeholder.

### 3.7 Agent Health

Per-agent status card:

```
┌──────────┬──────┬──────────┬──────────┐
│ Agent    │ Role │ Status   │ Last act │
├──────────┼──────┼──────────┼──────────┤
│ Moo 🐮   │ Route│ ✅ Active│ 2h ago   │
│ Veles 🐍 │ Res. │ ✅ Active│ 4h ago   │
│ Cmok 🐉  │ Build│ ⏳ Busy  │ 30m ago  │
│ Bagnik🚨 │ QA   │ ✅ Active│ 1h ago   │
│ ...      │      │          │          │
└──────────┴──────┴──────────┴──────────┘
```

Status inferred from last session timestamp (export script queries OpenClaw session list on the host). If the session list API doesn't expose last-active timestamps, we add agent instructions to log activity to a shared file.

## 4. Layout & UX

### Page layout (desktop — 3 columns):

```
┌─────────────────────────────────────────────┐
│  Halo — Moo Swarm Status  [updated: HH:MM] │
├──────────────┬──────────────┬───────────────┤
│ Active       │ Pipeline     │ Cron Jobs     │
│ Projects     │ Status       │ Schedule      │
│ [table]      │ [flowchart]  │ [table]       │
├──────────────┴──────────────┴───────────────┤
│ Open Issues & PRs                           │
│ [filterable table]                          │
├──────────────┬──────────────┐               │
│ Spending     │ Agent        │               │
│ & Usage      │ Health       │               │
│ [chart+table]│ [cards]      │               │
└──────────────┴──────────────┴───────────────┘
```

### Mobile — single column stack.

### Colour scheme — toggle, default follows system preference

- **System light:** white bg (#ffffff), slate-700 text, blue-600 accent (#2563eb)
- **System dark:** slate-900 bg (#0f172a), slate-100 text, blue-400 accent
- **CSS:** `prefers-color-scheme` media query + manual toggle button (🌙/☀️)
- **Toggle state** persisted in `localStorage`
- **Cards:** `bg-white` (light) / `bg-slate-800` (dark)
- **Status dots:** 🟢 #22c55e, 🟡 #eab308, 🔴 #ef4444
- **Toggle button** in the header, accessible

### Interactivity
- Clicking a project name → opens its repo/tree in new tab
- Clicking an issue/PR → opens GitHub in new tab
- Hover on chart → tooltip with exact values
- Filter issues by project / label (client-side JS)
- Theme toggle → immediate switch, persisted across visits

## 5. Acceptance Criteria

| # | Criterion | How to verify |
|---|-----------|---------------|
| 1 | Site loads at `moo-swarm.github.io/halo` | Open URL |
| 2 | Active Projects shows real swarm projects (not just GitHub repos) | Compare vs `_align_rail/PROJECTS.md` |
| 3 | Pipeline Status shows each stage with correct status per handoff logs + GHA | Cross-check against handoff-log.md files |
| 4 | Open Issues & PRs lists top items from all project repos | Manual spot-check on GitHub |
| 5 | Cron Jobs section shows correct schedule/last-run from `cron/jobs.json` | Compare against actual file on host |
| 6 | Spending section shows token/cost data (or graceful "data pending") | Visual check |
| 7 | Agent Health cards show each agent with status from OpenClaw | Match `sessions_list` output |
| 8 | Data freshness badge shows "updated X ago" | Check timestamp matches last cron run |
| 9 | Mobile layout stacks columns correctly | Viewport < 768px |
| 10 | Theme toggle works: follows system default, persists choice | Toggle, reload, toggle again |
| 11 | All links open in new tab with `rel="noopener"` | Inspect HTML |
| 12 | Zero external API calls at page load (pre-baked JSON only) | DevTools Network tab |
| 13 | New data appears within 1h of host changes (cron-driven) | Make change, wait for cron, reload |

## 6. Stretch Goals (nice-to-have, not v1)

- **Incident timeline** — when something broke and when it was fixed
- **Contributor activity** — who's been active recently
- **Search** — search across issues, projects, and tasks
- **RSS feed / Telegram bot integration** — daily digest from Halo data
- **Embeddable widgets** — embed a status card in other sites
- **Observable Framework** — richer data viz in a future version
- **`github-community-projects/org-metrics-dashboard`** pattern eval — our architecture already matches theirs; revisit if they release a major update

## 7. Open Questions

1. **Spending data from OpenClaw** — does OpenClaw expose token usage/cost via its API? Cmok: investigate OpenClaw provider API or session logs. If unavailable, add agent instructions to track usage. **Fallback: "data pending" placeholder for v1.**
2. **Agent last-active from OpenClaw** — can `sessions_list` or `session_status` provide last-active timestamps? Same approach: investigate, use if available, otherwise add agent logging instructions.
3. **What exactly counts as "spending"?** — OpenClaw model tokens only? GitHub Actions minutes? Storage? **v1: OpenClaw tokens only. Add GHA minutes and storage later.**
4. **Halo data export cron — where does it live?** — New cron job in `/home/lex/.openclaw/cron/jobs.json`, or a standalone script + systemd timer? **v1: new cron job on the Moo account.** Push to `data/export` branch (never `main`).
5. **Push mechanism — which identity?** — `gh` CLI with `${OPENCLAW_GITHUB_PAT}` from the host's `.env`. Same PAT as the org access. **Confirm: does the PAT have push access to `moo-swarm/halo`?** (Yes — it's an org token with `repo` scope.)

## 8. Deferred Decisions

| Decision | Deferred until | Why |
|----------|---------------|-----|
| Real-time updates via SSE/WebSocket | After v1 ships | GitHub Pages is static; needs external service |
| Search functionality | After v1 ships | Adds complexity; not needed for initial visibility |
| Observable Framework migration | After v1 ships | Would add build tooling overhead; vanilla JS is simpler for v1 |
| Automated spending tracking from agents | After v1 ships | Need to define agent logging conventions first |

## 9. Architecture & Test Implications

### Dependencies
- **Frontend:** Chart.js v4 (CDN), Mermaid.js v11 (CDN), List.js (CDN, ~10KB)
- **Markdown rendering:** marked + DOMPurify — deferred from v1 (no Markdown sections in v1; add when handoff logs are rendered inline)
- **Freshness badge:** Native `Intl.RelativeTimeFormat` — zero deps
- **Data export:** bash script (`moo-export-data.sh`) running on the Moo Swarm host
- **Push:** `gh` CLI + PAT on the host
- **Scheduling:** OpenClaw cron (`halo-data-export` job, every hour)

### Data export script — what it must do
1. Read `_align_rail/projects/` for project list and statuses
2. Read `_align_rail/projects/*/.moo-swarm/features/*/handoff-log.md` for pipeline state
3. Read `/home/lex/.openclaw/cron/jobs.json` for cron schedule + status
4. Query OpenClaw for session info (agent last-active)
5. Query OpenClaw or provider for token usage / cost
6. Fetch GitHub API for issues, PRs, stars (via `gh api`)
7. Assemble `data/swarm.json`
8. Commit and push to `github.com/moo-swarm/halo`

- `Intl.RelativeTimeFormat` — native, zero-dependency for freshness badge

### Data file schema: `data/swarm.json`

```json
{
  "updated_at": "2026-07-03T12:00:00Z",
  "refresh_interval": 3600,
  "projects": [
    {
      "name": "halo",
      "description": "Moo Swarm live status dashboard",
      "status": "active",
      "health": "green",
      "repo_url": "https://github.com/moo-swarm/halo",
      "stars": 0,
      "open_issues": 2,
      "last_updated": "2026-07-03",
      "pipeline_stage": "spec"
    }
  ],
  "pipeline": [
    {"agent": "veles", "emoji": "🐍", "role": "Research", "status": "pass", "last_run": "...", "badge_url": "...", "workflow_url": "..."},
    {"agent": "moo", "emoji": "🐮", "role": "Route", "status": "pass", "last_run": "...", "badge_url": "...", "workflow_url": "..."},
    {"agent": "cmok", "emoji": "🐉", "role": "Build", "status": "idle", "last_run": "...", "badge_url": "...", "workflow_url": "..."},
    {"agent": "bagnik", "emoji": "🚨", "role": "QA", "status": "pass", "last_run": "...", "badge_url": "...", "workflow_url": "..."},
    {"agent": "zlydni", "emoji": "🏚️", "role": "Commit", "status": "idle", "last_run": "...", "badge_url": "...", "workflow_url": "..."}
  ],
  "issues": [
    {"project": "aeroplasty", "number": 3, "title": "...", "labels": [], "created_at": "..."}
  ],
  "prs": [...],
  "cron_jobs": [
    {"name": "self-improvement-dispatch", "schedule": "0 9 * * *", "last_run": "...", "status": "ok"}
  ],
  "spending": {
    "total_tokens_7d": 1234567,
    "cost_7d": 2.45,
    "cost_30d": 10.20,
    "pricing_configured": false,
    "data_source": "openclaw_jsonl",
    "daily": [{"date": "2026-06-26", "tokens": 180000, "cost": 0.35}, ...]
  },
  "agents": [
    {"name": "moo", "emoji": "🐮", "role": "Orchestrator", "status": "active", "last_active": "...", "sessions_24h": 12, "tokens_24h": 45000}
  ],
  "meta": {
    "version": "1.0",
    "generated_by": "moo-export-data.sh",
    "export_host": "lex-agent-swarm",
    "openclaw_version": "24.18.0"
  }
}
```

### Performance targets
- FCP < 1.5s, LCP < 2.5s, TTI < 3.0s
- Total page weight < 500 KB, < 15 HTTP requests
- **Lazy load Chart.js** via Intersection Observer — only load when chart section enters viewport
- **Pre-minify** CSS/JS on the host before push: `npx terser script.js` / `npx clean-css-cli style.css`
- **Critical CSS** inlined in `<head>` for above-fold rendering
- Resource hints: `preconnect` to CDN hosts; `dns-prefetch` for GitHub
- Add `.nojekyll` file to prevent Jekyll processing on Pages

### Accessibility (WCAG AA minimum):
- **ARIA live regions**: `role="status" aria-live="polite" aria-atomic="true"` for content updates
- **Charts**: Canvas has `aria-hidden="true"`; companion `<table>` with `.sr-only` class for screen readers
- **Status indicators**: Never colour alone — combine dot + icon + text label for each status
- **Filterable table**: `role="grid"` pattern with roving tabindex for keyboard navigation; `aria-sort` on sortable headers
- **Filter controls**: Grouped with `<fieldset><legend>`; focus moves to first result after filter
- **Keyboard**: All interactive controls reachable via Tab/Enter/Space. No keyboard traps.
- **Theme toggle**: `aria-label` says what will happen (not current state). Min 44×44px touch target.
- **Pagination**: `aria-current="page"`, wrapped in `<nav aria-label="Table pagination">`

## 10. Documentation Implications

- `README.md` — what Halo is, data flow, how to contribute
- `CONTRIBUTING.md` — how to add a section/widget
- `docs/DATA-SOURCES.md` — where each piece of data comes from
- The export script should be well-commented since it's the critical path

## 11. Handoff Log

> Feature path: `/home/lex/.openclaw/workspaces/_align-rail_/projects/halo/.moo-swarm/features/2026-07-03-dashboard-v1`
> Spec by Moo 🐮 after requirements elicitation with Lex and 20-agent research sweep.
> Key changes from draft: data pushed FROM Moo host (not pulled by GHA), projects-focused (not repos),
> theme toggle following system preference, cron export script on host.
> **Research additions:** Mermaid.js pipeline viz, List.js table filter, Intl.RelativeTimeFormat freshness badge,
> marked+DOMPurify for Markdown, a11y checklist, performance targets, export script patterns (flock, no-op guard, retry).
> Key ACs: 13. Open questions: 5 (resolved: spending via OpenClaw JSONL, agents via sessions_list). Deferred decisions: 4.
> Data schema: `data/swarm.json` (see §9). Research synthesis: `research-synthesis.md`
