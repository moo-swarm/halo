# Tech Plan — Halo Dashboard v1

> **Feature:** `2026-07-03-dashboard-v1`
> **Build seat:** Cmok 🐉
> **Based on:** `spec.md` (13 ACs) · `ux-design.md` (full UX spec) · `research-synthesis.md` (20-agent sweep)
> **Stance:** Zero build step, mobile-first, graceful degradation, FCP < 1.5s

---

## 1. File Structure

```
halo/                          # github.com/moo-swarm/halo (root of Pages)
├── index.html                 # Entry point — all HTML in one file
├── styles.css                 # All CSS — custom props, grid, components, responsive
├── dashboard.js               # All JS — data loading, rendering, interactivity
├── data/
│   └── swarm.json             # Pre-baked data (pushed by moo-export-data.sh)
├── mockups/                   # Design references (not shipped to Pages)
│   ├── desktop-full.html
│   ├── mobile-full.html
│   ├── section-states.html
│   ├── pipeline-states.html
│   ├── filter-interaction.html
│   └── README.md
├── .nojekyll                  # Prevents Jekyll processing on Pages
└── CNAME                      # (future) custom domain
```

**Rationale:** Single-file HTML keeps Pages deployment simple — no bundler, no routing. All CSS in one file avoids extra HTTP requests. JS in one file with clear section comments.

---

## 2. Module Organisation (`dashboard.js`)

The JS file is organised as a single IIFE with clearly commented sections. No module loader (no build step).

```
dashboard.js structure:
├── 1. Config & Constants
│   ├── REFRESH_INTERVAL = 3600
│   ├── SECTION_SELECTORS map
│   └── STATUS_COLORS map
├── 2. Data Loading
│   ├── loadDashboardData()          — fetch + parse swarm.json
│   ├── handleLoadError(err)         — show error banner + retry
│   └── renderFromData(data)         — dispatch to sections
├── 3. Freshness Badge
│   ├── initFreshnessBadge(isoTime)  — set up Intl.RelativeTimeFormat
│   └── updateFreshness()            — called by setInterval
├── 4. Active Projects
│   ├── renderProjects(data)         — build table HTML
│   ├── getHealthLabel(project)      — 🟢🟡🔴 logic
│   └── getHealthColor(project)      — CSS var mapping
├── 5. Pipeline
│   ├── renderPipeline(data)         — construct Mermaid def → render/fallback
│   ├── buildMermaidDefinition(d)    — flowchart LR string
│   ├── renderMermaid(def)           — mermaid.run/mermaid.render
│   └── renderPipelineFallback(d)    — plain badge row
├── 6. Issues & PRs
│   ├── renderIssues(data)           — List.js or vanilla filter table
│   ├── renderPRs(data)
│   ├── initFilters()                — project/label/status select bindings
│   └── filterTable()                — client-side row filter
├── 7. Cron Jobs
│   ├── renderCronJobs(data)         — schedule table
│   └── getCronStatus(job)           — status dot + label
├── 8. Spending
│   ├── renderSpending(data)         — Chart.js chart + summary table
│   ├── renderSpendingPending()      — "Data pending" placeholder
│   └── initChart(canvas, data)      — lazy-loaded via Intersection Observer
├── 9. Agent Health
│   ├── renderAgents(data)           — card grid
│   └── getAgentStatus(agent)        — status dot + label
├── 10. Theme System
│   ├── initTheme()                  — read localStorage, apply, listen
│   ├── toggleTheme()                — flip color-mode attr, persist
│   └── syncChartJSToTheme()         — update Chart.js defaults
├── 11. Helpers
│   ├── escapeHtml(str)              — XSS safety
│   ├── relativeTime(iso)            — Intl.RelativeTimeFormat wrapper
│   ├── skeletonHTML(type)           — generate skeleton shapes
│   └── showSection(id, state)       — manage aria-busy, visibility
└── 12. Init
    └── init()                       — DOMContentLoaded entry point
```

---

## 3. Component Tree (CSS Grid Areas)

Matches UX design faithfully:

