# 2026-08-23-baseline — Tech Plan

_Architecture baseline for the halo project as of `f85a0c6` (+ untracked `tests/`).
Spec: `spec.md` (this folder). Evidence base: `.tlk/maps/2026-08-23-halo-project/map.md`.
Design-only pass — no code or tests were written or modified; existing suites were NOT
executed (coordinator READ-ONLY constraint), see §5._

## 1. Architecture — current state

```text
                    ┌───────────────── swarm host ─────────────────┐
                    │  cron (hourly)  ✗ DEAD — nothing visible      │
                    │    │            has run since 2026-07-05     │
                    │    ▼                                          │
                    │  scripts/moo-export-data.sh                   │
                    │    ├── moo-export-data.py                     │
                    │    │    reads _align-rail_/projects/*,        │
                    │    │    gh api issue counts                   │
                    │    │    ✗ NameError if data file missing      │
                    │    │      (sys used, never imported :104-105) │
                    │    ├── git commit data/swarm.json (if diff)   │
                    │    └── git push ══(✗ PAT embedded in remote   │
                    │              URL, .git/config)══►             │
                    └──────────────────────┬───────────────────────┘
                                           ▼
                    github.com/moo-swarm/halo (main)
                                           │ push triggers
                                           ▼
                    .github/workflows/deploy-pages.yml
                    ✗ uploads WHOLE checkout (`path: .`) → publishes
                      server/*.py, server/agents.json, static/*,
                      .moo-swarm/** (28 internal files)
                      (note: server/.venv NOT tracked → not published)
                                           │
                                           ▼
        ┌────────────────  GitHub Pages (public)  ─────────────────┐
        │ index.html + styles.css + dashboard.js + data/swarm.json │
        │ ✓ theming (system-follow + Telegram FOUC/themeChanged)   │
        │ ✓ skeletons / error banner / retry / stale-cache reuse   │
        │ ✓ freshness badge thresholds 60/120min                   │
        │ ✓ v1→v2 client schema migration                          │
        │ ✗ RENDER CRASH: dashboard.js:123 calls undefined         │
        │   renderAgentBudget() → every load throws after Spending │
        │   → Budget by Agent + Agent Health blank, badge forced   │
        │   red/(stale) via fallback rerender (since f85a0c6)      │
        │ ✗ inert #theme-toggle button (no handler since dded6f0)  │
        │ ✗ data stale ~7 weeks (upstream cron death)              │
        └──────────────────────────────────────────────────────────┘

        ┌──── UNFINISHED VARIANT (dead weight on public main) ─────┐
        │ server/main.py (FastAPI): auth CRUD, lock, reports       │
        │   ✗ no launch path / __main__ / /static mount             │
        │   ✗ hardcoded dev session secret (:36)                   │
        │   ✗ seeded roles {orchestrator,research,build,qa,…}       │
        │     satisfy neither is_admin nor is_agent ({admin,agent}) │
        │     → admin routes unreachable; reports always 403       │
        │ static/halo.js → calls /api/static/swarm.json (:107),    │
        │   a route main.py never defines                          │
        │ templates/dashboard.html drifted clone of index.html     │
        └──────────────────────────────────────────────────────────┘

        ┌──────────────── TEST TOPOLOGY (two repos) ────────────────┐
        │ halo repo: tests/test_export_data.py (unittest, stdlib)   │
        │   7 tests; 1 @expectedFailure pins the sys bug (F1)       │
        │   ✗ EXISTS ONLY UNTRACKED on disk — never committed       │
        │ swarm repo: tests/halo-export.test.sh (runner shim →      │
        │   invokes halo unittest from kit's tests/run.sh)          │
        │ swarm repo: tests/halo-security.test.sh (lib.sh guards    │
        │   for AC-PAT/gitignore/artifact/park/lint — ALL           │
        │   skip_test-ed awaiting their hardening fixes)            │
        │ ✗ no JS harness anywhere; no CI lint workflow in halo     │
        └──────────────────────────────────────────────────────────┘
```

### What is sound (verified — do not churn)

- Pages frontend core loop: fetch → migrate → render → freshness; error banner +
  retry + stale-cache reuse; Mermaid fallback chain; IntersectionObserver-lazy Chart.js.
