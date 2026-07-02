# Research Synthesis — Halo Dashboard v1

> Compiled from 20 Veles research sub-agents. All 20 completed.
> Time: 2026-07-03 00:07–00:40, ~33 min total research.

---

## Top External Examples

| Project | Stars | Relevance | URL |
|---------|-------|-----------|-----|
| **org-metrics-dashboard** | ~500 | **Most directly relevant** — GitHub's own OSPO dashboard for WHO. Actions → JSON → Pages. Does exactly what Halo needs. | `github.com/github-community-projects/org-metrics-dashboard` |
| **Upptime** | 16K+ | Gold standard for GitHub-native status pages. Svelte + GHA + Issues. Used by Canonical. | `github.com/upptime/upptime` |
| **cState** | 2.5K | Hugo-based static status page. YAML-driven. Incident management. | `github.com/cstate/cstate` |
| **Tabler** | 41K | Most popular dashboard template. Bootstrap 5, MIT, dark mode, 70+ components. | `github.com/tabler/tabler` |
| **Gentelella v4** | 21K | Vanilla JS + Vite 8, no Bootstrap/jQuery, MIT, PWA-ready, dark/light. Fresh 2026 rebuild. | `github.com/ColorlibHQ/gentelella` |
| **Keen Dashboards** | 11K | CSS Grid layouts — demo on GitHub Pages itself. Chart.js compatible, no build step. | `github.com/keen/dashboards` |
| **someimportantcompany/status-page** | ~1K | Jekyll-based static status page. Config-driven. | `github.com/someimportantcompany/status-page` |

**Verdict:** Our architecture matches `org-metrics-dashboard` most closely. For the frontend, borrow Keen Dashboards' simplicity (CSS Grid, no build step) or Tabler's component library if we add a build step.

---

## Tech Stack Recommendations

| Concern | Recommended | Why |
|---------|-------------|-----|
| **Layout** | CSS Grid with `grid-template-areas` | Mobile-first, 3 col → 1 col. No framework. |
| **Charts** | Chart.js v4 (CDN) | Already decided. 5M weekly downloads. |
| **Pipeline diagram** | Mermaid.js v11 (CDN) | Text-to-diagram, style nodes by status, dark theme. No JS coding for the diagram. |
| **Markdown rendering** | marked (CDN ESM) | Zero deps, GFM tables, fastest parser. + DOMPurify for XSS safety. |
| **YAML parsing** | js-yaml v5 (CDN) | Most established browser YAML lib. |
| **Table filter/sort** | List.js (~10KB) or vanilla | List.js adds search+sort+filter with zero deps. Vanilla ~50 lines works for <500 rows. |
| **Freshness badge** | `Intl.RelativeTimeFormat` (native) | Zero-dependency. Works in all modern browsers. |
| **Theme toggle** | CSS custom properties + prefers-color-scheme + localStorage | Standard three-layer pattern. FOUC prevention via inline `<script>` in `<head>`. |
| **Status dots** | Pure CSS (pulse animation) + text label | Never colour alone — use icon + text label for accessibility. |

---

## Data Pipeline Architecture

```
┌──────────────────────────────────────┐
│  Moo Swarm Host (cron: hourly)      │
│                                      │
│  moo-export-data.sh:                 │
│  ├── Read _align-rail/projects/      │
│  ├── Read cron/jobs.json             │
│  ├── Read OpenClaw session JSONL     │
│  │   (usage.tokens, sessions)        │
│  ├── Run gh api for issues/PRs       │
│  ├── Generate data/swarm.json        │
│  ├── git push to data/export branch  │
│  │   (--force-with-lease, flock)     │
│  └── Triggers GitHub Pages rebuild   │
└──────────┬───────────────────────────┘
           │ push
           ▼
┌──────────────────────────────────────┐
│  github.com/moo-swarm/halo           │
│                                      │
│  GitHub Pages (auto-deploy on push)  │
│  ├── index.html (vanilla JS)         │
│  ├── styles.css                      │
│  ├── data/swarm.json (auto-generated)│
│  └── .nojekyll                       │
└──────────────────────────────────────┘
```

### Key details from research:
- **Locking:** `flock -n` prevents overlapping cron runs
- **Branch strategy:** Force-push to `data/export` branch; never touch `main`
- **No-op guard:** Check `git status --porcelain` — skip commit if nothing changed
- **Retry:** Transient push failures — 3 retries with exponential backoff
- **Spending data:** OpenClaw stores per-turn tokens in `~/.openclaw/agents/*/sessions/*.jsonl` (usage.totalTokens). Cost field populates only with pricing config. Use `/usage cost` command or direct JSONL parsing.
- **Agent last-active:** Query `sessions_list` or parse session JSONL timestamps on the host.