```html
<body>
  <header id="halo-header" role="banner">
    <!-- title, tagline, freshness badge, theme toggle, GitHub link -->
  </header>

  <main>
    <!-- ROW 1: 3 columns on desktop, equal width -->
    <section id="active-projects" aria-labelledby="projects-heading">
    <section id="pipeline-status" aria-labelledby="pipeline-heading">
    <section id="cron-jobs" aria-labelledby="cron-heading">

    <!-- ROW 2: Full-width -->
    <section id="issues-prs" aria-labelledby="issues-heading">

    <!-- ROW 3: 1/3 + 2/3 -->
    <section id="spending-usage" aria-labelledby="spending-heading">
    <section id="agent-health" aria-labelledby="agents-heading">
  </main>

  <footer id="halo-footer" role="contentinfo">
    <!-- generated timestamp, "Built by Moo Swarm", links -->
  </footer>
</body>
```

**CSS Grid definition (desktop ≥ 1024px):**

```css
.site-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  grid-template-areas:
    "header   header   header"
    "projects pipeline cron"
    "issues   issues   issues"
    "spending agents   agents"
    "footer   footer   footer";
  gap: 1.5rem;
  max-width: 1200px;
  margin: 0 auto;
  padding: 1.5rem;
}
```

---

## 4. Data Flow

### 4.1 Page load lifecycle

```
DOMContentLoaded
  │
  ├── initTheme()
  │   └── Inline FOUC script already ran; initTheme syncs Chart.js
  │
  ├── Insert skeleton HTML into all section containers
  │   └── aria-busy="true" on each section
  │
  ├── fetch('data/swarm.json')
  │   │
  │   ├── Success → JSON.parse → renderFromData(data)
  │   │   ├── initFreshnessBadge(data.updated_at)
  │   │   ├── renderProjects(data.projects)
  │   │   ├── renderPipeline(data.pipeline)
  │   │   ├── renderIssues(data.issues, data.prs)
  │   │   ├── renderCronJobs(data.cron_jobs)
  │   │   ├── renderSpending(data.spending)        ← lazy: IntersectionObserver
  │   │   ├── renderAgents(data.agents)
  │   │   └── Remove skeleton, set aria-busy="false"
  │   │
  │   └── Failure → handleLoadError
  │       ├── Show banner: "Unable to load dashboard data"
  │       ├── Retry button → fetch again
  │       └── Keep skeleton with "retrying..." note
  │
  └── setInterval(updateFreshness, interval)
```

### 4.2 Section-level data flow

| Section | JSON path | Render strategy | Fallback if missing |
|---------|-----------|-----------------|---------------------|
| Active Projects | `data.projects[]` | Build `<table>` element, inject via `innerHTML` (sanitised) | Empty state: "No active projects" |
| Pipeline Status | `data.pipeline[]` | Construct Mermaid def → `mermaid.run()` → inject SVG | Fallback badge row (`.mermaid-fallback`) |
| Issues & PRs | `data.issues[]`, `data.prs[]` | Build `<tbody>` rows, attach filter listeners | "All clear — no open issues or PRs" |
| Cron Jobs | `data.cron_jobs[]` | Build `<table>` rows | "No periodic tasks configured" |
| Spending | `data.spending{}` | If `daily[]` exists → Chart.js bar chart; else placeholder | "Data pending — spending tracking coming soon" |
| Agent Health | `data.agents[]` | Build card `<article>` elements in grid | "No agent data available" |

### 4.3 Stale data degradation

If `data/swarm.json` loads but some sections are missing arrays:
- Sections with data: render normally
- Sections missing data: show contextual empty state
- Keep freshness badge showing `updated_at` from the JSON root

If `updated_at` is > 2× `refresh_interval` old:
- Show "(stale)" badge in section header alongside the section data
- Dot colour shifts to amber/red per UX design

---

## 5. Library Integration Patterns

### 5.1 Chart.js v4 (CDN)

```html
<!-- Lazy-loaded via Intersection Observer in dashboard.js -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4" defer></script>
```

**Loading pattern:**
```javascript
function renderSpending(spending) {
  if (!spending || !spending.daily || spending.daily.length === 0) {
    return renderSpendingPending();
  }

  const canvas = document.getElementById('spending-chart');
  const observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting) {
      if (typeof Chart !== 'undefined') {
        initChart(canvas, spending.daily);
      }
      observer.disconnect();
    }
  }, { rootMargin: '200px' });
  observer.observe(canvas);
}
```

