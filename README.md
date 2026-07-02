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
  │   ├── read swarm project files
  │   ├── query OpenClaw internals
  │   ├── fetch GitHub API for issues/PRs
  │   └── generate data/swarm.json
  │
  └── git push to github.com/moo-swarm/halo
       │
       └── GitHub Pages auto-deploys from main
```

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

## File Structure

```
halo/
├── index.html        ← Entry point
├── styles.css        ← All CSS
├── dashboard.js      ← All JS (IIFE)
├── data/
│   └── swarm.json    ← Pre-baked data
├── .nojekyll         ← Disable Jekyll on Pages
├── CNAME             ← Custom domain placeholder
└── README.md         ← This file
```

## License

MIT