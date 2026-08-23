# UX Design: Halo Dashboard v1

> **Feature:** `dashboard-v1`
> **Status:** Complete ✓
> **Designer:** Mokash 🧶 (documentation seat)
> **Build target:** Pure static HTML/CSS/JS, no build step

---

## 1. Design Philosophy

### Calm at the centre of motion

Halo is a swarm dashboard — it shows live, changing data from autonomous agents. But the
experience should feel **calm, not frantic**. The visual language reflects Moo's vibe:

- **Generous whitespace** — content breathes at every breakpoint
- **Subdued palette** — accent colour used sparingly for interactive elements and status
- **Gentle motion** — only pulse animations for live indicators, no bouncing or spinning
- **Predictable layout** — sections are always in the same position, regardless of data state
- **Skeleton-first** — layout shells render immediately; content fills in as data loads

### The first-time visitor

Halo is **public** (`moo-swarm.github.io/halo`). A visitor might be a curious developer,
an open-source contributor, or someone evaluating the project. They know nothing about
the swarm. Every section must:

1. **Announce itself** with a clear heading and brief 1-line description
2. **Use plain language** — "Active Projects" not "Project Portfolio View"
3. **Provide context** — status dots are paired with words, not used alone
4. **Link outward** — every entity is clickable to its source (GitHub, project docs)

---

## 2. Information Architecture

### 2.1 Page structure (top to bottom)

```
┌─────────────────────────────────────────────────────┐
│ HEADER                                              │
│  ├── Logo/Mascot (text: "Halo")                     │
│  ├── Title + tagline                                │
│  ├── Data freshness badge                           │
│  └── Theme toggle + GitHub link                     │
├─────────────────────────────────────────────────────┤
│ ROW 1: ACTIVE PROJECTS · PIPELINE · CRON JOBS       │
│  ├── Project table (sortable, health-coloured)      │
│  ├── Mermaid.js pipeline flowchart                  │
│  └── Cron schedule table                            │
├─────────────────────────────────────────────────────┤
│ ROW 2: ISSUES & PRs                                 │
│  ├── Filter bar (project, label, status)            │
│  ├── Issues table (top 10)                          │
│  └── PRs table (top 5)                              │
├─────────────────────────────────────────────────────┤
│ ROW 3: SPENDING · AGENT HEALTH                      │
│  ├── Chart.js bar/line chart + summary table        │
│  └── Agent status cards (grid)                      │
├─────────────────────────────────────────────────────┤
│ FOOTER                                              │
│  ├── Generated timestamp                           │
│  ├── "Built by Moo Swarm"                          │
│  └── Links to main repo + docs                     │
└─────────────────────────────────────────────────────┘
```

### 2.2 Section descriptions

| Section | Type | Priority | Data source | Empty state |
|---------|------|----------|-------------|-------------|
| **Header** | Banner | P0 | `data.swarm.updated_at` | N/A (always shows) |
| **Active Projects** | Table | P0 (hero) | `data.swarm.projects[]` | "No active projects" |
| **Pipeline Status** | Diagram | P0 | `data.swarm.pipeline[]` | No pipeline stages configured |
| **Issues & PRs** | Table + Filter bar | P1 | `data.swarm.issues[]`, `prs[]` | "All clear — no open issues" |
| **Cron Jobs** | Table | P1 | `data.swarm.cron_jobs[]` | "No periodic tasks configured" |
| **Spending & Usage** | Chart + Table | P2 | `data.swarm.spending` | "Data pending — spending tracking coming soon" |
| **Agent Health** | Cards | P1 | `data.swarm.agents[]` | "No agent data available" |
| **Footer** | Banner | P0 | `data.swarm.meta` | N/A |

---

## 3. Grid System & Layout

### 3.1 Breakpoints

| Breakpoint | Columns | Grid template | Container width |
|------------|---------|---------------|-----------------|
| ≥ 1024px (desktop) | 3 | `"projects pipeline cron"` in row 1, `"issues issues issues"` in row 2, `"spending agents agents"` (or similar) | 1200px max |
| 768–1023px (tablet) | 2 | Row 1 becomes `"projects pipeline"` + `"cron cron"`, others adjust | 96vw |
| < 768px (mobile) | 1 | All sections stack vertically | 100vw – 2rem |

### 3.2 CSS Grid areas (desktop)

```css
.site-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  grid-template-rows: auto;
  grid-template-areas:
    "header      header      header"
    "projects    pipeline    cron"
    "issues      issues      issues"
    "spending    agents      agents"
    "footer      footer      footer";
  gap: 1.5rem;
}
```