**Dark theme sync:**
```javascript
function syncChartJSToTheme() {
  if (typeof Chart === 'undefined') return;
  const mode = document.documentElement.getAttribute('color-mode');
  const isDark = mode === 'dark';
  Chart.defaults.color = isDark ? '#94a3b8' : '#64748b';
  Chart.defaults.backgroundColor = isDark
    ? ['#60a5fa', '#f472b6', '#34d399', '#fbbf24', '#a78bfa']
    : ['#3b82f6', '#ec4899', '#10b981', '#eab308', '#8b5cf6'];
}
```

### 5.2 Mermaid.js v11 (CDN)

```html
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js" defer></script>
```

**Programmatic render:**
```javascript
function buildMermaidDefinition(pipeline) {
  let def = 'flowchart LR\n';
  pipeline.forEach((stage, i) => {
    const nodeId = stage.agent;
    const label = `${stage.emoji} ${stage.agent}\\n${stage.role}`;
    const style = MERMAID_STATUS_STYLES[stage.status] || 'idle';
    def += `    ${nodeId}["${label}"]:::${style}\n`;
    if (i < pipeline.length - 1) {
      def += `    ${nodeId} --> ${pipeline[i + 1].agent}\n`;
    }
  });
  // Add classDefs for status styles
  Object.entries(MERMAID_STATUS_STYLES).forEach(([key, cls]) => {
    def += `    classDef ${key} fill:${cls.fill},stroke:${cls.stroke},color:${cls.text}\n`;
  });
  return def;
}

function renderMermaid(definition) {
  if (typeof mermaid === 'undefined') {
    return renderPipelineFallback(data.pipeline);
  }
  mermaid.initialize({
    theme: 'base',
    themeVariables: getMermaidThemeVars(),
    securityLevel: 'loose',
    startOnLoad: false
  });
  const container = document.getElementById('mermaid-container');
  mermaid.render('pipeline-graph', definition).then((svg) => {
    container.innerHTML = svg;
    container.querySelector('svg').setAttribute('role', 'img');
    container.querySelector('svg').setAttribute('aria-label', 'Pipeline flow diagram');
  }).catch(() => {
    renderPipelineFallback(data.pipeline);
  });
}
```

**Mermaid dark theme config (open item from UX):**

```javascript
function getMermaidThemeVars() {
  const mode = document.documentElement.getAttribute('color-mode');
  const isDark = mode === 'dark';
  return {
    primaryColor: isDark ? '#1e293b' : '#eff6ff',
    primaryTextColor: isDark ? '#f1f5f9' : '#1e293b',
    primaryBorderColor: isDark ? '#60a5fa' : '#3b82f6',
    lineColor: isDark ? '#475569' : '#cbd5e1',
    secondaryColor: isDark ? '#334155' : '#f1f5f9',
    tertiaryColor: isDark ? '#0f172a' : '#ffffff',
    fontFamily: 'system-ui, -apple-system, sans-serif',
    fontSize: '14px',
  };
}
```

### 5.3 List.js (CDN) — for Issues & PRs filtering

```html
<script src="https://cdn.jsdelivr.net/npm/list.js@2/dist/list.min.js" defer></script>
```

**Integration:**
```javascript
function initIssuesList(issues) {
  const tableBody = document.getElementById('issues-tbody');
  tableBody.innerHTML = buildIssuesRows(issues);

  if (typeof List !== 'undefined' && issues.length > 10) {
    // Use List.js for client-side filter + sort
    new List('issues-table-wrapper', {
      valueNames: ['issue-title', 'issue-project', 'issue-age', 'issue-labels'],
      page: 10,
      pagination: true
    });
  }
  // If List.js not available: vanilla filter with select toggles (works for < 50 rows)
  attachVanillaFilters(issues);
}
```

**Fallback:** If List.js CDN fails, attach vanilla `change` event listeners on filter `<select>` elements that hide/show `<tr>` rows. Same experience, fewer features (no pagination).

### 5.4 marked + DOMPurify (CDN) — Markdown rendering

```html
<script src="https://cdn.jsdelivr.net/npm/marked@12/marked.min.js" defer></script>
<script src="https://cdn.jsdelivr.net/npm/dompurify@3/dist/purify.min.js" defer></script>
```

Used for: issue/PR descriptions in tooltips, project README snippets. Always sanitise output.

### 5.5 No library for freshness badge

`Intl.RelativeTimeFormat` is native in all modern browsers. Zero deps.

---

## 6. Theme System