- Exporter enrichment design: additive `setdefault`, path-injectable globals
  (`DATA_FILE`/`PROJECTS_DIR`) — the property the unittest layer exploits.
- Two-repo test topology and the shim wiring into the kit's `tests/run.sh`.
- Theming architecture: FOUC head script + custom-property layers + `.tg-dark`.

## 2. Target architecture (proposed deltas only)

Same shape; five targeted corrections, no new components:

```text
  host cron (RE-REGISTERED, hourly, openclaw cron store)      [H-F4/DR-B5]
     │
     ▼
  moo-export-data.sh ── moo-export-data.py (+import sys)      [H-F1]
     │
     ├─ git push ──(credential helper / gh auth, NO PAT)──►    [H-F2]
     ▼
  deploy-pages.yml: upload ALLOWLIST ONLY                     [H-F3/DR-B3]
     │   index.html styles.css dashboard.js data/ .nojekyll
     ▼
  GitHub Pages — full render pass, all 7 sections             [B-F1/DR-B1]
     │   (#agent-budget resolved: implement OR drop; OQ5)
     │   #theme-toggle removed or re-wired (OQ6)
     ▼
  CI lint on push: node --check *.js + py_compile *.py        [H-E1]
     ▼
  halo main tip WITHOUT server/ + static/halo.js|test.html    [H-F6/DR-B4]
  (preserved on park/server-variant) — tests/ COMMITTED       [B-F2]
```

Legend: `[H-*]` = owned by halo-hardening (do not duplicate here);
`[B-*]` = baseline-originated items needing a routing home (see §3 backlog).

## 3. Prioritized backlog

| Priority | ID | Change | Files | Owner / route |
|---|---|---|---|---|
| P0 | B-F1 | Resolve AC2 render crash: implement `renderAgentBudget` fed client-side from existing `agents[].budget_daily` (no schema change) **or** drop the section — owner decides via OQ5 | `dashboard.js` (+ possibly `index.html`, `scripts/moo-export-data.py`) | new quick-fix feature, or fold into halo-hardening if owner agrees |
| P0 | B-F2 | Commit `tests/` to halo git so the suite exists for CI/teammates | halo `tests/` | rides along with any next Cmok touch of halo |
| P1 | B-G1 | Structural guard: every function invoked inside `renderFromData` is defined in-file (grep-level lib.sh assertion) — would have caught AC2 | swarm `tests/` (new guard) | `/architecture-planning` on the fixing feature |
| P1 | B-G2 | Guard: `tests/` tracked in halo git (`git ls-files tests/` non-empty) | swarm `tests/` | same |
| P1 | H-F1..F6, E1, E2 | PAT removal, artifact allowlist, `import sys`, cron re-registration, park server variant, README, lint CI, gitignore venv | see halo-hardening tech-plan §3 | halo-hardening (already routed; gate pending) |
| P2 | B-F3 | Remove or re-wire inert `#theme-toggle`; sync README Theme section | `index.html`, `dashboard.js`, `README.md` | after OQ6 |
| P2 | B-F4 | README drift sweep (sections 6→7, CNAME, Development/tests note) — coordinate with hardening F7 to avoid duplicate edits | `README.md` | @mokash post-fix |

## 4. Decision records

### DR-B1 — Close AC2 by rendering Budget by Agent client-side from `agents[]` (recommended)

- **Chosen (recommendation):** implement `renderAgentBudget` aggregating
  `data.agents[].budget_daily`, which already exists in schema v2.0 and the live
  dataset — zero exporter/schema change, restores a publicly visible section.
- **Alternatives:**
  - _New top-level `agent_budgets` key + exporter support:_ matches the call site's
    guess (`data.agent_budgets`) but adds schema surface and exporter work for data
    derivable from `agents[]`.
  - _Drop the section:_ smallest diff, but removes a shipped public feature without
    an owner conversation (hence OQ5 still gates the final call).
- **Consequence:** whichever way the owner picks, the ReferenceError disappears and
  the forced-stale badge side effect goes with it.

### DR-B2 — Keep the two-repo, stdlib-only test topology

- **Chosen:** halo keeps Python stdlib `unittest`; swarm root keeps lib.sh structural
  guards + the runner shim into `tests/run.sh`. No new runner, no pytest, no npm.
