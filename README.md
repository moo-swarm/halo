# Halo — Moo Swarm Status

Live status dashboard for the [Moo Swarm](https://github.com/moo-swarm).

Halo is a **public GitHub Pages dashboard** that shows the current state of the
moo-swarm — active projects, pipeline status, issues, regular tasks, spending,
and agent health.

## Data Flow

```
Moo Swarm host (cron, hourly)
  │
  ├── moo-export-data.sh:
  │   ├── read swarm project files, openclaw.sqlite, agent session mtimes
  │   ├── fetch GitHub API for issues/PRs
  │   └── generate data/swarm.json
  │
  └── git push to github.com/moo-swarm/halo
       │
       └── GitHub Pages auto-deploys from main
```

## Export pipeline

`scripts/moo-export-data.sh` runs hourly from host cron: it regenerates
`data/swarm.json`, then commits and pushes it to `main`, where GitHub Pages
deploys it. Paths are configurable via env (current defaults):

| Variable | Default |
|---|---|
| `HALO_OPENCLAW_DB` | `/home/lex/.openclaw/state/openclaw.sqlite` |
| `HALO_AGENTS_DIR` | `/home/lex/.openclaw/agents` |
| `HALO_PROJECTS_DIR` | `/home/lex/.openclaw/workspaces/_align-rail_/projects` |
| `HALO_REPO_DENYLIST` | `.github` (comma-separated) |

### Where each section's data comes from

| Section | Status | Source |
|---|---|---|
| Active Projects | Live | Filesystem scan of `_align-rail_/projects` (feature dirs, git-log owner); `open_issues` counts come from the same GitHub fetch |
| Pipeline Status | Live | Latest entry headers from each project's `.moo-swarm/features/*/handoff-log.md` |
| Open Issues & PRs | Live | `gh api` over moo-swarm org repos — one paged repo-list call, then open issues and PRs per repo |
| Cron Jobs | Live | `cron_jobs` table of `openclaw.sqlite`, opened read-only, whitelisted columns only |
| Agent Health | Live | Session-file mtimes under `agents/*/sessions/` — metadata only, never content. `tokens_24h` exports as `null` (not derivable without parsing transcripts); status derives from mtime age only (<60 min active, <7 days idle, otherwise dormant) |
| Spending & Usage | Pending | Stays on seed/enrichment data, pending owner privacy decision F2 (may real dollar/token figures be published?). Not live — do not read it as current spend |

### Freshness and failure honesty

The exporter labels failed sources instead of hiding them:

- Every successful source fetch stamps its section into the top-level
  `sections_updated_at` map in `data/swarm.json`. Global `updated_at`
  timestamps the file itself.
- When a source fails, the error is recorded in `source_errors[<section>]`
  (`{error, at}`). That section keeps its last-good values and old timestamp,
  the other sections still refresh, the file still ships, and the run exits 0
  — partial success is success; the maps tell you which part is old.
- A legitimately empty source (zero open issues or PRs) exports empty arrays
  with a fresh stamp. Empty is success, never conflated with failure.

Badge semantics — the global header badge uses these thresholds. Per-section
chips differ: they are binary, with no 60–120 amber state.

| Global badge | Meaning |
|---|---|
| 🟢 green | refreshed < 60 min ago |
| 🟡 amber | 60–120 min since last successful fetch |
| 🔴 red + `(stale)` | > 120 min since last successful fetch |

Each section header carries its own chip: 🟡 `stale` when a section's mapped
stamp exceeds 120 min, 🔴 `source failed` when the section appears in
`source_errors` — that source failed this run; the rest of the page is still
live.

### Privacy boundaries

- **Cron payloads excluded.** The cron export reads a fixed column whitelist
  (name, schedule fields, timing/status counters). Payload bodies, job/state
  JSON blobs, delivery targets (Telegram chat ids), and free-text errors are
  never exported. A guard test greps the serialized output for forbidden
  substrings (`payload`, `delivery_to`, `delivery_channel`, `session_key`,
  `job_json`, `state_json`, `telegram:`) and token-like patterns.
- **Agent transcripts excluded.** Only session-file mtimes are read — never
  session content.

### Rate-limit budget

One paged `gh api orgs/moo-swarm/repos` call plus two calls per scanned repo:
`1 + 2·N` calls per hourly run, where N is the number of repos scanned after
the denylist — well under the 5,000/hour authenticated limit, asserted ≤ 40
in tests.

## Architecture

- **Single page:** `index.html` — all HTML in one file
- **Styles:** `styles.css` — 3-layer CSS custom properties for theming
- **Scripts:** `dashboard.js` — single IIFE with 12 commented sections
- **Data:** `data/swarm.json` — pre-baked JSON, zero API calls at page load
- **Charts:** Chart.js v4 (CDN, lazy-loaded via Intersection Observer)
- **Diagrams:** Mermaid.js v11 (CDN, with plain-HTML badge fallback)
- **No build step, no framework, no npm**

## Sections

1. **Active Projects** — table with health indicator (🟢/🟡/🔴)
2. **Pipeline Status** — Mermaid.js flowchart with plain-HTML fallback
3. **Open Issues & PRs** — filterable tables by project/label
4. **Cron Jobs** — schedule table with status dots
5. **Spending & Usage** — Chart.js bar chart + summary stats (lazy-loaded)
6. **Agent Health** — cards grid with status dots and activity

## Theme

- Light / dark mode toggle
- Follows system preference by default
- Persisted in `localStorage` as `halo-theme`
- FOUC prevention via inline script in `<head>`

## Development

No build step needed. Open `index.html` in a browser or serve locally:

```bash
npx serve .
```

### Tests

Stdlib-only (`unittest` + bash guards) — no dependencies to install:

```bash
# inside halo/: exporter unit tests
python3 -m unittest discover -s tests

# from the swarm root: all halo suites (unit + structural guards)
tests/run.sh halo
```

CI runs `node --check` on all JavaScript and `python3 -m py_compile` on all
Python on every push to main (`.github/workflows/lint.yml`).

## File Structure

```
halo/
├── index.html        ← Entry point
├── styles.css        ← All CSS
├── dashboard.js      ← All JS (IIFE)
├── data/
│   └── swarm.json    ← Pre-baked data
├── scripts/          ← Hourly export (host cron → commit → Pages)
├── tests/            ← Stdlib unit tests (exporter)
├── .nojekyll         ← Disable Jekyll on Pages
├── CNAME             ← Custom domain placeholder
└── README.md         ← This file
```


## License

MIT