**Rationale:**
- **Projects × Pipeline × Cron** in one row — these are the three "what is the swarm doing?"
  views. Projects (scope) · Pipeline (process) · Cron (rhythm).
- **Issues & PRs** spans full width — it's the widest table and benefits from space.
- **Spending + Agent Health** share a row — both are secondary; agent health gets 2/3 width
  because it has more visual content (cards).
- **Gap is 1.5rem** — enough breathing room without wasted space.

### 3.3 Mobile stacking order

```
Mobile order (< 768px):
1. Header
2. Active Projects (most important)
3. Pipeline Status (visual anchor)
4. Cron Jobs (quick reference)
5. Issues & PRs (wide content)
6. Agent Health (quick glance)
7. Spending & Usage (least critical)
8. Footer
```

---

## 4. Component Tree

```
Page
├── <header>#halo-header
│   ├── <h1> "Halo"
│   ├── <p> "Moo Swarm Status"
│   ├── <div>#freshness-badge [role="status"]
│   │   ├── <span>.status-dot (green/grey CSS pulse)
│   │   └── <span>.relative-time (e.g. "updated 12 min ago")
│   ├── <button>#theme-toggle [aria-label]
│   └── <a> GitHub link [target="_blank" rel="noopener"]
│
├── <section>#active-projects [aria-labelledby]
│   ├── <header>
│   │   ├── <h2> "Active Projects"
│   │   └── <span>.data-age-badge
│   ├── <div>.skeleton-loader (loading state, CSS animation)
│   └── <table> [role="grid"]
│       ├── <thead>
│       │   ├── <th> "Project"
│       │   ├── <th> "Status" [aria-sort]
│       │   ├── <th> "Last Update"
│       │   └── <th> "Pipeline Stage"
│       └── <tbody>
│           └── <tr> per project
│               ├── <td> name + repo link
│               ├── <td> health dot + label
│               ├── <td> relative time
│               └── <td> stage name
│
├── <section>#pipeline-status [aria-labelledby]
│   ├── <header>
│   │   ├── <h2> "Pipeline Status"
│   │   └── <span>.data-age-badge
│   ├── <div>.mermaid-container
│   │   └── (rendered SVG from Mermaid.js)
│   ├── <div>.mermaid-fallback (hidden by default)
│   │   └── rows of status badges
│   └── <div>.skeleton-loader
│
├── <section>#cron-jobs [aria-labelledby]
│   ├── <header>
│   │   ├── <h2> "Regular Tasks"
│   │   └── <span>.data-age-badge
│   ├── <div>.skeleton-loader
│   └── <table>
│       ├── thead
│       └── tbody per cron job
│
├── <section>#issues-prs [aria-labelledby]
│   ├── <header>
│   │   ├── <h2> "Issues & Pull Requests"
│   │   └── <span>.data-age-badge
│   ├── <form>#filter-bar
│   │   ├── <fieldset>
│   │   │   ├── <legend class="sr-only">Filters</legend>
│   │   │   ├── <select> filter by project
│   │   │   ├── <select> filter by label
│   │   │   ├── <select> filter by status (open/closed)
│   │   │   └── <button>#clear-filters
│   │   └── <output>#result-count [aria-live="polite"]
│   ├── <div>.skeleton-loader
│   ├── <h3> "Open Issues"
│   ├── <table>#issues-table [role="grid"]
│   ├── <h3> "Open Pull Requests"
│   └── <table>#prs-table [role="grid"]
│
├── <section>#spending-usage [aria-labelledby]
│   ├── <header>
│   │   ├── <h2> "Spending & Usage"
│   │   └── <span>.data-age-badge
│   ├── <div>.chart-container
│   │   └── <canvas> [aria-hidden="true"]
│   ├── <table>.sr-only (screen reader companion)
│   ├── <div>.summary-stats
│   │   └── stat cards (tokens, cost, calls, active agents)
│   └── <div>.data-pending-placeholder (when no data)
│
├── <section>#agent-health [aria-labelledby]
│   ├── <header>
│   │   ├── <h2> "Agent Health"
│   │   └── <span>.data-age-badge
│   ├── <div>.agent-grid
│   │   └── <article>.agent-card per agent
│   │       ├── <div>.agent-emoji
│   │       ├── <h3>.agent-name
│   │       ├── <p>.agent-role
│   │       ├── <span>.status-indicator (dot + label)
│   │       ├── <p>.last-active
│   │       ├── <p>.sessions-count
│   │       └── <p>.tokens-count
│   └── <div>.skeleton-loader
│
└── <footer>#halo-footer
    ├── <p> "Generated: {timestamp}"
    ├── <p> "Built by Moo Swarm"
    └── <nav>
        ├── <a> GitHub
        ├── <a> Docs
        └── <a> Contributors
```

