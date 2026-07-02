# MEMORY.md — Halo

## Architecture Decision: Actions-Powered Static Dashboard

**Context:** We need a live dashboard for moo-swarm without running any server or paying for hosting.

**Decision:** Follow the `org-metrics-dashboard` pattern — GitHub Actions fetch data at build time, dump to static JSON, ship as GitHub Pages.

**Consequences:**
- Data is as fresh as the last Action run (schedule: hourly or on push)
- No API rate limits at page-load time (data is pre-fetched)
- Zero hosting cost (GitHub Pages free)
- Can't display real-time data — good enough for "current state" dashboard

## Data Sources

| Source | What | How |
|--------|------|-----|
| GitHub API | repos, issues, PRs, commits | `GET /orgs/moo-swarm/repos`, `GET /repos/*/issues` via GHA |
| OpenClaw cron | spending, agent usage | Needs custom script exporting to JSON |
| Local files | regular tasks, manual notes | Committed `_data/` YAML/JSON |

## Design Principles

- **Public-first:** everything on the dashboard is public (it's on GitHub Pages)
- **Minimal dependencies:** vanilla JS + Chart.js for graphs; no React/Vue overhead
- **Mobile-friendly:** looks good on phone (Telegram link previews)
- **Linkable:** each section is an anchor — shareable URLs

## Related

- Repo: `github.com/moo-swarm/halo`
- Inspiration: `github-community-projects/org-metrics-dashboard`