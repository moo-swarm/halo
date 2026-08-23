# Halo — ideas & opportunities research (2026-08-23)

Advisory pass by tasks-researching. Every internal claim cites `path:line` from the working tree at
`workspaces/_align-rail_/projects/halo`; every external claim cites a URL that was actually fetched/searched today.
Scope was ideas + requirements, not a build plan.

---

## 1. Current state snapshot

### What the page shows today

Seven sections (`index.html:91-260`, rendered by `dashboard.js`, a 900-line single IIFE):

| Section | Source of truth | Live or frozen |
|---|---|---|
| Active Projects | `data/swarm.json` `.projects[]` | **half-live** — exporter refreshes `specs`, `last_updated`, `pipeline_owner_agent`, `open_issues` count; everything else is seed |
| Pipeline Status | `.pipeline[]` | **frozen** — last_run values are 2026-07-02 seed data (`data/swarm.json:122-168`) |
| Regular Tasks (cron) | `.cron_jobs[]` | **frozen** — last_run 2026-06/07 (`data/swarm.json:270-306`) |
| Issues & PRs | `.issues[]` / `.prs[]` | **frozen** — 6 seeded issues dated 2026-06-26…07-01 (`data/swarm.json:169-269`) |
| Budget & Usage | `.spending` | **frozen** — daily series ends 2026-07-03 (`data/swarm.json:307-388`) |
| Budget by Agent | `.agent_budgets[]` | **never renders** — see bug B1 |
| Agent Health | `.agents[]` | **never renders** — see bug B1 |

### Data flow (verified)

Host cron hourly → `scripts/moo-export-data.sh` → `scripts/moo-export-data.py` → commit+push `data/swarm.json`
→ GitHub Actions `deploy-pages.yml` assembles `_site/` from an explicit 5-file allowlist and deploys Pages.
The exporter is an *enricher*, not an exporter: it reads the existing JSON, recomputes specs from
`.moo-swarm/{features,archive}` dirs (`scripts/moo-export-data.py:27-47`), infers owner agent from git-log author
emails mapped through `AGENT_ALIASES` (`:50-84`), fetches one integer per repo via `gh api … open_issues_count`
(`:87-100`), and `setdefault`s budget fields (`:127-132`). It never regenerates issues/prs/pipeline/cron/agents/spending.

### Auth/security posture (good after e6bc0d0)

- Pages artifact allowlist — only `index.html styles.css dashboard.js data/swarm.json .nojekyll` ship
  (`.github/workflows/deploy-pages.yml`); no repo source, no server remnants.
- CI lint on push: `node --check` on all JS + `py_compile` on all Python (`.github/workflows/lint.yml`).
- Credential-free origin URL, auth via gh credential helper (commit message e6bc0d0).
- FastAPI server variant deleted; history parked at branch `park/server-variant` (`server/` now holds only a gitignored venv).
- XSS discipline in frontend: all interpolations go through `escapeHtml` (`dashboard.js:757-762`); external links get
  `rel="noopener"`. One flag: Mermaid initialized with `securityLevel: 'loose'` (`dashboard.js:320`) — unnecessary for
  fully self-produced static input; tighten to `'strict'`.

### Bugs found during this research (verified by reading, not yet fixed)

- **B1 (P0, breaks two sections):** `renderFromData` calls `renderAgentBudget(data.agent_budgets || [])` at
  `dashboard.js:123`, but no such function exists anywhere in the artifact (index.html has only theme/CDN script tags;
  grep over f85a0c6 and e6bc0d0 trees confirms it never landed). ReferenceError fires mid-render → `renderAgents`
  (`:124`) never runs, so **Budget-by-Agent stays skeleton forever and Agent Health never renders**, and the `.catch`
  at `:94-101` treats every load as failed (error banner / cached re-render loop). Introduced by f85a0c6 which added
  the call site but not the implementation.
- **B2 (P1, silent):** `buildMermaidDefinition` references `MERMAID_STATUS_STYLES_DARK`/`MERMAID_STATUS_STYLES`
  (`dashboard.js:285`) — undefined anywhere. Throws synchronously inside `renderMermaid`, which *is* inside the
  try/catch at `dashboard.js:257-264`, so it silently falls back to the plain-HTML list: **the Mermaid flowchart can
  never render**; nobody notices because the fallback looks intentional.