### 6.1 Three-layer CSS custom properties

| Layer | Selector | Source |
|-------|----------|--------|
| 1. Default | `:root` | Light theme values |
| 2. Dark override | `[color-mode="dark"]` | Dark theme values |
| 3. System preference | `@media (prefers-color-scheme: dark) :root:not([color-mode="light"])` | Auto-fallback when no user choice |

### 6.2 FOUC Prevention (inline `<script>` in `<head>`)

```html
<script>
  (function() {
    var stored = localStorage.getItem('halo-theme');
    var mode = stored || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    document.documentElement.setAttribute('color-mode', mode);
  })();
</script>
```

This runs **before** any CSS loads, ensuring the correct colour mode attribute is set on `<html>` before first paint. No flash.

### 6.3 Theme toggle button

```html
<button id="theme-toggle" type="button"
        aria-label="Switch to dark mode"
        aria-pressed="false">
  <svg class="sun-icon" .../>  <!-- visible in light mode -->
  <svg class="moon-icon" .../> <!-- visible in dark mode -->
</button>
```

**Toggle behaviour:**
1. Click → flip `[color-mode]` on `<html>`
2. Persist to `localStorage.setItem('halo-theme', newMode)`
3. Update `aria-label` and `aria-pressed`
4. Sync Chart.js colours (`syncChartJSToTheme()`)
5. Re-init Mermaid if visible (swap SVG via `renderMermaid(data.pipeline)`)
6. 200ms CSS transition on `background-color` and `color` only

### 6.4 shields.io badge labelColor

**Decision:** Use `labelColor=555555` (neutral grey) for all badges. It works on both light and dark backgrounds without needing per-theme URLs. If readability is poor on dark mode, switch to `labelColor=1e293b` when `color-mode="dark"` is detected.

```javascript
function badgeLabelColor() {
  const mode = document.documentElement.getAttribute('color-mode');
  return mode === 'dark' ? '1e293b' : '555555';
}
```

### 6.5 Colour palette reference

| Token | Light | Dark |
|-------|-------|------|
| `--color-success` | `#22c55e` | `#22c55e` |
| `--color-warning` | `#eab308` | `#eab308` |
| `--color-danger` | `#ef4444` | `#ef4444` |
| `--color-running` | `#3b82f6` | `#60a5fa` |
| `--color-idle` | `#94a3b8` | `#64748b` |
| Chart.js bg array (light) | `#3b82f6, #ec4899, #10b981, #eab308, #8b5cf6` | — |
| Chart.js bg array (dark) | — | `#60a5fa, #f472b6, #34d399, #fbbf24, #a78bfa` |

---

## 7. Responsive Breakpoints

| Breakpoint | Columns | Grid template | Container width |
|------------|---------|---------------|-----------------|
| ≥ 1024px (desktop) | 3 | See §3 | 1200px max |
| 768–1023px (tablet) | 2 | Row 1: `"projects pipeline"` / `"cron cron"`; Row 2 full; Row 3: `"spending agents"` | 96vw |
| < 768px (mobile) | 1 | All stack vertically (see mobile order below) | 100vw – 2rem |

**Mobile stacking order** (matches UX design):
1. Active Projects
2. Pipeline Status
3. Cron Jobs
4. Issues & PRs
5. Agent Health
6. Spending & Usage

**Mobile-specific behaviours:**
- Tables collapse to stacked card-like rows (`<dl>` or `<div>` per item)
- Mermaid flowchart: use `{flowchart LR}` → will auto-orient. For very thin viewports, Mermaid's `{direction LR}` nodes may need manual override (recognised in UX; acceptable for v1)
- Chart.js: `responsive: true, maintainAspectRatio: true` handles width
- Filter bar: `<select>` stacks vertically per UX design
- Padding: 1rem on mobile vs 1.5rem on desktop

---

## 8. UX States Implementation

### 8.1 Skeleton screens (Loading state)

```html
<section id="active-projects" aria-labelledby="projects-heading" aria-busy="true">
  <header><h2>Active Projects</h2><span class="data-age-badge"></span></header>
  <div class="skeleton-loader">
    <!-- 3 skeleton rows matching table height -->
    <div class="skeleton-row"><div class="skeleton-cell" style="width:40%"></div><div class="skeleton-cell" style="width:20%"></div><div class="skeleton-cell" style="width:25%"></div><div class="skeleton-cell" style="width:15%"></div></div>
    <div class="skeleton-row"><!-- ... --></div>
    <div class="skeleton-row"><!-- ... --></div>
  </div>
</section>
```

