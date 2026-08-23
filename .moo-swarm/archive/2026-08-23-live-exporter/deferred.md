# Deferred decisions — live-exporter

> defer.sh unavailable for non-`.tlk` feature paths; entries recorded manually per kit schema.

## DEF-1 — Live spending/cost panels
- **Status:** open
- **Deferred by:** requirements-eliciting (2026-08-23)
- **Trigger:** owner resolves privacy decision F2 (are real dollar/token figures publishable?)
- **Context:** Spending & Budget-by-Agent stay on seed/enrichment path this feature. Candidate
  sources once unblocked: host-side transcript parse (ccusage pattern) or OpenRouter activity pull.
  Cmok: implement nothing here for now; revisit when F2 resolved.

## DEF-2 — Cron heartbeat math (late/missed classification)
- **Status:** open
- **Deferred by:** requirements-eliciting (2026-08-23)
- **Trigger:** real `next_run` history accumulated post-launch of live cron export
- **Context:** Groundwork ships in this feature (`next_run`, `consecutive_errors` fields). The
  healthchecks-style on-time/late/missed panel and uptime strips are a follow-up.

## DEF-3 — GH-Actions export runner evaluation
- **Status:** open
- **Deferred by:** requirements-eliciting (2026-08-23)
- **Trigger:** proposal to migrate exporter off host-cron
- **Context:** Actions runner would lose SQLite + agents-dir sources (host-only); needs explicit
  trade-off decision before any migration.

## DEF-4 — Shields.io badges + OG meta tags from swarm.json
- **Status:** open
- **Deferred by:** requirements-eliciting (2026-08-23)
- **Trigger:** live sections shipped and trusted (this feature done)
- **Context:** Research C1/C4; near-zero effort follow-up, but only meaningful over live data.

## DEF-5 — Talaka `.tlk/features` projects in projects/pipeline scan
- **Status:** open
- **Deferred by:** requirements-eliciting (2026-08-23)
- **Trigger:** a swarm project using talaka appears outside `_align-rail_`
- **Context:** Scan currently keys on `.moo-swarm/features`; no known affected project today.
