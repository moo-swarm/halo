# PROJECT.md — Halo

- **Name:** Halo
- **Purpose:** GitHub Pages dashboard showing live status of the moo-swarm organisation — active projects, tasks, issues, regular jobs, spending/usage, agent health
- **Slug:** halo

## Code

- **Location:** `github.com/moo-swarm/halo`
- **Stack:** Vanilla HTML5 + CSS3 (Tailwind via CDN or plain CSS) + JavaScript (Chart.js for charts), GitHub Actions for data fetching
- **Run / build:** `npm run build` (builds static site to `docs/` or root for GitHub Pages); or pure static — open `index.html` locally

## Pipeline config

- **Test command:** `npm run test:html` (validate HTML structure) or `npx htmlhint index.html`
- **Version files:** none (static site — no version bumps)
- **Lint / format:** `npx prettier --check .` or omit for pure static

## Notes

- Zero external services — everything runs on GitHub Actions + GitHub Pages + public GitHub API
- Data pipeline: GitHub Action fetches from `api.github.com/orgs/moo-swarm` and `api.github.com/repos/moo-swarm/*` → transforms to static JSON → committed to `gh-pages` branch or `data/` folder → frontend renders
- No backend, no database, no auth — fully static, public dashboard
- Inspired by `github-community-projects/org-metrics-dashboard` architecture
- Spending data comes from host-exported logs, not GitHub — needs a separate data source
- Site should load fast — data is compiled at build time, not fetched live from APIs

## Memory

Decisions, conventions, and design rationale accrue in `MEMORY.md`. Active features in `features/`.