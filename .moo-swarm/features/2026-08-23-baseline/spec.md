# 2026-08-23-baseline — Spec

> **PROPOSAL-STAGE — awaiting owner decisions.** Elicited from evidence (codebase map,
> full code reads, git history, dataset inspection) with no live user in the loop, per
> the coordinator's baseline batch. Every AC was re-verified against actual files at
> commit `f85a0c6` (halo repo, working tree with untracked `tests/`). Items marked
> **VIOLATED** describe where current reality fails the contract; they are candidate
> requirements, not yet approved work.
>
> Project root: `workspaces/_align-rail_/projects/halo/` (own git repo, `github.com/moo-swarm/halo`)
> Feature path: `.moo-swarm/features/2026-08-23-baseline/`
> Evidence base: `.tlk/maps/2026-08-23-halo-project/map.md` (+ `open-questions.md`)

## Summary

Halo is the Moo Swarm's public status dashboard: a zero-build static site (GitHub
Pages) rendered from one pre-baked dataset (`data/swarm.json`, schema v2.0) that a
host-side cron job regenerates hourly and pushes to `main`. The shipped frontend
(`index.html` + `dashboard.js` + `styles.css`) is a single-IIFE vanilla-JS page with
seven sections, system/Telegram-native theming, Mini App integration, freshness
signalling, schema migration tolerance, and solid a11y affordances. The repo also
carries an unfinished FastAPI-served variant (`server/` + `static/halo.js`) that is
unrunnable as written. This baseline records the current-state contracts above,
and surfaces six verified gaps: a mid-render crash breaking two sections, a stale
public dataset (~7 weeks), an exporter error-path bug, over-broad Pages artifact
publishing, a plaintext PAT in the git remote, and dead UI chrome (inert theme
button).

## Related in-flight work (cross-references — not re-specced here)

| Feature | Location | State | Relationship to this baseline |
|---|---|---|---|
| telegram-native-theme | `.moo-swarm/features/2026-07-06-telegram-native-theme/` | implemented (dded6f0, f5f9d6b) | Its theming decisions (FOUC injection, `tg-dark`, themeChanged resync) are recorded here as current-state AC6, not re-litigated. |
| fullscreen-expand | `.moo-swarm/features/2026-07-06-fullscreen-expand/` | implemented (f85a0c6 kept expand, dropped haptics) | `ready()+expand()` behaviour is AC7 below. |
| main-button-refresh | `.moo-swarm/features/2026-07-06-main-button-refresh/` | partially implemented | Its spec marks spinner/retry/haptic ACs done; code shows only `setText('↻ Refresh') + onClick(reload) + show()` (`dashboard.js:717-723`) and f85a0c6 explicitly dropped haptics. Recorded factually under AC7; drift is flagged for the owner, not "fixed" here. |
| halo-hardening | `/home/lex/.openclaw/.tlk/features/2026-08-23-halo-hardening/` (main kit) | arch + tests done, awaiting Bagnik test gate | Overlapping findings (PAT, artifact scope, exporter `sys` bug, server parking, CI lint) are cross-referenced as hardening AC IDs, NOT duplicated as new requirements. One factual correction found: `server/.venv` is **not** git-tracked (`git ls-files` → 0 files), so the checkout-based Pages artifact never contains it; hardening's exposure premise shrinks but its F3 allowlist decision stands regardless. Hardening's "Pages frontend sound — do not touch" analysis premise is contradicted by finding F-A below (verified crash) — surfaced to the coordinator so the hardening gate knows about it. |

## Acceptance Criteria

MUST items describe contracts Halo should satisfy today. A **VIOLATED** tag means
the tree at `f85a0c6` demonstrably fails it; **OK** means verified holding.

### MUST

- [ ] **AC1 (OK)** — The Pages deployment of `main` serves a static page that renders
      seven sections (Active Projects, Pipeline Status, Regular Tasks, Issues & PRs,
      Budget & Usage, Budget by Agent, Agent Health — `dashboard.js:18-22`) from a
      single relative fetch of `data/swarm.json` (`dashboard.js:71,84`), with zero
      first-party runtime API calls; the only external deps are CDN scripts
      (Chart.js 4, Mermaid 11, telegram-web-app.js) and they fail soft (Mermaid has a
      plain-HTML pipeline fallback, `dashboard.js:339`).

