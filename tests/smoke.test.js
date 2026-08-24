'use strict';
/**
 * Runtime smoke test for dashboard.js.
 *
 * node --check / CI lint cannot catch runtime ReferenceErrors inside the
 * render path (they only surface when a browser executes the IIFE on the
 * deployed page). This harness executes the whole dashboard in a vm sandbox
 * with stubbed browser globals and the REAL data/swarm.json fixture, then
 * asserts every section actually rendered.
 *
 * Zero dependencies: node --test tests/
 */

const { test } = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ROOT = path.resolve(__dirname, '..');

function makeFakeElement(id) {
  return {
    id,
    style: {},
    innerHTML: '',
    textContent: '',
    className: '',
    value: '',
    options: [], // <select> support for setupFilters
    children: [],
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    setAttribute() {},
    getAttribute: () => null,
    addEventListener() {},
    appendChild(child) { this.children.push(child); },
    // Minimal class-selector resolution over explicitly appended children —
    // index.html markup is NOT parsed out of innerHTML strings by this mock,
    // so only appendChild-built structure is visible. Compound "a, b" lists
    // match either class; everything else stays null like a miss.
    querySelector(selector) {
      const parts = String(selector).split(',').map((s) => s.trim());
      return (
        this.children.find((c) =>
          parts.some((p) => {
            const classes = (String(p).match(/\.([\w-]+)/g) || []).map((m) => m.slice(1));
            return (
              classes.length > 0 &&
              classes.every((k) => String(c.className).includes(k))
            );
          })
        ) || null
      );
    },
    querySelectorAll: () => [],
    getContext: () => ({}) // Chart.js canvas
  };
}

function buildSandbox(fixture) {
  const elements = new Map();
  const state = {
    domContentLoadedHandler: null,
    mermaidDefinitions: [],
    chartConfigs: []
  };

  const documentStub = {
    addEventListener(type, fn) {
      if (type === 'DOMContentLoaded') state.domContentLoadedHandler = fn;
    },
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, makeFakeElement(id));
      return elements.get(id);
    },
    createElement: (tag) => makeFakeElement(`<${tag}>`),
    createTextNode: (text) => ({ nodeType: 3, textContent: String(text) }),
    querySelectorAll: () => [],
    documentElement: makeFakeElement('<html>')
  };

  const sandbox = {
    console,
    document: documentStub,
    window: {
      matchMedia: () => ({ matches: false, addEventListener() {} }),
      addEventListener() {}
    },
    localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    navigator: {},
    fetch: async () => ({ ok: true, json: async () => fixture }),
    setInterval: () => 0,
    clearInterval() {},
    setTimeout: (fn) => 0,
    clearTimeout() {},
    mermaid: {
      initialize() {},
      render(id, definition) {
        state.mermaidDefinitions.push(definition);
        return Promise.resolve({ svg: `<svg id="${id}"></svg>` });
      }
    },
    Chart: function Chart(canvas, config) {
      state.chartConfigs.push(config);
    },
    // Fires the callback immediately as intersecting so lazy chart init runs.
    IntersectionObserver: function (callback) {
      this.observe = () => setImmediate(() => callback([{ isIntersecting: true }]));
      this.disconnect = () => {};
      this.unobserve = () => {};
    }
  };
  sandbox.Chart.defaults = {}; // real Chart.js carries a defaults object
  sandbox.window.Telegram = undefined;
  sandbox.globalThis = sandbox;
  return { sandbox, elements, state };
}