**CSS shimmer animation:**
```css
.skeleton-loader {
  background: linear-gradient(90deg, var(--color-skeleton) 25%, var(--color-skeleton-shine) 50%, var(--color-skeleton) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
  border-radius: 0.5rem;
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
```

**Shapes per section:**
| Section | Skeleton shape | Dimensions |
|---------|---------------|------------|
| Active Projects | 3–5 rectangular rows | 100% width, 40px each |
| Pipeline | 5 horizontal pill shapes connected by lines | Rough Mermaid shape |
| Issues & PRs | 5–10 rows | 100% width, 36px each |
| Cron Jobs | 5 rows with status dot | 100% width, 36px each |
| Spending | Rectangle (chart area) + 4 stat pills | 300×200px + 4×60px |
| Agent Health | 6 square cards in 2×3 grid | 180×120px each |

### 8.2 Empty states

Each section has a reusable empty state template:

```javascript
function renderEmptyState(sectionId, message, icon) {
  const container = document.getElementById(sectionId);
  container.querySelector('.skeleton-loader')?.remove();
  container.querySelector('.section-content')?.remove();
  const empty = document.createElement('div');
  empty.className = 'empty-state';
  empty.innerHTML = `
    <div class="empty-state-icon">${icon}</div>
    <p class="empty-state-text">${escapeHtml(message)}</p>
  `;
  container.appendChild(empty);
  container.setAttribute('aria-busy', 'false');
}
```

Messages per section (from UX design):
- Active Projects: "No active projects"
- Pipeline: "No pipeline stages configured"
- Issues & PRs: "All clear — no open issues or PRs" (green checkmark)
- Cron Jobs: "No periodic tasks configured" (clock icon)
- Spending: "Data pending — spending tracking coming soon" (hourglass)
- Agent Health: "No agent data available"

### 8.3 Error / stale-data states

```javascript
function handleSectionError(sectionId, staleData) {
  const container = document.getElementById(sectionId);
  if (staleData) {
    // Show stale data with "(stale)" badge
    renderSectionData(sectionId, staleData);
    const badge = container.querySelector('.data-age-badge');
    badge.textContent = '(stale)';
    badge.classList.add('stale');
    return;
  }
  // No data at all — show error state
  container.querySelector('.skeleton-loader')?.remove();
  const error = document.createElement('div');
  error.className = 'error-state';
  error.innerHTML = `
    <div class="error-state-icon">⚠️</div>
    <p class="error-state-text">Data temporarily unavailable</p>
    ${staleLastKnown ? `<p class="error-state-sub">Last known: ${relativeTime(staleLastKnown)}</p>` : ''}
  `;
  container.appendChild(error);
  container.setAttribute('aria-busy', 'false');
}
```

**Key principle:** Never show a blank error. Always prefer stale data + "(stale)" badge over an error state. Error state only shown when there is zero data ever.

---

## 9. Performance Strategy

| Target | Approach | Verification |
|--------|----------|-------------|
| FCP < 1.5s | Critical CSS inlined in `<head>`, no render-blocking resources | Lighthouse |
| LCP < 2.5s | Largest element is header (text-based, no images) | Lighthouse |
| TTI < 3.0s | Defer all JS, lazy-load Chart.js and Mermaid.js | Lighthouse |
| < 500 KB total | Minified CSS/JS, no web fonts, system font stack | `curl` + `wc -c` |
| < 15 HTTP requests | Fonts: 0, CSS: 1, JS: 4 (Chart, Mermaid, List, marked+DOMPurify), JSON: 1, Favicon: 1 = 7-8 total | DevTools Network |
| Zero CLS | Skeleton screens reserve space; all images have dimensions | Lighthouse |

**Specific techniques:**
- **FOUC prevention:** Inline `<script>` sets `color-mode` before CSS paint
- **Critical CSS inlined:** All above-fold styles (header, grid, skeleton) in `<style>` block in `<head>`
- **Resource hints:** `<link rel="preconnect" href="https://cdn.jsdelivr.net">` + `<link rel="dns-prefetch" href="https://github.com">`
- **Defer all scripts:** `<script defer>` for all external JS
- **Lazy-load Chart.js:** Only load when spending section enters viewport
- **Pre-minify:** `npx terser dashboard.js` + `npx clean-css-cli styles.css` before push (zero-install, downloaded from npm on the host)
- **No web fonts:** System font stack: `system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif`