- **Alternatives:** consolidating everything into halo (breaks the kit's single
  `tests/run.sh` gate contract); pytest (new dependency, violates zero-dependency
  principle — rejected in hardening DR-2 already); JS harness now (deferred, DB1/DD-001).
- **Consequence:** Bagnik's full-suite gate exercises halo logic today; browser-runtime
  behaviour stays manually/structurally verified until DD-001 triggers.

### DR-B3 — Pages artifact moves to an explicit allowlist (endorses hardening F3)

- **Chosen:** `actions/upload-pages-artifact` receives an enumerated site-file list.
- **Alternatives:** exclude-list (`!:**` patterns) — fragile as new dirs appear;
  orphan `gh-pages` branch — adds a build-ish step against repo principles; relocating
  `.moo-swarm/` out of the public repo — bigger org question, tracked separately as OQ4.
- **Correction recorded:** hardening's premise that `server/.venv` (~all repo bytes)
  currently ships is false — the venv is untracked and `actions/checkout` materializes
  tracked files only. Exposure is real but smaller (source, accounts file, process docs).
  F3 remains right regardless; severity framing should be adjusted when its gate reads this.

### DR-B4 — Server variant parking mechanics (endorses hardening DR-1, adds detail)

- **Chosen:** plain git branch `park/server-variant` at f85a0c6 content, then `git rm`
  on main. No subtree/notes/tag cleverness — a branch is discoverable with stock git.
- **Alternative considered here:** `git worktree`/subtree preservation — unnecessary
  machinery for a variant whose revival (if ever) starts from a fresh requirements pass.
- **Consequence:** role-model flaws documented in spec AC12 travel with the branch as
  caveats for whoever revives it.

### DR-B5 — Cron restoration is an ops action through the `openclaw cron` CLI