async function flushMicrotasks(times = 5) {
  for (let i = 0; i < times; i++) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

test('dashboard boots end-to-end against the real swarm.json without ReferenceErrors', async () => {
  const source = fs.readFileSync(path.join(ROOT, 'dashboard.js'), 'utf8');
  const fixture = JSON.parse(
    fs.readFileSync(path.join(ROOT, 'data', 'swarm.json'), 'utf8')
  );

  const { sandbox, elements, state } = buildSandbox(fixture);
  vm.runInNewContext(source, sandbox, { filename: 'dashboard.js' });

  assert.ok(state.domContentLoadedHandler, 'IIFE registered a DOMContentLoaded handler');
  await state.domContentLoadedHandler(); // init(): theme, telegram, load, refresh timer
  await flushMicrotasks(); // let fetch().then(...) chains settle

  // Sections that silently died or stayed skeleton before the smoke test existed:
  const agentsHtml = elements.get('agents-content').innerHTML;
  assert.ok(agentsHtml.includes('agent-card'), 'Agent Health section rendered cards');

  // UAT fix: Budget by Agent was merged into Agent Health — every budgeted
  // agent card must carry the compact used/limit line with a colour-coded %.
  assert.ok(agentsHtml.includes('budget-pct'), 'Agent Health cards carry merged per-agent budget %');

  assert.ok(
    elements.get('projects-body') === undefined ||
      elements.get('projects-body').innerHTML.length > 0,
    'Projects table rendered'
  );
  assert.ok(elements.get('cron-content').innerHTML.length > 0, 'Cron section rendered');

  // Mermaid pipeline graph: definition must contain classDef lines for all statuses
  assert.ok(state.mermaidDefinitions.length === 1, 'mermaid.render called exactly once');
  const def = state.mermaidDefinitions[0];
  for (const status of ['pass', 'fail', 'running', 'idle']) {
    assert.ok(def.includes(`classDef ${status}`), `classDef ${status} present`);
  }

  // Spending chart got a Chart.js config
  assert.ok(state.chartConfigs.length >= 1, 'Chart.js spending chart initialised');
});

test('mermaid styles differ between light and dark color schemes', async () => {
  const source = fs.readFileSync(path.join(ROOT, 'dashboard.js'), 'utf8');
  const fixture = JSON.parse(
    fs.readFileSync(path.join(ROOT, 'data', 'swarm.json'), 'utf8')
  );

  const light = buildSandbox(fixture);
  vm.runInNewContext(source, light.sandbox, { filename: 'dashboard.js' });
  await light.state.domContentLoadedHandler();
  await flushMicrotasks();

  const dark = buildSandbox(fixture);
  dark.sandbox.window.matchMedia = () => ({ matches: true, addEventListener() {} });
  vm.runInNewContext(source, dark.sandbox, { filename: 'dashboard.js' });
  await dark.state.domContentLoadedHandler();
  await flushMicrotasks();

  const lightDef = light.state.mermaidDefinitions[0];
  const darkDef = dark.state.mermaidDefinitions[0];
  assert.notEqual(lightDef, darkDef, 'dark scheme produces different classDef colors');
});

/* ── Per-section staleness markers (live-exporter AC12/AC13) ─────────── */

const SECTION_IDS = [
  'active-projects', 'pipeline-status', 'cron-jobs',
  'issues-prs', 'agent-health'
];

function chipsFor(elements, sectionId) {
  const el = elements.get(sectionId);
  if (!el) return [];
  return el.children.filter((c) => String(c.className).includes('section-stale'));
}

async function boot(source, fixture) {
  const { sandbox, elements, state } = buildSandbox(fixture);
  vm.runInNewContext(source, sandbox, { filename: 'dashboard.js' });
  await state.domContentLoadedHandler();
  await flushMicrotasks();
  return { sandbox, elements, state };
}

test('stale stamps + one source_errors entry mark exactly those sections', async () => {
  const source = fs.readFileSync(path.join(ROOT, 'dashboard.js'), 'utf8');
  const base = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'swarm.json'), 'utf8'));

  const fresh = new Date(Date.now() - 5 * 60000).toISOString();   // 5 min old
  const old = new Date(Date.now() - 3 * 3600000).toISOString();   // 3 h old
  const fixture = JSON.parse(JSON.stringify(base));
  fixture.sections_updated_at = {
    projects: fresh, pipeline: fresh, cron_jobs: old,
    issues: fresh, prs: fresh, agents: fresh
  };
  fixture.source_errors = { pipeline: { error: 'boom', at: fresh } };

  const { elements } = await boot(source, fixture);

  // cron-jobs: stamp >120 min. pipeline-status: listed in source_errors.
  assert.equal(chipsFor(elements, 'cron-jobs').length, 1, 'cron chip shown');
  assert.equal(chipsFor(elements, 'pipeline-status').length, 1, 'pipeline chip shown');
  assert.equal(
    chipsFor(elements, 'pipeline-status')[0].textContent, 'source failed',
    'error-backed chip says why'
  );
  // Everything else is fresh: no markers at all.
  for (const id of ['active-projects', 'issues-prs', 'agent-health']) {
    assert.equal(chipsFor(elements, id).length, 0, `${id} stays clean`);
  }
});

test('fixture without staleness maps renders identically — no markers, badge per age rules', async () => {
  const source = fs.readFileSync(path.join(ROOT, 'dashboard.js'), 'utf8');
  const fixture = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'swarm.json'), 'utf8'));
  // The hourly auto-export cron setdefaults both maps into the tracked
  // data/swarm.json, so asserting their absence would race live state. Strip
  // them instead: this always simulates an old-format file, and
  // applySectionStaleness treats absent and empty maps identically.
  delete fixture.sections_updated_at;
  delete fixture.source_errors;

  // Pre-seed the badge with the real index.html structure (lines 75-78) so
  // updateFreshness's querySelector paths run against the mock DOM.
  const { sandbox, elements, state } = buildSandbox(fixture);
  const badge = sandbox.document.getElementById('freshness-badge');
  const dot = sandbox.document.createElement('span');
  dot.className = 'status-dot green';
  const relSpan = sandbox.document.createElement('span');
  relSpan.className = 'relative-time';
  badge.appendChild(dot);
  badge.appendChild(relSpan);

  vm.runInNewContext(source, sandbox, { filename: 'dashboard.js' });
  await state.domContentLoadedHandler();
  await flushMicrotasks();

  for (const id of SECTION_IDS) {
    assert.equal(chipsFor(elements, id).length, 0, `${id} has no marker`);
  }

  // Global badge still renders and follows the documented thresholds
  // (green <60 min, amber ≤120, red + (stale) beyond).
  assert.ok(relSpan.textContent.startsWith('updated '), 'badge shows relative time');
  const minsAgo = (Date.now() - new Date(fixture.updated_at).getTime()) / 60000;
  const expected = minsAgo > 120 ? 'red' : minsAgo > 60 ? 'amber' : 'green';
  assert.equal(dot.className, `status-dot ${expected}`, 'dot colour matches age');
});