---

## 5. States

Every data-backed section has four states:

### 5.1 Loading state

**Visual:** Skeleton screen
- Grey rectangular blocks: `linear-gradient(90deg, ...)` shimmer animation
- Shapes match final content (rows for tables, rectangles for cards, a rough mermaid shape)
- `aria-busy="true"` on the container
- No spinner — shimmer only, less distracting

**Example — Active Projects skeleton:**
```
┌─────────────────────────────────────────┐
│ Active Projects                          │
│ ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐    │
│ │ ▓▓▓▓▓▓▓▓    ▓▓    ▓▓▓▓    ▓▓▓   │    │
│ │ ▓▓▓▓▓▓▓▓▓▓  ▓▓    ▓▓▓▓    ▓▓▓   │    │
│ │ ▓▓▓▓▓▓▓▓    ▓▓    ▓▓▓▓    ▓▓▓▓  │    │
│ └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘    │
└─────────────────────────────────────────┘
```

### 5.2 Loaded state

- Full content rendered
- Animations complete
- Interactive elements enabled
- `aria-busy="false"`

### 5.3 Empty state

- Section heading remains visible
- Body area shows contextual message
- Icon or simple illustration for visual weight
- No error decoration — empty is not an error

| Section | Empty message | Visual |
|---------|---------------|--------|
| Active Projects | "No active projects" | Box with dashed border |
| Pipeline | "No pipeline stages configured" | Dashed border box |
| Issues & PRs | "All clear — no open issues or PRs" | Green checkmark + text |
| Cron Jobs | "No periodic tasks configured" | Clock icon + text |
| Spending | "Data pending — spending tracking coming soon" | Hourglass + text |
| Agent Health | "No agent data available" | Dashed card grid |

### 5.4 Error state

- Rare — data is pre-baked, but JSON could be malformed or missing
- Section shows: title + "Data unavailable" + icon
- No stack traces or technical detail (public dashboard)
- Previous data is **stale-displayed**: if we have old data, show it with
  "(stale)" badge instead of error state
- Only show error state if there's zero data ever

**Visual:**
```
┌─────────────────────────────────────────┐
│ Active Projects            (stale)      │
│ ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐    │
│ │     ⚠️ Data temporarily           │    │
│ │        unavailable                 │    │
│ │     Last known: 2 hours ago       │    │
│ └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘    │
└─────────────────────────────────────────┘
```

---

## 6. Theme System

### 6.1 Colour tokens

Tokenised as CSS custom properties. Three layers of specificity:

```css
/* Layer 1: Default (light) */
:root {
  --color-bg: #ffffff;
  --color-surface: #f8fafc;
  --color-surface-elevated: #ffffff;
  --color-border: #e2e8f0;
  --color-text-primary: #0f172a;
  --color-text-secondary: #64748b;
  --color-text-muted: #94a3b8;
  --color-accent: #3b82f6;       /* blue-500 */
  --color-accent-hover: #2563eb; /* blue-600 */
  --color-success: #22c55e;      /* green-500 */
  --color-warning: #eab308;      /* yellow-500 */
  --color-danger: #ef4444;       /* red-500 */
  --color-running: #3b82f6;      /* blue-500 */
  --color-idle: #94a3b8;         /* slate-400 */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
  --shadow-md: 0 4px 6px rgba(0,0,0,0.07);
  --color-skeleton: #e2e8f0;
  --color-skeleton-shine: #f1f5f9;
}

/* Layer 2: Dark */
[color-mode="dark"] {
  --color-bg: #0f172a;
  --color-surface: #1e293b;
  --color-surface-elevated: #334155;
  --color-border: #334155;
  --color-text-primary: #f1f5f9;
  --color-text-secondary: #94a3b8;
  --color-text-muted: #64748b;
  --color-accent: #60a5fa;       /* blue-400 */
  --color-accent-hover: #93c5fd; /* blue-300 */
  --color-running: #60a5fa;      /* blue-400 */
  --color-idle: #64748b;         /* slate-500 */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.3);
  --shadow-md: 0 4px 6px rgba(0,0,0,0.4);
  --color-skeleton: #334155;
  --color-skeleton-shine: #475569;
}

/* Layer 3: System preference (fallback if no localStorage) */
@media (prefers-color-scheme: dark) {
  :root:not([color-mode="light"]) { /* same vars as [color-mode="dark"] */ }
}
```