- **Chosen:** register the hourly job in OpenClaw's SQLite cron store via
  `openclaw cron` (the kit's canonical scheduler — jobs live in
  `state/openclaw.sqlite`, not crontab), cwd = halo dir, then observe one pushed
  auto-export commit (hardening AC7's verification).
- **Alternatives:** system crontab (second scheduler to maintain, invisible to the
  swarm's own tooling); GitHub Actions scheduled export (would need repo secrets for
  host filesystem access — the exporter reads local `_align-rail_` paths, so it must
  run on the host).
- **Consequence:** no code change; verification is observational, hence the AC8-schedule
  half stays a known gap in the traceability table.

## 5. Tests — inventory and status (nothing executed this pass)

Per the coordinator's READ-ONLY constraint, no suite was run and no test file was
created or modified; main-repo `check-coverage.sh` was **skipped deliberately** — it
executes `.tlk/PROJECT.md`'s `tests/run.sh`, whose scope is the swarm/kit repo, not
this project tree (halo coverage reaches it only via the shim below).

| Suite | Layer | Location | Last-known state (not re-run) |
|---|---|---|---|
| `tests/test_export_data.py` | Python unittest (stdlib) | halo repo — **untracked on disk** | Written by halo-hardening; its tech-plan records green-except-1-expectedFailure; `__pycache__` (cpython-312) proves a prior local run |
| `tests/halo-export.test.sh` | bash runner shim | swarm repo `tests/` | Invokes the unittest layer from kit `tests/run.sh`; passes-through its result |
| `tests/halo-security.test.sh` | bash lib.sh guards | swarm repo `tests/` | All 5 guards `skip_test`-ed pending hardening F2/E2/F3/F6/E1, by design (DR-3 there) |

## 6. UX states covered

No UI change is proposed directly by this baseline (changes are owner-gated), but the
current-state matrix documents what exists and what AC2 breaks:

| State | Where today | Status |
|---|---|---|
| loading | skeleton loaders + `aria-busy` per section (`index.html` sections, cleared `dashboard.js:105-112`) | OK |
| success | normal render path | broken past Spending by AC2 crash |
| empty | `EMPTY_MESSAGES` for all 7 sections (`dashboard.js:59-67`) | unreachable for Agent Health while AC2 crashes first |
| error | page banner + Retry (`index.html:85-88`) | OK, but masked during AC2 (banner never shown; silent blankness instead) |
| retry | Retry button + MainButton refresh + stale-cache reuse | OK mechanically; stale-flag side effect from AC2 mislabels fresh data |
| stale | red dot + `(stale)` >120 min | OK logic; currently always-on due to AC2 fallback rerender |

No ux-design.md exists for this baseline (no UI delta approved); a11y assertions stay
structural (spec AC14) rather than behavioural until DD-001.

## 7. AC-to-test traceability (mandatory — covers every spec AC)

Status vocabulary: `written` = an existing test pins it; `pending` = no executable test
today (guard candidates noted); hardening-guard rows keep their skip-until-fix semantics.

| Acceptance Criterion | Test file | Test name / mechanism | Status |
|---|---|---|---|
| AC1 static seven-section delivery | — | structural guard candidate: `DATA_URL` relative + workflow trigger + `SCHEMA.sectionIds` length 7 | pending |
| AC2 no runtime render error | — | B-G1 guard candidate (`renderFromData` callees defined) + future JS smoke (DD-001) | **pending — blocked on OQ5 resolution** |
| AC3 banner/retry/stale-cache | — | JS-behavioural; manual smoke today | pending |
| AC4 freshness thresholds | — | pure-function candidate once extracted (`updateFreshness` is DOM-coupled) | pending |
| AC5 additive enrichment + migration tolerance | halo `tests/test_export_data.py` | `MainEnrichmentTest.test_enriches_defaults_preserving_existing_fields`; `ComputeSpecsTest.*` | written |
| AC6 theming follow/injection/resync | — | structural greps possible (FOUC script presence, tg-dark rules); behavioural needs browser | pending |
| AC7 Mini App ready/expand/MainButton | — | JS-behavioural; manual smoke today | pending |
| AC8 exporter robustness (exit-1 path, gh→0, author→null) | halo `tests/test_export_data.py` | `MissingDataFileTest.test_missing_data_file_exits_cleanly` (`@expectedFailure` until H-F1); `FetchIssuesTest.test_returns_zero_when_gh_fails`; `InferPipelineOwnerTest.test_unknown_author_returns_none` | written (AC4-pin expected-failing by design) |
| AC8-schedule hourly export observed | — | ops verification per DR-B5 — not unit-testable | **known gap** (mirrors hardening AC7) |
| AC9 dataset contract v2.0 | halo `tests/test_export_data.py` | `MainEnrichmentTest` (schema_version, budget defaults); full key-set completeness itself untested — guard candidate over `data/swarm.json` keys | written (partial) |
| AC10 site-files-only artifact | swarm `tests/halo-security.test.sh` | `test_pages_workflow_uploads_site_files_only` (skip_test → H-F3) | pending (skipped → F3) |
| AC11 no PAT in remote URL | swarm `tests/halo-security.test.sh` | `test_remote_url_has_no_embedded_pat` (skip_test → H-F2) | pending (skipped → F2) |
| AC12 server variant decided fate enforced | swarm `tests/halo-security.test.sh` | `test_server_variant_absent_from_main` (skip_test → H-F6) | pending (skipped → F6) |
| AC13 suite committed + lint CI | swarm `tests/halo-security.test.sh` | `test_ci_lint_workflow_exists` (skip_test → H-E1); committed-ness: B-G2 guard candidate | pending (unittest half: written-on-disk, untracked) |
| AC14 a11y affordances present | — | structural guard candidate (skip-link/aria-live/sr-table greps) | pending |
| AC-N15 filter persistence | — | — | pending (NICE, unscheduled) |
| AC-N16 next-run info in Regular Tasks | — | — | pending (NICE, unscheduled) |
| AC-N17 halo.sh domain | — | — | pending (NICE, gated on DD-003) |

## 8. Known gaps

- **Browser-runtime behaviours (AC2/3/4/6/7)** have no automated coverage; nearest
  executable step is the B-G1 static guard plus resolving OQ5. Tracked as DD-001.
- **AC8-schedule** (cron alive) is observational only — closes like hardening AC7 at
  ops review, not in a suite.
- **AC13** cannot fully close until `tests/` is committed (B-F2) — a passing untracked
  suite protects nobody.
- **AC2** is simultaneously the highest-value finding and untestable until its fix shape
  is chosen; any fix should land together with B-G1 so the class of bug gets a guard,
  not just this instance a patch.