---

## 10. Accessibility (WCAG AA)

### 10.1 ARIA landmarks

```html
<header role="banner">...</header>
<main role="main">...</main>
  <section aria-labelledby="projects-heading">...</section>
  <section aria-labelledby="pipeline-heading">...</section>
  ...
<footer role="contentinfo">...</footer>
```

### 10.2 Live regions

| Element | Role | aria-live | Purpose |
|---------|------|-----------|---------|
| Freshness badge | `status` | `polite` | Announces relative time updates |
| Filter result count | `status` | `polite` | "Showing 3 of 12 results" |
| Error banner (JSON failure) | `alert` | `assertive` | Critical: data couldn't load |

### 10.3 Screen reader companions

- **Charts:** `<canvas aria-hidden="true">` + `<table class="sr-only">` with chart data
- **Mermaid diagram:** `role="img"` + `aria-label="Pipeline flow diagram: Veles → Moo → Cmok → Bagnik → Zlydni"`
- **Status dots:** `aria-label="Status: active"` (dot) + visible text label
- **Filter controls:** `<fieldset><legend class="sr-only">Filters</legend>`

### 10.4 Keyboard navigation

- All `<select>` filters reachable via Tab/arrows
- Theme toggle: Tab + Enter/Space (44×44px touch target)
- Table rows: links open in new tab via individual `<a>` elements
- No custom keyboard traps

### 10.5 Colour + text pairs

Every status indicator has three layers:
1. **Shape/icon** — dot, emoji, icon
2. **Colour** — green/amber/red/blue/grey
3. **Text label** — "Active", "Stalled", "Dormant", "Pass", "Fail", "Running", "Idle"

---

## 11. AC-to-Test Mapping

| AC # | Criterion | Test approach | Test tool | Status |
|------|-----------|---------------|-----------|--------|
| 1 | Site loads at `moo-swarm.github.io/halo` | Open URL in browser | Manual | pending |
| 2 | Active Projects shows real swarm projects | Compare against `_align_rail/PROJECTS.md` | Manual | pending |
| 3 | Pipeline Status shows stages with status per handoff logs + GHA | Cross-check against `handoff-log.md` files | Manual | pending |
| 4 | Open Issues & PRs lists top items from all project repos | Spot-check each on GitHub | Manual | pending |
| 5 | Cron Jobs shows correct schedule/last-run from cron data | Compare against cron config on host | Manual | pending |
| 6 | Spending shows token/cost data or graceful "data pending" | Toggle between having/not having spending data in JSON | Visual + manual | pending |
| 7 | Agent Health cards show status from OpenClaw | Verify against `sessions_list` output | Manual | pending |
| 8 | Data freshness badge shows "updated X ago" | Check timestamp matches last cron run | Visual | pending |
| 9 | Mobile layout stacks columns | DevTools device mode (< 768px) | Visual | pending |
| 10 | Theme toggle works, persists across reload | Toggle → refresh → verify localStorage | Manual | pending |
| 11 | All links open in new tab with `rel="noopener"` | Inspect HTML | Manual | pending |
| 12 | Zero external API calls at page load | DevTools Network tab — only CDN scripts + `data/swarm.json` | DevTools | pending |
| 13 | New data appears within 1h of host changes | Make change, wait for cron, reload | End-to-end | pending |

**Testing philosophy:** Since this is a static HTML/CSS/JS dashboard with no build step, the test approach is predominantly visual/inspection-based. Automated tests would require a test runner (JSDOM, Playwright, or Cypress). This is noted as a gap for phase 2.

---

## 12. Data Schema (Final)

The canonical schema for `data/swarm.json` — used by both `moo-export-data.sh` and `dashboard.js`.