### 6.2 Colour usage rules

| Element | Light | Dark | WCAG contrast |
|---------|-------|------|---------------|
| Body bg | `#ffffff` | `#0f172a` | N/A |
| Card bg | `#f8fafc` | `#1e293b` | N/A |
| Primary text | `#0f172a` | `#f1f5f9` | ≥ 7:1 on bg |
| Secondary text | `#64748b` | `#94a3b8` | ≥ 4.5:1 on bg |
| Accent (links, buttons) | `#3b82f6` | `#60a5fa` | ≥ 4.5:1 on bg |
| Success dot | `#22c55e` | `#22c55e` | Same green (≥ 3:1 paired with text) |
| Warning dot | `#eab308` | `#eab308` | Same yellow |
| Danger dot | `#ef4444` | `#ef4444` | Same red |

### 6.3 Theme toggle behaviour

1. **On first visit:** FOUC prevention script in `<head>` reads `localStorage.getItem('halo-theme')`.
   - If absent: checks `prefers-color-scheme: dark` → sets `[color-mode="dark"]` or light
   - If present: applies the stored value
2. **On toggle click:**
   - Toggle `[color-mode]` attribute on `<html>`
   - Persist to `localStorage.setItem('halo-theme', newValue)`
   - `aria-label` updates: "Switch to light mode" / "Switch to dark mode"
3. **On OS theme change event:**
   - `matchMedia('(prefers-color-scheme: dark)').addEventListener('change', ...)`
   - Only auto-switch if `localStorage` has no user override
4. **Transition:** 200ms ease-in-out on `background-color` and `color` only
   - Not all properties — performance

### 6.4 Dark mode considerations for components

| Component | Dark mode note |
|-----------|---------------|
| Chart.js | `Chart.defaults.color = '#94a3b8'` and `Chart.defaults.backgroundColor` array with dark-compatible colours |
| Mermaid.js | `mermaid.initialize({ theme: 'base', themeVariables: { primaryColor, primaryTextColor, lineColor, ... } })` matching dark palette |
| shields.io badges | Embedded URLs use `labelColor=...` parameter to match theme, or accept their default dark badge style |
| Card shadows | Lighter, more diffuse in dark mode — `rgba(0,0,0,0.4)` |

---

## 7. Interaction Design

### 7.1 Theme toggle

```
State: [☀️] Light mode active
Action: Click toggle
Result: → [🌙] Dark mode active, localStorage saved, transition animates
```

- `aria-label`: "Switch to dark mode" / "Switch to light mode"
- Touch target: minimum 44×44px
- Keyboard: Tab to focus, Enter/Space to toggle
- Icon: Sun/Moon SVG inline (no external icon font)

### 7.2 Table interactions (Issues & PRs)

**Filtering:**
- Select/dropdown `<select>` for project, label, status
- As selection changes, rows are filtered client-side
- Result count updates: `<output>` with `aria-live="polite"`
- "Showing 3 of 12 results" announcement
- Clear filters button resets all dropdowns

**Sorting:**
- Click column header → toggle ascending/descending
- `aria-sort` updates: "ascending" / "descending" / "none"
- Current sort indicator: ▲ or ▼ Unicode arrow

**Row click:**
- Entire row is clickable (link to GitHub issue/PR)
- Opens in new tab (`target="_blank" rel="noopener"`)
- Hover effect: background change + pointer cursor

### 7.3 Pipeline diagram

- Static rendered SVG (Mermaid.js) — no per-node clicks in v1
- Hover: title tooltip on each node showing "Last run: 2h ago"
- Full diagram fallback to badged row if Mermaid.js fails to load

### 7.4 Spending chart

- Chart.js renders bar chart (daily tokens) + optional line overlay (cost)
- Hover tooltip: date, tokens, cost
- Chart is `aria-hidden="true"` with screen-reader companion table
- Summary stats below chart: total tokens, cost, API calls

### 7.5 Data freshness badge

- Auto-updates every 10 seconds using `Intl.RelativeTimeFormat`
- Relative time: "just now" (< 1 min), "3 min ago", "2 hours ago", "yesterday"
- Hover: `<span title="2026-07-03 12:00 UTC">` shows exact timestamp
- Color: green dot if < 1h old, amber dot if 1–2h, red dot if > 2h
- `role="status" aria-live="polite"` — announced to screen readers when text changes