- **B3 (P2):** dead theme toggle — `#theme-toggle` button exists (`index.html:71`) but `dashboard.js` registers no
  click handler and there is no `halo-theme` localStorage key anywhere; README's "Persisted in localStorage"
  claim (`README.md:44-48`) describes behaviour that does not exist (theme follows system/Telegram media query only).
- **B4 (P2):** signature drift — `renderSpending(data.spending, isStale)` called with 2 args (`:122`), defined with 1
  (`:536`); `initChart(canvas, spending.daily)` uses `.daily` even when rows were sourced from `budget_daily.items`
  (`:543-545, :570`).
- **B5 (P1, trust):** misleading freshness — `updated_at` is refreshed hourly by the enricher, so the badge shows a
  green "updated N minutes ago" while five of seven sections display June/July seed data. The freshness signal is
  honest about the file, dishonest about the content.
- Why CI missed B1/B2: `node --check` is syntax-only; unresolved identifiers are runtime errors. There is no test
  that executes `dashboard.js`.

### Config drift

`.moo-swarm/PROJECT.md:11-17` documents `npm run build` / `npm run test:html` / optional prettier — there is no
`package.json` (root listing verified). README correctly says "no build step, no framework, no npm". Tests are Python
stdlib unittest (`tests/test_export_data.py`, 144 lines) + bash guards, not jest.

---

## 2. Comparables & their advantages

| Comparable | What it shows / does | Advantage halo could absorb | URL |
|---|---|---|---|
| github-community-projects/org-metrics-dashboard | Actions-fetched org repo health: licenses, issue/PR counts, response times; TS app+backend, `data.json` → Pages | Halo's stated inspiration; adds per-repo response-time metrics (time-to-first-response) | https://github.com/github-community-projects/org-metrics-dashboard |
| OSS Insight (PingCAP) | Repo/dev/org analytics over ~7B GitHub events (TiDB): stars, PRs, issue time-cost, contributor geography, NL→SQL explorer, API/MCP | Depth menu: PR time-cost distributions, contribution time heatmaps, org-vs-org compare | https://ossinsight.io/docs/about |
| devstats (CNCF) | Per-project contribution dashboards (GHArchive) for CNCF repos | Long-horizon weekly/monthly rollups per project | https://devstats.cncf.io |
| LinearB | Delivery/quality/DORA dashboards: cycle time split into Coding/Pickup/Review/Deploy stages, CFR, MTTR, throughput; benchmarks; free tier | Stage-split cycle time for the swarm pipeline itself (spec→build→QA→commit durations) | https://linearb.dev (metrics per vendor docs; pricing tiers via G2 comparison) |
| Swarmia | DORA + SPACE, benchmarks, working-agreement notifications; free ≤9 devs | Investment view (where agent effort goes across projects) | https://www.swarmia.com |
| Flightdeck | Self-hosted observability/control plane for AI agents: live fleet timeline (row per agent, sub-agents indented), token/latency/error/cost trends per agent, event search, token budgets + MCP allow/block governance | The closest nascent competitor to "swarm ops"; validates demand for fleet views + cost-per-agent + governance panels | https://github.com/flightdeckhq/flightdeck |
| ObserveCo | Fleet health: liveness checks, circuit breakers, auto-heal/restart, push alerts incl. Telegram, per-component token intelligence, span-tree tracing | Stall detection + auto-alerting vocabulary; Telegram alert channel matches moo-swarm's existing connector project | https://github.com/observeco/observeco |
| claude-code-telemetry (KubeRocketCI) | Claude Code OTel metrics → Prometheus/Loki/Grafana; tokens/cost attributed by model, agent, skill, tool, project, epic; captures counters only, no prompt content | Attribution taxonomy (per project / per agent / per skill) worth copying into swarm.json schema v3 | https://github.com/KubeRocketCI/claude-code-telemetry |
| ccusage / spendbar / claude-ledger / claude-code-cockpit | Transcript-parsing CLIs: per-project/per-model token+cost accounting from `~/.claude/projects/*.jsonl`, zero-dependency, local | Proves per-project cost is computable host-side with zero new infrastructure — exactly what halo's exporter needs | https://github.com/ryoppippi/ccusage (ecosystem per search results incl. paultaki/claude-code-cockpit, BMapAI/claude-ledger) |
| healthchecks.io / Dead Man's Snitch | Cron heartbeat monitoring: ping-on-success, alert when ping late; free 20 checks vs free 1 check; $20/mo ≈100 jobs | The model for cron-jobs section alerts: expected-next-run math + "missed" state + notification | https://healthchecks.io/pricing/ , https://healthchecks.io/docs/healthchecks_dead_mans_snitch_comparison/ |
| githubstatus.com | Component status grid, 90-day uptime bars per component, incident lifecycle (investigating→resolved), public REST API (Statuspage schema) | The design language for a *public transparency* page: uptime strips per cron job/project, incident-style feed for swarm failures | https://www.githubstatus.com (API at /api) |
| shields.io endpoint / dynamic-json badges | Badge rendered from any JSON URL + JSONPath (`/badge/dynamic/json?url=…&query=…`) or shield-schema endpoint | Zero-effort embedding of halo KPIs into any README/profile — halo already publishes stable JSON on Pages | https://shields.io/badges/dynamic-json-badge , https://shields.io/badges/endpoint-badge |

