# Tech Plan — Live exporter: make the frozen sections live

**Feature path:** `workspaces/_align-rail_/projects/halo/.moo-swarm/features/2026-08-23-live-exporter/`
**Date:** 2026-08-24 · **Author:** architecture-planning
**Inputs:** spec.md (20 ACs, authoritative) · scripts/moo-export-data.py (current enricher) · tests/test_export_data.py · tests/smoke.test.js · dashboard.js · data/swarm.json · .github/workflows/
**Constraints carried in:** stdlib-only Python (host has no pip — DR-2 precedent); schema-v2 mandatory; PII hard lines; write only data/swarm.json.

---

## 0. Baseline (measured this session)

| Fact | Value |
|---|---|
| Python suite | 7 unittest tests, green (`python3 -m unittest discover -s tests -p "test_*.py"`) |
| JS suite | 2 node --test tests, green — **but only via working invocation, see 1.4** |
| cron_jobs table | 5 rows / 5 enabled; live columns confirmed incl. `payload_message`, `delivery_to`, `job_json`, `state_json`, `description`, `last_error` — whitelist is load-bearing |
| ro-URI probe | `sqlite3.connect("file:…?mode=ro", uri=True)` then CREATE → `OperationalError: attempt to write a readonly database`. Writes blocked at engine level |
| agents dirs on host | 9: bagnik, cmok, damavik, main, mokash, moo, veles, yaga, zlydni (seed has 6) |
| gh auth | keyring, account bthos, active |
| Org repos | 16 project repos (gate correction; spec D5 said 17) |

**Baseline finding F-1 (invocation):** on host node v24.16.0, `node --test tests/` and `node --test tests`
**fail** with `Cannot find module …/tests` (directory arg not resolved). Working forms:
`cd tests && node --test` or from repo root `node --test tests/*.test.js`.
Spec AC17 names the broken form — Cmok implements against the working form; Mokash documents it.
No CI change required by AC17 ("lint workflow unchanged") — lint.yml never ran tests before; keep it that way.

---

## 1. Architecture

### 1.1 Module layout — one file, layered functions

Stay single-file: `scripts/moo-export-data.py` (importlib-loaded by tests; hyphen filename; stdlib only).
Internal layering, top to bottom:

```
┌─ CONFIG ────────────────────────────────────────────────────────
│  env-config(): HALO_OPENCLAW_DB, HALO_AGENTS_DIR,
│    HALO_PROJECTS_DIR, HALO_REPO_DENYLIST   (AC18; read once in main,
│    module-level defaults kept patchable for tests)
│  DATA_FILE, ISSUE_CAP=50, PR_CAP=50, STALE_MINUTES_DASH=120
│  AGENT_META      {name: {emoji, role}} — seed 6 + neutral fallback
│  WORKER_ROLES    static worker→role map for pipeline entries (D2)
│  CRON_COLUMNS    SELECT-projection tuple (§1.3)
│  FORBIDDEN_SUBSTRINGS + TOKEN_RE   guard lists (AC3/AC15)
├─ GH LAYER ──────────────────────────────────────────────────────
│  gh_api(path) -> dict|list|None     single subprocess.run wrapper:
│    ["gh","api",path], timeout=30, check=False; None on non-zero/
│    timeout/bad JSON  (error class G)
│  fetch_org_repos(denylist) -> [str]        1 paged call (AC1/D5)
│  map_issue(repo,item) -> dict              pure, excludes pull_request items
│  map_pr(repo,item) -> dict                 pure, draft→'draft', else 'open'
│  fetch_issues_and_prs(repos) -> {issues,prs,counts}   2N calls, capped newest-first
├─ CRON LAYER ───────────────────────────────────────────────────
│  ms_to_iso(ms) -> "…Z"                     pure (AC2)
│  humanize_schedule(kind, expr, tz, every_ms) -> str   pure (AC2)
│  extract_cron_jobs(db_path) -> list[dict]  mode=ro URI, whitelisted
│                                            projection, ORDER BY name
├─ PIPELINE LAYER ───────────────────────────────────────────────
│  HEADER_RE = ^## (\d\d:\d\d) \[([a-z-]+)\] .* \[([a-z ]+)\] …$
│  parse_handoff_tail(path) -> entry|None    latest matching header line
│  status_from_entry(status_word, age_days)  done/pass→pass, fail→fail,
│                                            blocked→idle, progress→running,
│                                            ≥30d stale→idle (AC4)
│  extract_pipeline(projects_dir) -> list[dict]  ≤1 per known worker (AC4)
├─ AGENTS LAYER ────────────────────────────────────────────────
│  status_from_age(minutes) -> active|idle|dormant      <60min/<7d/≥7d (D3)
│  extract_agents(agents_dir, now=None) -> list[dict]   mtimes only;
│    last_active=max mtime, sessions_24h=count(mtime>now-24h),
│    tokens_24h=None, budget_daily defaults (AC5); roster = seed ∪ dirs
├─ REGISTRY + ORCHESTRATION ────────────────────────────────────
│  SOURCES ordered list of (section_key, fn(data,cfg) -> new_value):
│    issues/prs → projects → pipeline → cron_jobs → agents
│  sanitize_error(exc) -> str     AT CAPTURE (gate blocker 1):
│    collapse whitespace → redact expanduser("~") prefix and
│    absolute-path runs (/… segments ≥2 chars) → truncate ~200 chars
│  run_source(key, fn, data, stamps, errors, now_iso):
│    try: data[key]=value; stamps[key]=now; errors.pop(key,None)
│    except Exception as e: errors[key]={error:sanitize_error(e),at:now}
│                            (data[key] + stamps[key] untouched)
│  guard_output(data) -> None|raise          serialized grep (AC3/AC15)
│  atomic_write(path, text)                  serialize → sibling tmp
│                                            file → os.replace (§1.2)
│  main()                                    unchanged contract otherwise
└────────────────────────────────────────────────────────────────
```