- [ ] **AC2 (VIOLATED)** — Every section renders either content or its defined empty
      state, with **no runtime JS error during the render pass**. Today
      `renderFromData` calls `renderAgentBudget(...)` (`dashboard.js:123`), a function
      defined nowhere in the file; every successful load throws ReferenceError after
      Spending renders, so Budget by Agent and Agent Health remain blank (skeletons
      already hidden), `renderAgents` never runs, and the promise `.catch` re-renders
      through the stale-cache path (`dashboard.js:94-101`) forcing red dot +
      `(stale)` on fresh data. Introduced by f85a0c6; live on the public site.
      Resolution needs an owner decision (implement renderer + data source, or drop
      the section — see OQ5; note `agent_budgets` exists neither in schema v2.0 nor
      exporter output).

- [ ] **AC3 (OK)** — Load failure shows the page-level error banner with a Retry
      button (`index.html:85-88`, `dashboard.js:870-878`, retry wiring
      `dashboard.js:891-896`); a previously-loaded dataset is reused (stale-cache
      fallback, `dashboard.js:96-97`); skeleton loaders show until first render and
      sections carry `aria-busy` until then (`dashboard.js:105-112`).

- [ ] **AC4 (OK)** — The freshness badge derives from `data.updated_at`: green ≤60 min,
      amber ≤120 min, red plus `(stale)` label beyond 120 min or on fallback render;
      text is relative time; region is `aria-live="polite"` (`dashboard.js:138-172`,
      `index.html:75-78`). (The badge can only tell the truth about fresh data once
      AC2's forced-stale path is fixed.)

- [ ] **AC5 (OK)** — Schema tolerance: the frontend migrates v1.0 payloads client-side
      (`SCHEMA_MIGRATIONS`, `dashboard.js:24-57`) and tolerates additive unknown
      fields; the exporter enriches additively (`setdefault` everywhere,
      `scripts/moo-export-data.py:109-153`) and must preserve operator-preset values
      (pinned by existing test `MainEnrichmentTest`).

- [ ] **AC6 (OK, with UI gap)** — Theming auto-follows `prefers-color-scheme`; when
      served as a Telegram Mini App, the `<head>` FOUC script injects `--tg-*`
      tokens before first paint (`index.html:17-38`), `.tg-dark` flips the palette
      (`styles.css:39-53`), and the `themeChanged` event re-applies tokens and re-syncs
      charts/Mermaid (`dashboard.js:726-745`). Per dded6f0 there is deliberately NO
      manual toggle — but the header still renders an inert `#theme-toggle` button
      (`index.html:71`, no handler anywhere in `dashboard.js`). Resolving the dead
      control (remove, or restore manual override) requires an owner call (OQ6);
      shipping inert interactive chrome fails basic UI hygiene either way.

- [ ] **AC7 (OK, reduced scope)** — In Mini App context: `ready()` + `expand()` on init,
      MainButton shown with `↻ Refresh` retriggering `loadDashboardData()`;
      everything no-ops gracefully outside Telegram (`dashboard.js:708-746`). Current
      code does NOT implement the July main-button spec's progress-spinner/retry-text/
      haptic states (haptics dropped in f85a0c6) — recorded as intentional-for-now
      unless the owner says otherwise (OQ6 adjacent).

- [ ] **AC8 (VIOLATED)** — Exporter robustness contract: `moo-export-data.sh` runs the
      Python enricher then commits/pushes `data/swarm.json` **only when changed**
      (verified in script); the enricher maps unknown git authors to `null` owner and
      `gh api` failures to 0 issues without crashing (existing tests pin both) — and a
      missing `data/swarm.json` exits **status 1 with the intended message**. Today
      `sys.stderr`/`sys.exit` are used without `import sys`
      (`scripts/moo-export-data.py:104-105`) → NameError instead. Fix owned by
      halo-hardening F1/AC4 (its regression test sits at `@expectedFailure` until
      then). Also under this AC: the export schedule itself is dead — last
      `updated_at` 2026-07-05T15:51Z (~49 days) — restoration is hardening DR-4/AC7
      (ops, host scheduler).

- [ ] **AC9 (OK)** — Dataset contract: `swarm.json` carries exactly the v2.0 key set
      (`schema_version, updated_at, refresh_interval(3600), projects, pipeline,
      issues, prs, cron_jobs, spending, budget_daily, agents, meta`) with per-project
      and per-agent budget defaults `limit_tokens=200000`, `limit_cost=0.60`,
      `pricing_configured=false` on enrichment (verified against live file + tests).

- [ ] **AC10 (VIOLATED)** — Deploy surface: any push to `main` auto-deploys Pages
      (`.github/workflows/deploy-pages.yml`, verified trigger/concurrency/permissions),
      and the published artifact contains **site files only**. Today the artifact is
      the whole checkout (`path: .`), publicly exposing committed non-site files:
      `server/*.py`, `server/agents.json`, `static/halo.js`, `static/test.html`, and
      all 28 tracked `.moo-swarm/**` process files (specs, handoff logs). Nuance vs
      hardening's premise: `server/.venv` is untracked, so it is *not* published.
      Fix owned by hardening F3/AC3 (its guard asserts exactly this); whether the
      `.moo-swarm/` tree belongs in a public repo at all is OQ4.

- [ ] **AC11 (VIOLATED)** — Secrets hygiene: the origin remote URL embeds a plaintext
      GitHub PAT (map OQ3, value deliberately not reproduced here). Anyone with read
      access to the workspace gets push access to the org. Migration to credential
      helper + rotation owned by hardening F2/AC1 and user-side D1.

- [ ] **AC12 (OPEN — decision in flight)** — The unfinished server variant reaches a
      decided fate and the tree enforces it: either finished-and-runnable (static
      mount, launch path, the missing `/api/static/swarm.json` route
      `static/halo.js:107` expects, secret management, working role model — today's
      seeded roles `{orchestrator,research,build,qa,commit,docs}` satisfy neither
      `is_admin` nor `is_agent` (`{admin,agent}`), so admin routes are unreachable and
      report submission 403s even when logged in) **or** parked off `main` per
      hardening DR-1/AC6 (`park/server-variant` branch does not exist yet). Baseline
      takes no position; it records that limbo-with-public-exposure is not a stable
      end state (OQ1).

- [ ] **AC13 (PARTIAL)** — Quality floor: the stdlib-unittest exporter suite
      (`tests/test_export_data.py`, 7 tests incl. one `@expectedFailure` pinning
      AC8/F1) passes against the current tree **and is committed to the halo repo** —
      it currently exists only untracked on disk (`?? tests/`), so CI/teammates never
      see it; and a lint workflow (`node --check` all JS + `python3 -m py_compile`
      all Python on push) guards the auto-push pipeline (absent today; hardening
      E1/AC8-hardening). Swarm-root runner shim `tests/halo-export.test.sh` already
      wires the unittest layer into the kit's `tests/run.sh`.

- [ ] **AC14 (OK)** — Accessibility affordances hold: skip links (`index.html:14,57`),
      per-section `aria-busy`, live-region badge and result count, `role="alert"`
      error banner, screen-reader companion table for the spend chart
      (`index.html:233`), fieldset/legend filter group, and `escapeHtml` on all
      interpolated strings (`dashboard.js:757-762`).

### NICE

- [ ] **AC-N15** — Issues/PRs filter selections survive a page reload (URL hash or
      localStorage); today filters reset silently.
- [ ] **AC-N16** — Regular Tasks rows show next-estimated-run info when the export
      schema grows a field for it; today only last-status dots exist.
- [ ] **AC-N17** — Custom domain `halo.sh` restored via CNAME when DNS is ready
      (CNAME was removed at 89a0dca pending DNS; see deferred DB3).

## Open Questions (user input required)

- [ ] **OQ1** — Server variant fate: confirm hardening DR-1's "park on branch" (vs finish
      vs delete)? Baseline treats park as the leading option and flags the role-model
      inconsistency (seeded roles make admin/agent gates unreachable) as evidence the
      variant was never exercised.