```json
{
  "updated_at": "2026-07-03T12:00:00Z",
  "refresh_interval": 3600,
  "projects": [
    {
      "name": "halo",
      "description": "Moo Swarm live status dashboard",
      "status": "active",
      "health": "green",
      "repo_url": "https://github.com/moo-swarm/halo",
      "stars": 0,
      "open_issues": 2,
      "last_updated": "2026-07-03",
      "pipeline_stage": "spec"
    }
  ],
  "pipeline": [
    {
      "agent": "veles",
      "emoji": "🐍",
      "role": "Research",
      "status": "pass",
      "last_run": "2026-07-03T10:00:00Z",
      "badge_url": "https://img.shields.io/github/actions/workflow/status/moo-swarm/aeroplasty/veles.yml?label=veles&labelColor=555555",
      "workflow_url": "https://github.com/moo-swarm/aeroplasty/actions"
    }
  ],
  "issues": [
    {
      "project": "aeroplasty",
      "number": 3,
      "title": "Pipeline visualisation breaks on dark mode",
      "labels": ["bug", "ui"],
      "created_at": "2026-07-01T15:30:00Z",
      "url": "https://github.com/moo-swarm/aeroplasty/issues/3"
    }
  ],
  "prs": [
    {
      "project": "halo",
      "number": 1,
      "title": "Add skeleton loading states",
      "author": "cmok",
      "status": "open",
      "created_at": "2026-07-02T08:00:00Z",
      "url": "https://github.com/moo-swarm/halo/pull/1"
    }
  ],
  "cron_jobs": [
    {
      "name": "self-improvement-dispatch",
      "schedule": "0 9 * * *",
      "schedule_human": "09:00 daily",
      "last_run": "2026-07-03T09:00:00Z",
      "status": "ok"
    }
  ],
  "spending": {
    "total_tokens_7d": 1234567,
    "cost_7d": 2.45,
    "cost_30d": 10.20,
    "api_calls_7d": 847,
    "active_agents_7d": 6,
    "total_agents": 8,
    "pricing_configured": false,
    "data_source": "openclaw_jsonl",
    "daily": [
      { "date": "2026-06-26", "tokens": 180000, "cost": 0.35 }
    ]
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

## 13. Health Indicator Logic

```javascript
function getProjectHealth(project) {
  const daysSinceUpdate = daysAgo(project.last_updated);
  if (daysSinceUpdate <= 7) return { color: 'green', label: 'Active' };
  if (daysSinceUpdate <= 30) return { color: 'yellow', label: 'Stalled' };
  return { color: 'red', label: 'Dormant' };
}
```

### Mermaid status styles

```javascript
const MERMAID_STATUS_STYLES = {
  pass:   { fill: '#dcfce7', stroke: '#22c55e', text: '#166534' },  // light green
  fail:   { fill: '#fee2e2', stroke: '#ef4444', text: '#991b1b' },  // light red
  running:{ fill: '#dbeafe', stroke: '#3b82f6', text: '#1e40af' },  // light blue
  idle:   { fill: '#f1f5f9', stroke: '#94a3b8', text: '#475569' },  // light grey
};
// Dark counterparts applied via getMermaidThemeVars()
```

### Freshness dot colour logic

```javascript
function getFreshnessColor(isoTime) {
  const minutesAgo = (Date.now() - new Date(isoTime).getTime()) / 60000;
  if (minutesAgo < 60) return 'var(--color-success)';  // green < 1h
  if (minutesAgo < 120) return 'var(--color-warning)';  // amber 1-2h
  return 'var(--color-danger)';                          // red > 2h
}
```

---

## 14. Open Items (from UX design handoff)

| # | Item | Resolution |
|---|------|------------|
| 1 | Mermaid.js dark theme config | `getMermaidThemeVars()` function (see §5.2) — returns `themeVariables` based on `[color-mode]` attribute |
| 2 | Chart.js colour palette for both modes | Dual palette in `syncChartJSToTheme()` (see §5.1) — switches backgroundColor array on `[color-mode]` change |
| 3 | shields.io badge `labelColor` | Use `555555` (neutral grey) for light; `1e293b` for dark. Resolved in `badgeLabelColor()` helper (see §6.4) |
| 4 | Export script (`moo-export-data.sh`) | **Separate build task** — not in scope of this frontend build. Noted in deferred decisions. Script uses `flock -n`, `data/export` branch, 3-retry push. |

---

## 15. HTML Structure (`index.html` skeleton)

```html
<!DOCTYPE html>
<html lang="en" color-mode="light">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="light dark">
  <meta name="description" content="Moo Swarm live status dashboard — active projects, pipeline, issues, regular tasks, spending, and agent health.">
  <meta property="og:title" content="Halo — Moo Swarm Status">
  <meta property="og:description" content="Live dashboard of the Moo swarm">
  <meta property="og:image" content="https://moo-swarm.github.io/halo/og-image.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:type" content="website">
  <title>Halo — Moo Swarm Status</title>

  <!-- FOUC Prevention (runs before CSS) -->
  <script>
    (function() {
      var stored = localStorage.getItem('halo-theme');
      var mode = stored || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
      document.documentElement.setAttribute('color-mode', mode);
    })();
  </script>

  <!-- Resource hints -->
  <link rel="preconnect" href="https://cdn.jsdelivr.net">
  <link rel="dns-prefetch" href="https://github.com">
  <link rel="dns-prefetch" href="https://img.shields.io">

  <!-- Critical CSS (inlined) -->
  <style>
    /* All above-fold CSS: theme vars, grid, skeleton, header */
  </style>

  <!-- Full styles -->
  <link rel="stylesheet" href="styles.css">
  <link rel="icon" href="data:image/svg+xml,...">