Existing `compute_specs` / `infer_pipeline_owner` stay as-is (projects filesystem logic preserved, AC6);
projects enrichment moves inside a source function so its `open_issues` comes from AC1's counts.

### 1.2 Last-good cache strategy — **the input file IS the cache**

Decision: retained last-good values live in `data/swarm.json` itself. No sidecar state file.

- On success: replace section value + stamp `sections_updated_at[section]`.
- On failure: leave both `data[section]` and `sections_updated_at[section]` exactly as read from the input file; add `source_errors[section]`.
- Both maps are seeded from the input file each run (`setdefault`), so a previously-failed section's old stamp persists truthfully until its source next succeeds; a recovered section's error entry is cleared.

Alternatives considered:
- *Sidecar `.last-good.json`*: rejected — violates AC14's "never writes outside data/swarm.json", adds a second artifact to deploy, and git history of swarm.json already gives deep last-good for free.
- *In-memory only*: rejected — process dies between runs; retention must survive restarts.

Merge/ordering rule: `issues+prs` fetched first because projects (AC6) consumes their counts; all other sources independent. Fixed order keeps failure blast radius deterministic.

**Atomic write — gate blocker 2.** Because this design writes the file every hourly run *even degraded* (DR-A makes the file the cache), a torn write is catastrophic: invalid JSON ⇒ next run exits 1, dashboard fetch fails, last-good destroyed. `main()` therefore never calls bare `write_text`: serialize once → write to a sibling tmp file in the same directory (`swarm.json.tmp-<pid>`) → `os.replace(tmp, DATA_FILE)` (atomic on POSIX). AC14 note: a transient same-dir tmp consumed by the replace **is part of writing data/swarm.json itself**, not a second persistent artifact — it does not violate AC14's letter ("never writes outside data/swarm.json"); no other location is ever touched.

Exit codes (AC10): **0 whenever the file was written**, even if every source failed (truth lives in `source_errors`). Exit 1 only for: missing/unreadable DATA_FILE (existing behavior), unwritable output, or guard violation.

**Error-string hygiene — gate blocker 1.** `source_errors[<section>].error` is published publicly, and raw `str(OSError)` embeds `/home/lex/…` paths. Sanitization happens **at capture** inside `sanitize_error` (whitespace-collapsed, home prefix + absolute-path runs redacted, ~200-char truncate) so every error string entering the maps is already safe to publish. The serialized-output grep (`guard_output`, class V) stays as defense-in-depth backstop — with capture-time sanitization it should never fire; if it does, that is an exporter bug and refusing to publish remains correct.

### 1.3 SQLite read-only access pattern

```python
con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
rows = con.execute(
    f"SELECT {','.join(CRON_COLUMNS)} FROM cron_jobs ORDER BY name"
).fetchall()
```

- `CRON_COLUMNS = (name, enabled, schedule_kind, schedule_expr, schedule_tz, every_ms,
  next_run_at_ms, last_run_at_ms, last_run_status, consecutive_errors)` — enforced as the
  **SELECT projection, not a post-filter**: future schema drift cannot leak payload columns even if code changes elsewhere (defense-in-depth behind AC3).
- Never `SELECT *`. Single short-lived connection, closed in `finally`; reader-only so gateway concurrency needs no retry loop — worst case `database is locked` becomes error class S below and self-heals next hour.
- Verified live: ro URI blocks writes at engine level (baseline probe).

