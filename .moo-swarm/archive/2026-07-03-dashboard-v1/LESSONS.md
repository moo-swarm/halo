# Lessons — Halo Dashboard v1

## What went well

- **Architecture inversion**: Switching from GHA-pull to host-push was the right call — keeps the deploy simple (git push → Pages) and avoids cron-on-GHA complexity.
- **Graceful degradation as design principle**: Mermaid.js → plain-HTML fallback, Chart.js → sr-only table, vanilla JS filter → no List.js dependency. Every library has a fallback path.
- **FOUC prevention**: Inline `<script>` before CSS paint works perfectly for theme switching.
- **Single-file JS IIFE**: 12 commented sections, no build step, no module loader — easy to maintain for a status dashboard.

## What could be improved

- **Label/status filter dead code** (bagbug #1) — `setupFilters()` passes 3 args but `filterTableRows()` only uses 1. The UI dropdowns are misleading. Fix in v1.1.
- **A11Y gaps on cron section** (bagbug #2) — colour-only status dots missed during build. The spec explicitly says "never colour alone." Need a text label or `aria-label`.
- **sr-only spending table** (bagbug #3) — declared in HTML but never populated. Screen readers get no chart data.
- **CSS colour inconsistency** (bagbug #4) — status-tag classes use hardcoded hex instead of CSS custom properties. Dark mode still works (separate overrides) but the pattern is inconsistent.

## Process notes

- Bagnik's code QA caught 4 issues that Cmok didn't spot — good. All non-blocking, all fixable in v1.1.
- Spec-vs-tech-plan branch contradiction (main vs data/export) was caught at test gate — tech plan was canonical, spec was stale. Document drift earlier.
- The handoff-log pattern works well as a single source of truth for feature progression.

## Deferred to v1.1

- Label/status filter fixes
- Cron a11y fix
- Spending sr-table population
- CSS custom property refactor
- Export script (moo-export-data.sh)
- Mermaid dark theme config
- Chart.js dark-compatible colours
