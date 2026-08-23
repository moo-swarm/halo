(function () {
  'use strict';
  var API = window.location.origin + '/api';
  var IS_ADMIN = typeof window !== 'undefined' && !!window.__HALO_UI_ADMIN__;
  var STATE_KEY = 'halo-auth';

  function el(id) { return document.getElementById(id); }
  function text(el, msg) { if (el) el.textContent = msg; }
  function html(el, msg) { if (el) el.innerHTML = msg; }

  async function api(path, opts) {
    opts = opts || {};
    var res = await fetch(API + path, {
      method: opts.method || 'GET',
      headers: Object.assign({}, opts.headers || {}, {'Accept':'application/json'}),
      body: opts.body || undefined,
    });
    var data = null;
    try { data = await res.json(); } catch (e) { data = {}; }
    if (!res.ok) throw Object.assign(new Error('API error ' + res.status), {status: res.status, data: data});
    return data;
  }

  function getAuth() {
    try { return JSON.parse(sessionStorage.getItem(STATE_KEY) || 'null'); } catch (e) { return null; }
  }
  function setAuth(value) {
    if (value) sessionStorage.setItem(STATE_KEY, JSON.stringify(value)); else sessionStorage.removeItem(STATE_KEY);
  }
  function authHeaders() {
    var auth = getAuth();
    var headers = {};
    if (auth) headers['X-Halo-User'] = auth.username;
    return headers;
  }

  async function whoami() {
    try { return await api('/auth/whoami', {headers: authHeaders()}); } catch (e) { return {ok: false}; }
  }

  // Theme
  function applyTheme(mode) {
    var root = document.documentElement;
    if (!mode || mode === 'system') {
      root.removeAttribute('data-theme');
      text(document.querySelector('.toggle-label') || {}, 'System');
      return;
    }
    root.setAttribute('data-theme', mode);
    text(document.querySelector('.toggle-label') || {}, mode === 'dark' ? 'Dark' : 'Light');
  }

  function initTheme() {
    var mode = localStorage.getItem('halo-theme') || 'system';
    applyTheme(mode);
    var btn = document.getElementById('theme-toggle');
    if (!btn) return;
    btn.addEventListener('click', function () {
      var next = (localStorage.getItem('halo-theme') || 'system');
      next = next === 'dark' ? 'light' : next === 'light' ? 'system' : 'dark';
      localStorage.setItem('halo-theme', next);
      applyTheme(next);
    });
  }

  async function loadRoleOptions() {
    var select = document.getElementById('user-role');
    if (!select) return;
    var roles = [
      {id:'public', label:'Guest'},
      {id:'agent', label:'Agent'},
      {id:'admin', label:'Admin'},
    ];
    roles.forEach(function (r) {
      var opt = document.createElement('option');
      opt.value = r.id;
      opt.textContent = r.label;
      select.appendChild(opt);
    });
    select.value = localStorage.getItem('halo-role') || 'public';
    select.addEventListener('change', function () {
      localStorage.setItem('halo-role', select.value);
      location.reload();
    });
  }

  // Dashboard
  function budgetPct(spent, limit) {
    if (!limit) return null;
    return Math.max(0, Math.min(100, (spent / limit) * 100));
  }

  async function refreshDashboard() {
    var main = document.getElementById('dashboard-main');
    if (!main) return;
    var auth = getAuth();
    var role = (auth && auth.role) || localStorage.getItem('halo-role') || 'public';
    if (role === 'public') {
      document.getElementById('gate-banner').style.display = 'grid';
      main.style.display = 'none';
      return;
    }
    document.getElementById('gate-banner').style.display = 'none';
    main.style.display = '';

    try {
      var data = await api('/static/swarm.json');
      var now = new Date().toISOString();
      text(document.getElementById('footer-timestamp'), 'updated ' + now);
      var projectsEl = document.getElementById('active-projects-content');
      if (data.projects && data.projects.length) {
        var rows = data.projects.map(function (p) {
          var updated = p.last_updated ? p.last_updated : '—';
          var stage = p.pipeline_stage ? p.pipeline_stage : '—';
          return '<tr><td>' + escapeHtml(p.name) + '</td><td>' + escapeHtml(p.status || '') + '</td><td>' + escapeHtml(updated) + '</td><td>' + escapeHtml(stage) + '</td></tr>';
        }).join('');
        html(projectsEl, '<table><thead><tr><th>Project</th><th>Status</th><th>Last Update</th><th>Stage</th></tr></thead><tbody>' + rows + '</tbody></table>');
      } else {
        projectsEl.innerHTML = '<p class="empty-state">No active projects</p>';
      }

      var spendingEl = document.getElementById('spending-content');
      if (data.spending && data.spending.daily && data.spending.daily.length) {
        var daily = data.spending.daily.slice(-14);
        var tok = daily.map(function (d) { return d.tokens || 0; });
        var cost = daily.map(function (d) { return d.cost || 0; });
        var chartHtml = '<div class="chart-container"><canvas id="spending-chart" aria-hidden="true"></canvas></div>' +
          '<div class="spending-stats"><div class="stat-card"><div class="stat-value">' + fmtNum((data.spending.total_tokens_7d || 0)) + '</div><div class="stat-label">Tokens (7d)</div></div>' +
          '<div class="stat-card"><div class="stat-value">$' + (data.spending.cost_7d || 0).toFixed(2) + '</div><div class="stat-label">Cost (7d)</div></div></div>';
        html(spendingEl, chartHtml);
        if (window.Chart) {
          var ctx = document.getElementById('spending-chart');
          if (ctx) {
            new Chart(ctx, {
              type: 'bar',
              data: { labels: daily.map(function (d) { return d.date.slice(5); }), datasets: [{ label: 'Tokens', data: tok, backgroundColor: 'rgba(37,99,235,0.7)', borderColor: '#2563eb', borderWidth: 1, yAxisID: 'y' }] },
              options: {
                responsive: true, maintainAspectRatio: true,
                plugins: { legend: { display: false }, tooltip: { callbacks: { afterBody: function (items) { var idx = items[0].dataIndex; return 'Cost: $' + cost[idx].toFixed(2); } } } },
                scales: { x: { grid: { display: false } }, y: { beginAtZero: true } }
              }
            });
          }
        }
      } else {
        html(spendingEl, '<p class="empty-state">Spending data pending</p>');
      }

      var agentsEl = document.getElementById('agents-content');
      if (data.agents && data.agents.length) {
        var cards = data.agents.map(function (a) {
          return '<article class="agent-card"><span class="agent-emoji">' + escapeHtml(a.emoji || '🤖') + '</span><div class="agent-info"><div class="agent-name">' + escapeHtml(a.name) + '</div><div class="agent-role">' + escapeHtml(a.role || '') + '</div></div><div class="agent-meta"><span class="agent-status"><span class="dot-sm ' + statusClass(a.status) + '"></span> ' + escapeHtml(a.status || 'unknown') + '</span><span class="agent-last">' + escapeHtml(a.last_active || '') + '</span></div></article>';
        }).join('');
        html(agentsEl, '<div class="agent-grid">' + cards + '</div>');
      } else {
        agentsEl.innerHTML = '<p class="empty-state">No agent data</p>';
      }
    } catch (err) {
      console.error('dashboard refresh failed', err);
      text(document.getElementById('footer-timestamp'), 'update failed: ' + (err.message || ''));
    }
  }

  function statusClass(status) {
    var map = { active: 'green', busy: 'amber', idle: 'grey', error: 'red', fail: 'red', running: 'blue' };
    return map[status] || 'grey';
  }
  function fmtNum(n) { return (n || 0).toLocaleString(); }
  function escapeHtml(str) {
    str = str || '';
    return str.replace(/[&<>"]/g, function (c) { return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c]; });
  }

  async function submitReport(e) {
    e.preventDefault();
    var text = document.getElementById('report-text').value.trim();
    var attachments = document.getElementById('report-attachments').value.split(/,\s*/).filter(Boolean);
    if (!text) return;
    var auth = getAuth();
    if (!auth || !auth.username) return;
    var res = await api('/agents/' + auth.username + '/report', {
      method: 'POST',
      headers: Object.assign({'Content-Type': 'application/json'}, authHeaders()),
      body: JSON.stringify({text: text, attachments: attachments})
    });
    var status = document.getElementById('report-status');
    if (res && res.ok) { text(status, '✅ Report sent'); document.getElementById('report-text').value = ''; document.getElementById('report-attachments').value = ''; }
    else { text(status, '❌ Failed to send report'); }
  }

  async function loadAdmin() {
    var loginCard = document.getElementById('login-card');
    var panel = document.getElementById('admin-panel');
    var whoamiData = await whoami();
    text(document.getElementById('admin-user'), whoamiData.ok ? whoamiData.username : 'anonymous');
    if (!whoamiData.ok || whoamiData.role !== 'admin') {
      if (loginCard) loginCard.style.display = '';
      if (panel) panel.style.display = 'none';
      return;
    }
    if (loginCard) loginCard.style.display = 'none';
    if (panel) panel.style.display = '';
    await loadAgents();
    await loadReports();
    await loadLock();
  }

  async function loadAgents() {
    var tbody = document.getElementById('agents-tbody');
    if (!tbody) return;
    var data;
    try { data = await api('/admin/agents', {headers: authHeaders()}); } catch (e) { return; }
    if (!data || !data.ok) return;
    html(tbody, data.agents.map(function (a) {
      return '<tr data-username="' + escapeHtml(a.username) + '"><td><input type="checkbox" class="agent-select" value="' + escapeHtml(a.username) + '"></td><td>' + escapeHtml(a.username) + '</td><td>' + escapeHtml(a.role) + '</td><td>' + (a.active ? '✅' : '—') + '</td></tr>';
    }).join(''));
  }

  async function saveAgent() {
    var username = document.getElementById('agent-username').value.trim();
    var role = document.getElementById('agent-role').value.trim() || 'agent';
    var password = document.getElementById('agent-password').value || null;
    var active = document.getElementById('agent-active').checked;
    var body = { username: username, role: role, password: password, active: active };
    var res = await api('/admin/agents', { method: 'POST', headers: Object.assign({'Content-Type':'application/json'}, authHeaders()), body: JSON.stringify(body) });
    if (res && res.ok) { await loadAgents(); }
  }

  async function removeSelected() {
    var checked = Array.from(document.querySelectorAll('.agent-select:checked')).map(function (el) { return el.value; });
    for (var i = 0; i < checked.length; i++) {
      await api('/admin/agents/' + encodeURIComponent(checked[i]), { method: 'DELETE', headers: authHeaders() });
    }
    await loadAgents();
  }

  async function loadLock() {
    var lockEl = document.getElementById('lock-value');
    if (!lockEl) return;
    var data;
    try { data = await api('/admin/lock', {headers: authHeaders()}); } catch (e) { return; }
    text(lockEl, data && data.lock ? 'locked' : 'unlocked');
  }

  async function setLock(value) {
    var data = await api('/admin/lock', { method: 'POST', headers: Object.assign({'Content-Type':'application/json'}, authHeaders()), body: JSON.stringify({lock: value}) });
    if (data && data.ok) { await loadLock(); }
  }

  async function loadReports() {
    var tbody = document.getElementById('reports-tbody');
    if (!tbody) return;
    var data;
    try { data = await api('/admin/reports', {headers: authHeaders()}); } catch (e) { return; }
    if (!data || !data.ok || !data.reports) return;
    html(tbody, data.reports.map(function (r) { return '<tr><td>' + escapeHtml(r.agent) + '</td><td>' + escapeHtml(r.reported_at) + '</td><td>' + escapeHtml((r.text || '').slice(0, 220)) + '</td></tr>'; }).join(''));
  }

  async function downloadReports(format) {
    var path = '/admin/reports.csv';
    if (format === 'json') path = '/admin/reports.json';
    var resp = await fetch(API + path, { method: 'GET', headers: authHeaders() });
    if (!resp.ok) { alert('Export failed'); return; }
    var blob = await resp.blob();
    var url = window.URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'reports.' + format;
    a.click();
    window.URL.revokeObjectURL(url);
  }

  async function login() {
    var username = document.getElementById('username').value.trim();
    var password = document.getElementById('password').value;
    var data = await api('/auth/login', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({username: username, password: password}) });
    if (data && data.ok) { setAuth({username: data.username, role: data.role, active: data.active}); loadAdmin(); }
    else { html(document.getElementById('login-status'), 'Login failed'); }
  }

  async function logout() {
    setAuth(null);
    loadAdmin();
  }

  document.addEventListener('DOMContentLoaded', function () {
    initTheme();
    loadRoleOptions();
    var reportForm = document.getElementById('report-form');
    if (reportForm) reportForm.addEventListener('submit', submitReport);
    if (IS_ADMIN) {
      loadAdmin();
      var loginForm = document.getElementById('login-form');
      if (loginForm) loginForm.addEventListener('submit', function (e) { e.preventDefault(); login(); });
      var lockCard = document.getElementById('lock-card');
      if (lockCard) lockCard.addEventListener('click', function (e) {
        if (e.target.dataset.action === 'lock-on') setLock(true); else if (e.target.dataset.action === 'lock-off') setLock(false);
      });
      var panel = document.getElementById('admin-panel');
      if (panel) {
        panel.addEventListener('click', function (e) {
          if (e.target.id === 'agents-form') return;
          var action = e.target.dataset && e.target.dataset.action;
          if (action === 'reset') removeSelected();
          else if (action === 'save') saveAgent();
          else if (action === 'download') downloadReports(e.target.dataset.download);
        });
        panel.querySelector('#agent-form').addEventListener('submit', function (e) { e.preventDefault(); saveAgent(); });
        panel.querySelectorAll('[data-download]').forEach(function (btn) { btn.addEventListener('click', function () { downloadReports(btn.dataset.download); }); });
      }
    } else {
      var gateBtn = document.getElementById('gate-btn');
      if (gateBtn) {
        gateBtn.textContent = 'Enter dashboard';
        gateBtn.addEventListener('click', async function () {
          var role = localStorage.getItem('halo-role') || 'public';
          if (role === 'public') { localStorage.setItem('halo-role', 'agent'); location.reload(); return; }
          var whoamiData = await whoami();
          if (!whoamiData.ok) {
            var username = prompt('Agent username');
            var password = prompt('Password');
            var loginRes = await api('/auth/login', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({username: username, password: password}) });
            if (loginRes && loginRes.ok) { setAuth({username: loginRes.username, role: loginRes.role}); }
          }
          refreshDashboard();
        });
      }
      refreshDashboard();
      setInterval(refreshDashboard, 60000);
    }
  });
})();\n