---

## 8. Responsive Behaviour

### 8.1 Desktop (≥ 1024px) — 3-column

```
┌─────┬──────┬──────┐
│ Prj │ Pipe │ Cron │  <- equal thirds
├─────┴──────┴──────┤
│ Issues & PRs      │  <- full width
├─────┬──────┬──────┤
│ Spd │ Agents      │  <- 1:2 ratio
└─────┴──────┴──────┘
```

### 8.2 Tablet (768–1023px) — 2-column

```
┌─────┬──────┐
│ Prj │ Pipe │
├─────┴──────┤
│ Cron       │
├────────────┤
│ Issues & PRs │
├─────┬──────┤
│ Spd │ Agts │
└─────┴──────┘
```

### 8.3 Mobile (< 768px) — 1-column

```
┌────────────┐
│ Projects   │
├────────────┤
│ Pipeline   │
├────────────┤
│ Cron       │
├────────────┤
│ Issues & PRs │
├────────────┤
│ Agents     │
├────────────┤
│ Spending   │
└────────────┘
```

**Mobile specifics:**
- Tables collapse to card-like rows (stacked `<dl>` or stacked `<div>` per item)
- Mermaid flowchart may need `{ direction LR }` → `{ direction TB }` for thin viewports
- Chart.js responsive: `responsive: true, maintainAspectRatio: true`
- Filter bar stacks vertically (label above dropdown)
- Card width fills container
- Padding: 1rem (vs 1.5rem on desktop)

---

## 9. Accessibility

### 9.1 ARIA landmarks

| Landmark | Element | Usage |
|----------|---------|-------|
| `banner` | `<header>` | Site header |
| `main` | `<main>` | Wraps all section content |
| `contentinfo` | `<footer>` | Site footer |
| `region` | Each `<section>` | Content sections, with `aria-labelledby` |

### 9.2 Live regions

| Region | `role` | `aria-live` | Purpose |
|--------|--------|-------------|---------|
| Freshness badge | `status` | `polite` | Announces relative time updates |
| Filter result count | `status` | `polite` | "Showing 3 of 12 results" |
| Error banner | `alert` | `assertive` | Only for critical JSON parse failures |

### 9.3 Colour + text pairs

Every status indicator has three layers:
1. **Shape/icon** — dot shape, emoji, icon
2. **Colour** — green/amber/red/blue/grey
3. **Text label** — "Active", "Stalled", "Dormant", "Pass", "Fail", "Running", "Idle"

Never rely on colour alone.

### 9.4 Keyboard navigation

- All `<select>` filters: Tab to focus, arrow keys to change
- Theme toggle: Tab + Enter/Space
- Table rows: Tab through links within rows (individual `<a>` per project/issue)
- No custom keyboard traps

### 9.5 Screen reader companion

- Charts: each `<canvas>` has `aria-hidden="true"` followed by a `.sr-only` `<table>` with the data
- Mermaid.js diagram: `aria-label` on container describing the pipeline flow
- Filter controls: grouped with `<fieldset>` and `<legend>` (visually hidden)
- Status dots: `aria-label="Status: active"` on the dot element, plus visible text label

---

## 10. Data Freshness & Auto-Update

### 10.1 Freshness badge mechanics

```javascript
function updateFreshness(isoString) {
  const now = new Date();
  const then = new Date(isoString);
  const diffMs = now - then;

  // Format using Intl.RelativeTimeFormat
  const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
  const units = [
    { name: 'second', ms: 1000 },
    { name: 'minute', ms: 60000 },
    { name: 'hour', ms: 3600000 },
    { name: 'day', ms: 86400000 },
  ];

  for (const unit of units) {
    if (Math.abs(diffMs) < unit.ms * 60) {
      const value = -Math.round(diffMs / unit.ms);
      return rtf.format(value, unit.name);
    }
  }
  // falls back to ISO date for older data
  return then.toLocaleDateString();
}
```

**Update intervals:**
- First 60 seconds: every 10 seconds (shows "just now" → "50 seconds ago")
- After 1 minute: every 60 seconds (shows "2 minutes ago" → "59 minutes ago")
- After 1 hour: every 5 minutes (shows "1 hour ago", "2 hours ago", etc.)

### 10.2 Dot colour by age

| Age | Dot colour | Code |
|-----|-----------|------|
| < 1 hour | `🟢` green | `var(--color-success)` |
| 1–2 hours | `🟡` amber | `var(--color-warning)` |
| > 2 hours | `🔴` red | `var(--color-danger)` |