---

## 3. New ideas / feature candidates

Grouped by theme; each is small because the architecture (pre-baked JSON + dumb renderer) makes every feature mostly
an exporter field plus a render function.

**A. Make it true (data honesty)**
- A1. Full export: regenerate issues/PRs lists via `gh api` paging, pipeline stage from each project's handoff-log tail, cron jobs from OpenClaw's cron store, agents from session L1 state. Kills B5.
- A2. Real spending: host-side transcript parsing (ccusage pattern — zero infra) or OpenRouter `/api/v1/activity` management-key pull (returns USD usage, requests, prompt/completion/reasoning tokens per date/model/provider — docs verified).
- A3. Per-section freshness: emit `sections_updated_at` map; badge per section instead of one global green dot.

**B. Ops value**
- B1. Cron heartbeat panel: compute expected next run from schedule; show "on-time / late / missed" like healthchecks; missed = red strip.
- B2. Stall detection upgrade: currently 7d/30d thresholds on folder dates (`dashboard.js:224-230`); use spec activity + git push dates + cron cadence to classify *active / stalled / dormant / abandoned* with reason strings.
- B3. Cost-per-feature: join daily spend with feature-folder date ranges → "$ per shipped feature", per project. Nobody in the comparables table shows this; it is the killer number for a swarm.
- B4. Cycle-time stages à la LinearB for the swarm pipeline: median hours in spec→arch→build→QA→commit per feature (computable purely from `.moo-swarm/features/*/handoff-log.md` timestamps).
- B5. Incident feed: append-only list of gate failures / fix-loop escalations (Bagnik FAIL events) rendered githubstatus-style.
- B6. Uptime strips: 90-day (or 30-day) green/red day-strip per cron job and per project — cheap, instantly legible.
- B7. Alert fan-out: exporter pushes Telegram message on missed heartbeat / budget overrun via the org's own telegram-connector; dashboard becomes the *record*, Telegram the *channel*.

**C. Reach / embedding**
- C1. Shields badges from `data/swarm.json`: projects-active, 7-day cost, oldest-stale-project, cron-health — dynamic-json badge points straight at the Pages JSON. ~Zero backend work.
- C2. Org-profile README embed: same badges composed into `moo-swarm/.github` profile.
- C3. JSON-as-API stance: document swarm.json as a stable public feed (schema versioned — schema migration machinery already exists at `dashboard.js:24-57`); other agents/tools consume it.
- C4. OG/Twitter card meta tags so Telegram link previews show live numbers (mobile-first principle already in MEMORY.md).

**D. Governance / privacy**
- D1. Private-mode build flag: exporter redaction profile (costs rounded, agent names kept, projects hidden) producing a second artifact — public page stays, private page behind anything.
- D2. Budget enforcement surfacing: limit_tokens/limit_cost already exist in schema (`scripts/moo-export-data.py:131-132`); show burn-down vs limit and projected breach hour.

---

## 4. New requirements / gaps