---

## Design Decisions from Research

### Theme toggle implementation:
1. Inline `<script>` in `<head>` reads `localStorage` → falls back to `prefers-color-scheme` → sets `color-mode` attribute on `<html>`
2. CSS custom properties for all colours, scoped to `:root[color-mode="light/dark"]`
3. `<meta name="color-scheme" content="light dark">` for browser UI
4. Toggle button with `aria-label` that says what WILL happen (screen reader friendly)
5. Listen for OS-level changes — only auto-switch if no `localStorage` override

### GitHub Pages config:
- Add `.nojekyll` (prevents Jekyll processing on plain HTML)
- Custom domain: A records → `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
- OG tags for Telegram: `og:title`, `og:description`, `og:image` (1200×630, absolute HTTPS URL)

### Pipeline visualization:
- Mermaid.js flowchart with coloured nodes by status
- Programmatic rendering from JSON data (not static Mermaid definition)
- Dark theme via `mermaid.initialize({ theme: 'base', themeVariables: {...} })`
- Fallback: plain status badges row (no JS)

### Data freshness:
- Native `Intl.RelativeTimeFormat` — outputs "3 minutes ago", "yesterday", etc.
- Badge in header: green dot + relative time + hover exact timestamp
- Auto-refresh: `setInterval` at 10s (sub-minute) / 60s (longer)

### Accessible tables (Issues & PRs):
- `role="grid"` with roving tabindex
- `aria-sort` on sortable column headers
- Filter controls grouped with `<fieldset>` + `<legend>`
- Focus management on filter: move to first result row or announce count in live region

### Performance targets:
- FCP < 1.5s, LCP < 2.5s, TTI < 3.0s
- < 500 KB total, < 15 requests
- Lazy-load Chart.js only when chart section enters viewport (Intersection Observer)
- Pre-minify with `npx terser` / `npx clean-css-cli` (zero-install)

### Project health indicators (🟢🟡🔴):
- **🟢 Active**: Feature work in last 7d, last commit < 7d, issues < 5
- **🟡 Stalled**: 7–30d no activity, or issues 5–15
- **🔴 Dormant**: 30d+ no activity, or issues > 15
- CHAOSS-inspired: issue response time, release freshness, PR merge rate (phase 2)

---

## Updated Data Schema

Extended `data/swarm.json` with fields discovered during research:

```json
{
  "updated_at": "2026-07-03T12:00:00Z",
  "refresh_interval": 3600,
  "projects": [ ... ],
  "pipeline": [
    {
      "agent": "veles",
      "role": "Research",
      "emoji": "🐍",
      "status": "pass",
      "last_run": "2026-07-03T10:00:00Z",
      "workflow_url": "https://github.com/moo-swarm/aeroplasty/actions/workflows/veles.yml",
      "badge_url": "https://img.shields.io/github/actions/workflow/status/moo-swarm/aeroplasty/veles.yml"
    }
  ],
  "issues": [ ... ],
  "prs": [ ... ],
  "cron_jobs": [ ... ],
  "spending": {
    "total_tokens_7d": 1234567,
    "cost_7d": 2.45,
    "cost_30d": 10.20,
    "daily": [...],
    "data_source": "openclaw_jsonl",
    "pricing_configured": false
  },
  "agents": [
    {
      "name": "moo",
      "emoji": "🐮",
      "role": "Orchestrator",
      "status": "active",
      "last_active": "2026-07-03T10:30:00Z",
      "sessions_24h": 12,
      "tokens_24h": 45000
    }
  ],
  "meta": {
    "version": "1.0",
    "generated_by": "moo-export-data.sh",
    "export_host": "lex-agent-swarm",
    "openclaw_version": "24.18.0"
  }
}
```

---

## Summary of Changes Required in Spec

| Section | Change |
|---------|--------|
| **Architecture** | Add `data/export` branch strategy, `flock` locking, retry logic |
| **Pipeline Status** | Use Mermaid.js + shields.io badges. Programmatic render from JSON. |
| **Active Projects** | Apply CHAOSS-inspired health scoring |
| **Table (Issues)** | Use List.js or vanilla filter; add a11y attributes |
| **Spending** | Parse OpenClaw JSONL; note pricing config requirement |
| **Header** | Add data freshness badge using `Intl.RelativeTimeFormat` |
| **Design** | Dark theme Mermaid config; `.nojekyll`; OG tags |
| **Performance** | Lazy load Chart.js; minify CSS/JS; Intersection Observer |
| **Accessibility** | Full a11y checklist from research |
| **Deferred** | Move `Observable Framework` to stretch goals; remove from deferred |