---

## 11. Performance UX

| Technique | Implementation | Impact |
|-----------|---------------|--------|
| **FOUC prevention** | Inline `<script>` in `<head>` before CSS | Theme applied before paint |
| **Critical CSS inlined** | All above-fold styles in `<style>` block | No render-blocking CSS fetch |
| **Skeleton screens** | Each section has a skeleton shell in initial HTML | Instant layout, no CLS |
| **Lazy Chart.js** | Intersection Observer → dynamic `<script>` load | No chart JS until needed |
| **Font system stack** | `system-ui, -apple-system, ...` — no web fonts | Zero font download |
| **Resource hints** | `<link rel="preconnect">` to CDN hosts | Parallel DNS resolution |
| **Minified assets** | CSS/JS minified before push | Smaller payload |
| **No external API calls** | All data pre-baked in `data/swarm.json` | Zero runtime HTTP |

---

## 12. Error Handling UX

### 12.1 JSON load failure

If `data/swarm.json` fails to fetch (HTTP error, network issue, corrupt file):

1. Show banner at top: "Unable to load dashboard data" with retry button
2. Sections remain in skeleton state (never show empty or error if we just
   haven't fetched yet — show skeleton with a note)
3. Retry button re-fetches JSON and reinitialises

### 12.2 Partial data

Some sections may have data while others don't (data export produced incomplete JSON):

- Sections with data: render normally
- Sections missing data: show empty state with specific message
- Always show the age badge for whatever data exists

### 12.3 Mermaid.js failure

If Mermaid.js can't load from CDN or fails to render:

1. Hide `.mermaid-container`
2. Show `.mermaid-fallback` — plain HTML status badges in a row
3. No error shown to user — graceful degradation

### 12.4 Chart.js failure

If Chart.js fails to load:

1. Hide `<canvas>`
2. Show `.sr-only` table visibly (was hidden before)
3. Summary stats remain visible

---

## 13. Micro-interactions

| Element | Interaction | Feedback |
|---------|-------------|----------|
| Theme toggle | Click | 200ms background transition; icon swap |
| Table row | Hover | `background-color` transition 100ms |
| Table row | Click | Open new tab |
| Filter select | Change | Row filter instantly, count updates |
| Skeleton | Page load | Shimmer animation loops until data loaded |
| Freshness badge | Timer tick | Text updates every 10s/60s/5min |
| Status dot | Any | Pulse animation (CSS `@keyframes pulse-opacity`) |
| Card hover | Mouse over | Subtle shadow elevation (2px lift) |

---

## 14. Copy & Tone

- **Friendly but professional** — "Hey, here's what's happening" not "System Status Dashboard"
- **Section descriptions** in 1 sentence: "Active projects in the Moo swarm, with health and last activity."
- **Empty states** are helpful, not apologetic: "No issues — all clear!" not "There are no items to display."
- **Error states** are factual: "Data pending — spending tracking will light up in a future update."

### Example section descriptions:

| Section | Description |
|---------|-------------|
| Active Projects | "Live projects in the swarm — hover the health dot for details." |
| Pipeline Status | "The build chain from research to commit. Each stage shows its last run status." |
| Regular Tasks | "Scheduled jobs that keep the swarm humming along." |
| Issues & PRs | "Open issues and pull requests across all project repos. Filter by project or label." |
| Spending & Usage | "OpenClaw token usage and cost for the last 14 days." |
| Agent Health | "Each agent's current status and recent activity at a glance." |

---

## 15. Design Checklist (pre-build)

- [ ] All 13 acceptance criteria have UX coverage
- [ ] Every section has loading → loaded → empty → error states
- [ ] Dark theme passes all contrast checks
- [ ] Theme toggle works without FOUC
- [ ] Keyboard navigable end-to-end
- [ ] Screen reader can navigate by landmark
- [ ] Mobile viewport handles all sections without horizontal scroll
- [ ] Touch targets are ≥ 44×44px
- [ ] No colour-only status indicators
- [ ] All links have `target="_blank" rel="noopener"`
- [ ] Data freshness badge auto-updates
- [ ] Chart.js lazy-loaded, not blocking initial render
- [ ] Mermaid.js has a non-JS fallback
- [ ] Skeleton screens match final layout dimensions
- [ ] `color-mode` attribute set before first paint
- [ ] Empty states have meaningful messages
- [ ] Stale data degrades gracefully with "(stale)" badge