- [ ] **OQ2** — Who owns re-registering the hourly export cron on the host (hardening
      DR-4/AC7)? Not recoverable from inside the repo; scheduler lives in the swarm
      host's cron store, and nothing visible has run since Jul 5.
- [ ] **OQ3** — PAT rotation mechanics (hardening D1): user-side auth action the swarm
      cannot perform silently. Until rotated, the leaked token remains valid even
      after the remote URL is cleaned.
- [ ] **OQ4** — Are the 28 tracked `.moo-swarm/**` files (internal specs, handoff logs)
      acceptable on a PUBLIC repo/Pages artifact? Hardening's F3 allowlist removes
      them from the artifact; whether they belong in the public repo at all is a
      separate owner call.
- [ ] **OQ5** — Budget by Agent section (added f85a0c6): implement `renderAgentBudget`
      + an `agent_budgets` exporter/schema field, or drop the section? Required to
      close AC2 either way.
- [ ] **OQ6** — Theme control product call: remove the inert `#theme-toggle` button and
      correct the README, or restore a working manual override (the old
      `localStorage["halo-theme"]` behaviour the README still describes)?
- [ ] **OQ7** — Swarm config drift: halo `.moo-swarm/PROJECT.md` names test commands
      (`npm run test:html` / `npx htmlhint`) for tooling the repo doesn't have (no
      package.json). Update the config to the unittest/guard reality, or add the
      HTML-lint tooling?