</head>
<body>
  <!-- Header, main sections, footer as per §3 component tree -->
  <!-- Skeleton HTML in each section -->
  <script src="dashboard.js" defer></script>
</body>
</html>
```

---

## 16. Export Script Notes (`moo-export-data.sh`)

This is a **separate build task** (not part of the frontend). Key contracts that the frontend depends on:

1. **Output path:** `halo/data/swarm.json` at the root of the repo
2. **Schema:** Must match the JSON schema in §12 exactly (all fields, types, and nesting)
3. **`updated_at`:** ISO 8601 timestamp in UTC
4. **`refresh_interval`:** 3600 (1 hour) — used for stale-data detection
5. **Pricing notes:** The export script should include or omit `cost` fields based on whether the host has pricing configured. Dashboard handles missing `cost` gracefully.
6. **Empty arrays:** Preferred over missing fields. Dashboard handles both.
7. **No-op guard:** Script must detect no changes before pushing — dashboard has no concept of incremental updates.

**Script patterns (from research-synthesis.md):**
- `flock -n` for locking
- Force-push to `data/export` branch (not `main`) via `--force-with-lease`
- `git status --porcelain` check (skip if nothing changed)
- 3 retries with exponential backoff (5s, 10s, 20s) for transient push failures
- `git worktree add` for clean working directory

---

## 17. Deferred Decisions

| Decision | Deferred until | Why |
|----------|---------------|-----|
| Real-time updates via SSE/WebSocket | After v1 ships | GitHub Pages is static; needs external service |
| Search functionality | After v1 ships | Adds complexity; not needed for initial visibility |
| Observable Framework migration | After v1 ships | Would add build tooling overhead; vanilla JS is simpler for v1 |
| Automated spending tracking from agents | After v1 ships | Need to define agent logging conventions first |
| Export script (`moo-export-data.sh`) | Separate build task | Script is infrastructure, not frontend; built after dashboard HTML/JS stabilises |
| Automated E2E tests (Playwright/Cypress) | Phase 2 | Static site with CDN libs — manual testing sufficient for v1 |

---

## 18. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| CDN outage (Chart.js, Mermaid.js) | Low | Medium — chart/diagram sections degrade | Graceful fallbacks: badge row for pipeline, no-chart view for spending |
| `data/swarm.json` schema drift | Medium | High — sections render empty or broken | Defensive parsing: check `.length` before `.map()`, default empty arrays |
| GitHub Pages DNS/cert issues | Low | High — site inaccessible | .nojekyll ensures no Jekyll interference; Pages auto-renew certs |
| Export script push fails repeatedly | Low | Medium — data gets stale | Dashboard shows "(stale)" badge; retry logic in script |
| OpenClaw API changes (spending/agents) | Medium | Low — missing fields show "data pending" | Graceful degradation is built-in; no hard dependency on any single field |
| Browser doesn't support `Intl.RelativeTimeFormat` | Very low (Safari 14+, Chrome 71+, Firefox 65+) | Low — freshness badge shows ISO timestamp instead | `Intl.RelativeTimeFormat` polyfill not worth 4KB; ISO fallback is acceptable |
| Browser doesn't support `fetch` | Very low (no IE11) | High — site doesn't load | Not supporting IE11 is acceptable (decision documented)"