- R1. Exporter must generate, not enrich (A1/A2) — otherwise every downstream idea renders stale seed data. Biggest gap between README promise ("shows the current state") and reality.
- R2. Runtime smoke test for `dashboard.js`: execute the IIFE against a stub DOM (jsdom or hand-rolled stubs) asserting all seven sections render from a fixture JSON. Directly prevents recurrence of B1/B2; `node --check` cannot catch identifier-resolution errors.
- R3. Fix B1/B2 before any new feature — two of seven sections are dark right now on the deployed site.
- R4. Freshness contract: per-section timestamps + stale styling (A3/B5) — required for the public-transparency story to be credible.
- R5. Privacy decision recorded in MEMORY.md: what cost/token granularity may be public (currently seed values are fake-safe; real values may not be). Blocks A2/C1 shipping real numbers.
- R6. Schema v3 plan: add `cycle_time`, `heartbeats`, `incidents`, `sections_updated_at`; keep the migration chain (`SCHEMA_MIGRATIONS`) growing rather than mutating in place.
- R7. Docs hygiene: reconcile `.moo-swarm/PROJECT.md` npm fiction with reality; note `park/server-variant` branch in README so future archaeologists don't rebuild the server.
- R8. Tighten Mermaid `securityLevel` to `'strict'` once B2 is fixed (input is self-produced; loose buys nothing).

---

## 5. Productization options

**The niche that exists:** "public status page for your coding-agent swarm." Verified adjacent landscape:

- Transcript cost tools (ccusage et al.) — local CLI numbers, no shareable page.
- OTel stacks (claude-code-telemetry, Grafana dashboards) — powerful but require collector+Prometheus+Loki+Grafana plumbing.
- Flightdeck / ObserveCo / Musematic — self-hosted streaming observability planes; real products, real features, Apache/MIT.

None of these produces a zero-infra, hosted-free, linkable public page. That is exactly halo's shape:
Actions+Pages, pre-baked JSON, Telegram Mini App, embeddable badges, MIT template others can fork.

**Verdict: realistic as a productized open-source template, not as a SaaS.**

- Template path (yes): polish halo into "fork-me status page for Claude Code / OpenClaw swarms" — config-driven org name, generic exporter, badge snippets, screenshots. Costs little beyond items in §4; gives moo-swarm a visible artifact (recruiting/portfolio/transparency) and possibly stars.
- SaaS path (no): private multi-tenant mode needs a backend + secrets + billing; that abandons the zero-infra advantage and lands halo inside Flightdesk/Grafana territory where it loses on every axis. Swarmia/LinearB already give free tiers to teams ≤9 devs; healthchecks.io is free for OSS.
- Monetization: none credible short-term. Adjacent option if ever desired: paid hosted-redaction proxy (turn private telemetry into a safe public page) — interesting idea, unproven market, do not build now.

---

## 6. Top-3 recommendations (impact × effort)

1. **P0 — Repair truth: fix B1+B2, add runtime smoke test (R2), honest per-section freshness (R3/R4).**
   Impact: critical (site is silently half-broken today); Effort: low (~a day incl. test harness). Everything else assumes a rendering dashboard.
2. **P1 — Make the exporter export (R1 + A1/A2):** live issues/PRs/pipeline/cron/agents/spending, transcript-based cost parse or OpenRouter activity pull, gated by the privacy decision (R5).
   Impact: high — converts halo from animated mockup to the real thing; Effort: medium (one focused feature cycle).
3. **P2 — Ops surface: cron heartbeats + stall reasons + 90-day strips + Telegram alerts (B1/B2/B6/B7) and shields badges (C1/C2).**
   Impact: high perceived value, both internally (catch dead jobs) and publicly (badges everywhere); Effort: low-medium; badges alone are near-zero effort and can ship with #1.

---

## 7. Open questions

- Audience: who actually reads the public page besides the operator? (Determines whether C-group investment is justified.)
- Privacy boundary: are real dollar costs and per-agent token counts publishable, or must public mode be redacted (D1)?
- Ground truth for agents/sessions: session.sh L1 state, OpenClaw SQLite (cron lives there), or transcripts? Needs a decision before A1.
- Should the exporter also read talaka `.tlk/features` for projects that use talaka rather than `.moo-swarm`?
- GitHub Actions as export runner (token-scoped, no host dependency) vs current host-cron — trade-off not yet evaluated.
- Is Mermaid still wanted at all once B2 is fixed, or is the plain fallback (which users have only ever seen) good enough?