## Deferred Decisions

Tracked in `deferred.md` (created via `defer.sh`):

- **DB1** — JS unit/E2E test infrastructure (mirrors hardening D3). Trigger: second UI
  regression, or first feature touching `dashboard.js` logic beyond markup.
- **DB2** — Generalizing the exporter beyond hardcoded `PROJECTS_DIR` / single org.
  Trigger: project roster diverges from what the `_align-rail_` scan covers.
- **DB3** — Custom domain `halo.sh`. Trigger: DNS configured for the apex.
- **DB4** — Localisation beyond English. Trigger: demonstrated non-English audience.

## Architecture & Test Implications

- **Dependencies:** runtime = three CDN scripts only; build = none; tests = Python
  stdlib `unittest` only (host has no pytest — hardening DR-2) + bash guards via
  `talaka/tests/lib.sh`. Any proposed change must keep the zero-build property.
- **Storage/API surface:** frontends treat `data/swarm.json` as read-only; the ONLY
  component that writes the dataset is (would-be) `server/main.py`
  (`save_data`, lock + report endpoints) — a single-writer hazard to remember if the
  variant is ever revived alongside the hourly exporter. Other state:
  `server/agents.json`, `server/reports/*.jsonl`; shipped frontend uses no
  localStorage/sessionStorage at all (README says otherwise — docs gap).
- **Constraints for architecture-planning:** keep the 12-section IIFE convention and
  numbered banners in `dashboard.js`; FOUC head script must stay before `styles.css`
  in any HTML carrying the stylesheet; schema changes go through additive
  `setdefault` enrichment and deliberate `schema_version` bumps; interpreter skew
  exists between host python3.12 (tests pycache) and server venv 3.13.
- **Test implications:** AC2/AC4/AC6/AC7 are browser-runtime behaviours with no JS
  test harness today (DB1) — near-term verification is structural (node --check,
  grep-level guards like hardening's lib.sh pattern) plus manual smoke; AC8/AC9 are
  covered or pinnable in the existing unittest layer; AC10/AC11/AC12/AC13 map to
  hardening's skipped guards awaiting their fixes.

## Documentation Implications

README drift to reconcile once OQ1/OQ5/OQ6 resolve (Mokash scope, not this feature):

1. "Theme" section documents a toggle + `localStorage["halo-theme"]` persistence that
   no longer exists in the shipped frontend (auto-follow since dded6f0).
2. File structure lists a `CNAME` that was removed; omits `server/`, `static/`,
   `tests/`, and the exporter scripts' operational detail.
3. "Sections" enumerates six; the page renders seven (Budget by Agent missing).
4. No Development/tests note (`python3 -m unittest discover -s tests`) — matches
   hardening's planned F7 README edit; coordinate, don't duplicate.