### 1.4 Failure taxonomy → spec behavior

| Class | Detection | sections_updated_at | section data | source_errors | Exit |
|---|---|---|---|---|---|
| **G** gh non-zero / timeout / bad JSON | returncode≠0, TimeoutExpired, JSONDecodeError | untouched | last-good kept | `{issues,prs}` entry added | 0 (AC10) |
| **R** repos listing fails | class G on org call | untouched | last-good kept | issues+prs entries | 0 |
| **S** SQLite missing/corrupt/locked | OperationalError, DatabaseError | untouched | last-good kept | cron_jobs entry | 0 (AC10) |
| **A** agents dir absent/unreadable | not is_dir() / OSError during scan | untouched | last-good kept | agents entry | 0 |
| **E** legitimately empty (0 open issues/PRs, empty sessions dir) | successful fetch, len==0 | **fresh stamp** | replaced with [] | none — emptiness ≠ failure | 0 (AC11) |
| **M** malformed handoff-log line | regex no match | n/a | skip silently | none | 0 (AC4) |
| **V** guard violation (forbidden substring in output) | guard_output() pre-write | — | **no write at all** | — | **1** — exporter bug, never publish |

All `source_errors[].error` strings pass through `sanitize_error` at capture (§1.2), so classes G/R/S/A publish redacted, truncated messages only. Class V is a backstop that should be unreachable once sanitization is in place.

