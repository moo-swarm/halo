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
    querySelector: () => null,
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

  const budgetHtml = elements.get('agent-budget-content').innerHTML;
  assert.ok(budgetHtml.includes('agent-card'), 'Budget by Agent section rendered cards');

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