Class E vs G/S/A distinction is structural, not ad-hoc: only an exception raised inside a source fn marks failure; an empty-but-successful result flows through the success path (AC11 falls out of `run_source`'s shape).

### 1.5 gh api call budget (AC19)

```
1            GET orgs/moo-swarm/repos?per_page=100   (N < page size ⇒ 1 page)
+ N × 2      per repo: /issues?state=open (map_issue drops pull_request items)
                       /pulls?state=open  (draft flag lives here)
= 1 + 2N calls/run; today N=16 ⇒ 33/hr  « 5000/hr authenticated;
  bound ≤ 40 holds for any N ≤ 19
```

Denylist (default `.github`) shrinks N further. Gate correction: the org has **16** project repos,
not spec D5's 17 — formula unaffected. Tests stay **symbolic in N**: the budget test counts mocked
`subprocess.run` calls scoped to the gh layer only (`fetch_org_repos` + `fetch_issues_and_prs`;
`infer_pipeline_owner`'s git invocations share the same seam and must NOT be counted), over a
fixture repo list, asserting `calls ≤ 40` with this formula in a comment beside it.

### 1.6 Dashboard wiring (AC12–13)

One helper + one constant, additive to dashboard.js:

```js
SECTION_SOURCES = {           // dashboard section id ← swarm.json stamp keys
  'active-projects': ['projects'], 'pipeline-status': ['pipeline'],
  'cron-jobs': ['cron_jobs'],     'issues-prs': ['issues','prs'],
  'agent-health': ['agents'],     'agent-budget': ['agents']
}                             // spending-usage intentionally unmapped (F2 seed)
applySectionStaleness(data)   // called from renderFromData after renders
```

Marker: lazily created `.section-stale` chip in each section header, shown when any mapped
stamp is >120 min old or the section appears in `source_errors`; removed when fresh.
Absent maps ⇒ zero DOM writes ⇒ byte-identical behavior today (AC12 backward compat).
`issues-prs` goes stale if either issue or pr stamp is bad; `agent-budget` shares the agents
stamp since it renders the same array. Global badge logic untouched — it still timestamps the file (D4).

### 1.7 CI wiring

None new. lint.yml stays (its py_compile covers the extended module automatically — AC17).
deploy-pages.yml unchanged (already copies data/swarm.json). Exporter remains host-cron only
(SQLite + agents dir are host-local; DEF-3 tracks the runner question).

### 1.8 UX states covered

No ux-design.md exists for this feature (spec-driven); mapping SKILL's state matrix onto what ships:
loading (existing skeleton loaders, untouched), success (fresh stamps, green chips), empty (AC11 arrays
render existing EMPTY_MESSAGES), error/stale (new per-section amber/red markers, §1.6), retry
(existing 3600s refresh interval re-fetches; a recovered source clears its own error chip).

---

## 2. Rollout order (each step keeps both suites green)

1. Env config + constants (`AGENT_META`, `WORKER_ROLES`, `CRON_COLUMNS`, guard lists) — no behavior change.
2. Pure helpers: `ms_to_iso`, `humanize_schedule`, `status_from_age`, `map_issue`, `map_pr` + unit tests.
3. Source extraction fns (`extract_cron_jobs`, `extract_pipeline`, `extract_agents`,
   `fetch_issues_and_prs`) + fixture tests (temp SQLite, temp trees, mocked gh).
4. `SOURCES` registry + `run_source` (+ `sanitize_error` at capture) + map merge/seeding in `main()` + atomic `os.replace` write + merge/failure/sanitizer tests (AC9–11, gate blockers 1–2).
5. `guard_output` + secrets-guard tests (AC3/AC15) wired just before write.
6. Dashboard `SECTION_SOURCES` + `applySectionStaleness` + smoke.test.js extensions (AC12–13).
7. AC19 budget assert + README handoff notes to Mokash (AC20 content listed in spec §5).

## 3. Test plan — coverage baseline & AC-to-test traceability

**Baseline:** 7 python unittest + 2 node --test, all green (invocation caveat F-1).
Planned per the table below: **33 new python tests + 2 new JS ≈ 44 total**
(32 budgeted at gate + the unbudgeted gate carry-forward atomic-write test;
(QA gates by the table, not this prose — the table is authoritative). Fixtures over mocks where cheap:
real temp SQLite DBs, real temp `.moo-swarm` trees, `os.utime` mtimes; `mock.patch` only for gh
(`subprocess.run`) and clock (`NOW`-style params defaulting to real time).

| AC | Test file | Test name | Status |
|---|---|---|---|
| AC1 | test_export_data.py | GhLayerTest::test_org_repos_single_paged_call_respects_denylist | written |
| AC1 | test_export_data.py | GhLayerTest::test_map_issue_fields_and_excludes_pull_request_items | written |
| AC1 | test_export_data.py | GhLayerTest::test_map_pr_draft_and_open_status | written |
| AC1 | test_export_data.py | GhLayerTest::test_caps_50_newest_first_overall | written |
| AC2 | test_export_data.py | CronExtractionTest::test_cron_expr_with_tz_becomes_schedule_human | written |
| AC2 | test_export_data.py | CronExtractionTest::test_every_ms_rendered_human_readable | written |
| AC2 | test_export_data.py | CronExtractionTest::test_disabled_job_reports_status_disabled | written |
| AC2 | test_export_data.py | CronExtractionTest::test_ok_and_fail_status_from_last_run_status | written |
| AC2 | test_export_data.py | CronExtractionTest::test_ms_to_iso_utc_z_and_next_run_consecutive_errors | written |
| AC2 | test_export_data.py | CronExtractionTest::test_missing_db_raises_operational_error | written |
| AC3+AC15 | test_export_data.py | SecretsGuardTest::test_serialized_output_has_no_forbidden_substrings_or_token_patterns | written |
| AC15 | test_export_data.py | SecretsGuardTest::test_source_errors_error_strings_redact_home_prefix_and_absolute_paths_truncate_200c | written |
| AC10 | test_export_data.py | MergeAndFailureTest::test_path_bearing_exception_lands_redacted_in_published_map | written |
| AC3 | test_export_data.py | CronExtractionTest::test_output_keys_are_whitelist_even_when_private_columns_populated | written |
| AC4 | test_export_data.py | PipelineExtractionTest::test_latest_header_line_wins_per_worker | written |
| AC4 | test_export_data.py | PipelineExtractionTest::test_status_mapping_done_pass_fail_blocked_progress | written |
| AC4 | test_export_data.py | PipelineExtractionTest::test_malformed_log_skipped_without_failing_run | written |
| AC4 | test_export_data.py | PipelineExtractionTest::test_worker_inactive_30d_falls_back_to_idle_with_last_run | written |
| AC5 | test_export_data.py | AgentsScanTest::test_last_active_max_mtime_sessions_24h_count | written |
| AC5 | test_export_data.py | AgentsScanTest::test_unknown_dir_gets_neutral_meta_roster_is_union | written |
| AC5 | test_export_data.py | AgentsScanTest::test_status_thresholds_active_idle_dormant | written |
| AC5 | test_export_data.py | AgentsScanTest::test_tokens_24h_is_null_honest_gap | written |
| AC6 | test_export_data.py | MergeAndFailureTest::test_project_open_issues_come_from_issues_fetch_not_extra_call | written |
| AC7 | test_export_data.py | SchemaCompatTest::test_required_keys_and_version_2_on_every_success | written |
| AC8 | test_export_data.py | SchemaCompatTest::test_main_against_seed_shaped_fixture_preserves_custom_user_fields | written |
| AC9 | test_export_data.py | MergeAndFailureTest::test_success_stamps_real_fetch_time_updated_at_stays_file_time | written |
| AC10 | test_export_data.py | MergeAndFailureTest::test_failed_source_keeps_lastgood_data_stamp_records_error_exit_zero | written |
| AC10 | test_export_data.py | MergeAndFailureTest::test_global_updated_at_advances_despite_partial_failure | written |
| AC11 | test_export_data.py | MergeAndFailureTest::test_empty_source_is_success_with_fresh_stamp_no_error | written |
| AC14 | test_export_data.py | MergeAndFailureTest::test_serialization_failure_mid_write_leaves_original_swarm_json_byte_identical (gate carry-forward: blocker 2 crash-safety proof) | written |
| AC14 | test_export_data.py | CronExtractionTest::test_connect_uses_readonly_mode_uri | written |
| AC16 | test_export_data.py | (whole extension; existing 7 kept as regression) | written |
| AC17 | both suites | suite-level green runs in gate command | written |
| AC18 | test_export_data.py | EnvConfigTest::test_env_vars_override_defaults | written |
| AC19 | test_export_data.py | GhLayerTest::test_call_budget_le_40_documented_formula_counter_scoped_to_gh_layer_only | written |
| AC13 | smoke.test.js | smoke: stale stamps + one source_errors produce markers on exactly those sections | written |
| AC12 | smoke.test.js | smoke: fixture without maps renders identically, no markers, badge unchanged | written |
| AC12 | smoke.test.js | existing 2 boot/dark-mode tests keep passing (regression) | written |

**Known gaps / pending:** every row above is `written` as of the build (2026-08-24, resumed run);
Bagnik gates on this table being fully `written` at code QA. Guard test (V class) covers
write-blocking path but not a fuzz corpus — accepted (whitelist projection is the primary defense).

## 4. Decisions summary (alternatives in §1.2)

- **DR-A:** last-good cache = input file itself (sidecar rejected: AC14, deploy cost, git history already retains).
- **DR-B:** whitelist via SELECT projection, not post-filter (schema-drift proof).
- **DR-C:** single-file module grows layers in place; no package split (importlib pattern, DR-2 stdlib precedent).
- **DR-D:** exit 0 on partial success is structural via `run_source` try/except; exit 1 reserved for I/O + guard violations.
- **Open-question defaults chosen for build:** Q1 show discovered dirs w/ neutral meta (fold stays owner's); Q2 scan whole org minus denylist; Q5 disabled jobs shown grey. Owner can override later without schema change.

---

## Revision 1 — 2026-08-24 (post-gate amendments)

Bagnik test gate on this plan returned **FAIL**: two blockers, four advisories. All folded in above; deltas:

| Item | Amendment | Where |
|---|---|---|
| **Blocker 1 (PII)** — `source_errors[].error = str(e)` unsanitized; OSError messages embed `/home/lex/…` paths and the maps are published | `sanitize_error()` applied **at capture** inside `run_source`: whitespace-collapsed, `expanduser("~")` prefix + absolute-path runs redacted, ~200-char truncate. Class V exit-1-no-write demoted to unreachable defense-in-depth backstop, not the primary PII control. Named tests added: path-bearing exception lands redacted in published map; sanitizer redaction/truncation unit test | §1.1 registry block, §1.2 "Error-string hygiene", §1.4 table note, 2 new AC10/AC15 table rows |
| **Blocker 2 (integrity)** — no atomic write; degraded runs still write hourly; torn write destroys DR-A cache + dashboard fetch | `atomic_write()`: serialize once → sibling tmp file same dir → `os.replace`. Explicit AC14 ruling: transient consumed tmp **is part of writing data/swarm.json itself**, not an outside write | §1.2 "Atomic write", §1.1 `atomic_write` line, rollout step 4 |
| Advisory A | Org repos corrected 17 → **16**; budget math symbolic in N (`1+2N ≤ 40 ⇔ N ≤ 19`; today 33/hr); tests fixture-driven in N | §0 baseline row, §1.5 |
| Advisory B | Test counts re-derived from the authoritative table: gate-cited 30 new python / ≈41 total grew to **32 / ≈43** because blocker 1 mandates two named tests; prose now matches table | §3 intro |
| Advisory C | AC19 budget-counter scoped to the gh layer only — `infer_pipeline_owner`'s git calls share the `subprocess.run` seam and must not be counted | §1.5, AC19 table row |
| Advisory D | AC20 (README exporter section) has no automated test; verified manually at code QA | Known gates below |

**Known gates:** AC20 manual verification happens during Bagnik code QA (no automated assertion possible for prose quality). All other ACs carry named tests per the table.

No spec changes required — both blockers are implementation-discipline fixes fully compatible with AC9–15 as written.
