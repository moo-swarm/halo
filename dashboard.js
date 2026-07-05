/* ============================================================
   Halo Dashboard — dashboard.js
   Single IIFE with 12 commented sections.
   Zero build step, no modules.
   ============================================================ */
(function () {
  'use strict';

  /* ==========================================================
   * 1. Config & Constants
   * ========================================================== */
  var REFRESH_INTERVAL = 3600;
  var FRESHNESS_UPDATE_MS = 10000;
  var DATA_URL = 'data/swarm.json';

  var MERMAID_STATUS_STYLES = {
    pass:   { fill: '#dcfce7', stroke: '#22c55e', text: '#166534' },
    fail:   { fill: '#fee2e2', stroke: '#ef4444', text: '#991b1b' },
    running:{ fill: '#dbeafe', stroke: '#3b82f6', text: '#1e40af' },
    idle:   { fill: '#f1f5f9', stroke: '#94a3b8', text: '#475569' }
  };

  var MERMAID_STATUS_STYLES_DARK = {
    pass:   { fill: '#064e3b', stroke: '#22c55e', text: '#86efac' },
    fail:   { fill: '#7f1d1d', stroke: '#ef4444', text: '#fca5a5' },
    running:{ fill: '#1e3a5f', stroke: '#60a5fa', text: '#93c5fd' },
    idle:   { fill: '#1e293b', stroke: '#64748b', text: '#94a3b8' }
  };

  var SECTION_IDS = [
    'active-projects', 'pipeline-status', 'cron-jobs',
    'issues-prs', 'spending-usage', 'agent-health'
  ];

  var EMPTY_MESSAGES = {
    'active-projects': { icon: '📋', msg: 'No active projects' },
    'pipeline-status': { icon: '🔀', msg: 'No pipeline stages configured' },
    'cron-jobs':       { icon: '⏰', msg: 'No periodic tasks configured' },
    'issues-prs':      { icon: '✅', msg: 'All clear — no open issues or PRs' },
    'spending-usage':  { icon: '⏳', msg: 'Data pending — spending tracking coming soon' },
    'agent-health':    { icon: '🤖', msg: 'No agent data available' }
  };

  var freshnessIntervalId = null;
  var cachedData = null;

  /* ==========================================================
   * 2. Data Loading
   * ========================================================== */
  function loadDashboardData() {
    fetch(DATA_URL)
      .then(function (response) {
        if (!response.ok) throw new Error('HTTP ' + response.status);
        return response.json();
      })
      .then(function (data) {
        cachedData = data;
        renderFromData(data);
        removeErrorBanner();
        onDataLoadComplete(true);
      })
      .catch(function (err) {
        console.error('Halo: Failed to load dashboard data:', err);
        if (cachedData) {
          renderFromData(cachedData, true);
          onDataLoadComplete(false);
        } else {
          showErrorBanner();
          onDataLoadComplete(false);
        }
      });
  }

  function renderFromData(data, isStale) {
    SECTION_IDS.forEach(function (id) {
      var section = document.getElementById(id);
      if (section) {
        var skel = section.querySelector('.skeleton-loader');
        if (skel) skel.style.display = 'none';
        section.setAttribute('aria-busy', 'false');
      }
    });

    if (data.updated_at) {
      initFreshnessBadge(data.updated_at, isStale);
    }

    renderProjects(data.projects || []);
    renderPipeline(data.pipeline || []);
    renderCronJobs(data.cron_jobs || []);
    renderIssuesAndPRs(data.issues || [], data.prs || []);
    renderSpending(data.spending, isStale);
    renderAgents(data.agents || []);
  }

  /* ==========================================================
   * 3. Freshness Badge
   * ========================================================== */
  function initFreshnessBadge(isoTime, isStale) {
    updateFreshness(isoTime, isStale);
    if (freshnessIntervalId) clearInterval(freshnessIntervalId);
    freshnessIntervalId = setInterval(function () {
      updateFreshness(isoTime, isStale);
    }, FRESHNESS_UPDATE_MS);
  }

  function updateFreshness(isoTime, isStale) {
    var badge = document.getElementById('freshness-badge');
    if (!badge) return;

    var now = new Date();
    var then = new Date(isoTime);
    var rel = relativeTime(isoTime);
    var dot = badge.querySelector('.status-dot');

    var textSpan = badge.querySelector('.relative-time');
    if (textSpan) textSpan.textContent = 'updated ' + rel;
    badge.title = isoTime;

    var diffMs = now - then;
    var minsAgo = diffMs / 60000;
    var dotColor = 'green';
    if (isStale || minsAgo > 120) dotColor = 'red';
    else if (minsAgo > 60) dotColor = 'amber';

    if (dot) {
      dot.className = 'status-dot ' + dotColor;
    }

    var staleLabel = badge.querySelector('.stale-label');
    if (isStale || minsAgo > 120) {
      if (!staleLabel) {
        var sl = document.createElement('span');
        sl.className = 'stale-label';
        sl.textContent = '(stale)';
        badge.appendChild(sl);
      }
    } else {
      if (staleLabel) staleLabel.remove();
    }
  }

  /* ==========================================================
   * 4. Active Projects
   * ========================================================== */
  function renderProjects(projects) {
    var container = document.getElementById('active-projects-content');
    if (!container) return;

    if (!projects.length) {
      renderEmptyState('active-projects');
      return;
    }

    var rows = projects.map(function (p) {
      var health = getProjectHealth(p);
      var lastUpdate = p.last_updated ? relativeTime(p.last_updated + 'T00:00:00Z') : '—';
      var stageLabel = p.pipeline_stage || '—';
      var stageClass = getStageClass(p.pipeline_stage);
      var specsLabel = p.specs && p.specs.total > 0
        ? '<span class="project-specs" title="' + p.specs.active + ' active, ' + p.specs.total + ' total specs">' + p.specs.active + '&#47;' + p.specs.total + ' specs</span>'
        : '';
      var repoLink = p.repo_url
        ? '<a href="' + escapeHtml(p.repo_url) + '" target="_blank" rel="noopener">' + escapeHtml(p.name) + '</a>'
        : escapeHtml(p.name);

      return '<tr>' +
        '<td data-label="Project"><span class="project-name">' + repoLink + ' ' + specsLabel + '</span></td>' +
        '<td data-label="Status"><span class="health-cell"><span class="status-dot ' + health.color + '"></span><span class="health-label">' + escapeHtml(health.label) + '</span></span></td>' +
        '<td data-label="Last Update">' + escapeHtml(lastUpdate) + '</td>' +
        '<td data-label="Stage"><span class="status-tag ' + stageClass + '">' + escapeHtml(stageLabel) + '</span></td>' +
        '</tr>';
    }).join('');

    container.innerHTML =
      '<table>' +
      '<thead><tr><th>Project</th><th>Status</th><th>Last Update</th><th>Pipeline</th></tr></thead>' +
      '<tbody>' + rows + '</tbody>' +
      '</table>';
  }

  function getProjectHealth(project) {
    if (!project.last_updated) return { color: 'grey', label: 'Unknown' };
    var days = daysAgo(project.last_updated + 'T00:00:00Z');
    if (days <= 7) return { color: 'green', label: 'Active' };
    if (days <= 30) return { color: 'amber', label: 'Stalled' };
    return { color: 'red', label: 'Dormant' };
  }

  function getStageClass(stage) {
    var activeStages = ['spec', 'build', 'research', 'test', 'qa', 'route'];
    if (!stage || stage === 'idle') return 'idle';
    if (activeStages.indexOf(stage) !== -1) return 'active';
    if (stage === 'fail' || stage === 'failed') return 'fail';
    if (stage === 'running') return 'running';
    return 'idle';
  }

  /* ==========================================================
   * 5. Pipeline
   * ========================================================== */
  function renderPipeline(pipeline) {
    var container = document.getElementById('pipeline-content');
    if (!container) return;

    if (!pipeline.length) {
      renderEmptyState('pipeline-status');
      return;
    }

    if (typeof mermaid !== 'undefined') {
      try {
        renderMermaid(pipeline);
        return;
      } catch (e) {
        console.warn('Halo: Mermaid render failed, using fallback', e);
      }
    }

    renderPipelineFallback(pipeline);
  }

  function getMermaidThemeVars() {
    var isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    return {
      primaryColor: isDark ? '#1e293b' : '#eff6ff',
      primaryTextColor: isDark ? '#f1f5f9' : '#1e293b',
      primaryBorderColor: isDark ? '#60a5fa' : '#3b82f6',
      lineColor: isDark ? '#475569' : '#cbd5e1',
      secondaryColor: isDark ? '#334155' : '#f1f5f9',
      tertiaryColor: isDark ? '#0f172a' : '#ffffff',
      fontFamily: 'system-ui, -apple-system, sans-serif',
      fontSize: '14px'
    };
  }

  function buildMermaidDefinition(pipeline) {
    var isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    var styles = isDark ? MERMAID_STATUS_STYLES_DARK : MERMAID_STATUS_STYLES;

    var def = 'flowchart LR\n';
    pipeline.forEach(function (stage, i) {
      var nodeId = stage.agent;
      var label = stage.emoji + ' ' + stage.agent + '\\n' + stage.role;
      var styleKey = stage.status || 'idle';
      if (!styles[styleKey]) styleKey = 'idle';
      def += '    ' + nodeId + '["' + label + '"]:::' + styleKey + '\n';
      if (i < pipeline.length - 1) {
        def += '    ' + nodeId + ' --> ' + pipeline[i + 1].agent + '\n';
      }
    });

    Object.keys(styles).forEach(function (key) {
      var s = styles[key];
      def += '    classDef ' + key + ' fill:' + s.fill + ',stroke:' + s.stroke + ',color:' + s.text + '\n';
    });

    return def;
  }

  function renderMermaid(pipeline) {
    var container = document.getElementById('mermaid-container');
    if (!container) return;
    container.style.display = 'block';

    var fallback = document.getElementById('mermaid-fallback');
    if (fallback) fallback.style.display = 'none';

    var definition = buildMermaidDefinition(pipeline);

    mermaid.initialize({
      theme: 'base',
      themeVariables: getMermaidThemeVars(),
      securityLevel: 'loose',
      startOnLoad: false
    });

    mermaid.render('pipeline-graph', definition)
      .then(function (result) {
        container.innerHTML = result.svg;
        var svg = container.querySelector('svg');
        if (svg) {
          svg.setAttribute('role', 'img');
          svg.setAttribute('aria-label', 'Pipeline flow diagram: ' +
            pipeline.map(function (s) { return s.agent; }).join(' → '));
        }
      })
      .catch(function () {
        renderPipelineFallback(pipeline);
      });
  }

  function renderPipelineFallback(pipeline) {
    var mContainer = document.getElementById('mermaid-container');
    if (mContainer) mContainer.style.display = 'none';

    var fallback = document.getElementById('mermaid-fallback');
    if (!fallback) return;
    fallback.style.display = 'flex';

    var html = pipeline.map(function (stage) {
      var statusIcon = getStatusIcon(stage.status);
      var statusClass = stage.status || 'idle';
      var timeStr = stage.last_run ? relativeTime(stage.last_run) : '—';

      return '<div class="pipeline-stage">' +
        '<span class="stage-emoji">' + escapeHtml(stage.emoji || '') + '</span>' +
        '<span class="stage-label"><strong>' + escapeHtml(stage.agent) + '</strong> ' + escapeHtml(stage.role) + '</span>' +
        '<span class="status-tag ' + statusClass + '">' + statusIcon + ' ' + escapeHtml(statusClass) + '</span>' +
        '<span class="stage-time">' + escapeHtml(timeStr) + '</span>' +
        '</div>';
    }).join('');

    fallback.innerHTML = html;
  }

  function getStatusIcon(status) {
    switch (status) {
      case 'pass': return '✅';
      case 'fail': return '❌';
      case 'running': return '⏳';
      default: return '⚪';
    }
  }

  /* ==========================================================
   * 6. Issues & PRs
   * ========================================================== */
  function renderIssuesAndPRs(issues, prs) {
    var issuesBody = document.getElementById('issues-tbody');
    var prsBody = document.getElementById('prs-tbody');

    if (issues.length && issuesBody) {
      issuesBody.innerHTML = issues.slice(0, 10).map(function (issue) {
        var labelsHtml = (issue.labels || []).map(function (l) {
          return '<span class="label ' + getLabelClass(l) + '">' + escapeHtml(l) + '</span>';
        }).join(' ');
        var age = relativeTime(issue.created_at);
        return '<tr class="issue-row">' +
          '<td data-label="Issue"><a href="' + escapeHtml(issue.url) + '" target="_blank" rel="noopener">#' + issue.number + ' ' + escapeHtml(issue.title) + '</a></td>' +
          '<td class="issue-project" data-label="Project">' + escapeHtml(issue.project) + '</td>' +
          '<td data-label="Age">' + escapeHtml(age) + '</td>' +
          '<td data-label="Labels">' + labelsHtml + '</td>' +
          '</tr>';
      }).join('');
      setupFilters(issues, prs);
    } else if (issuesBody) {
      issuesBody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--color-text-muted);">No open issues</td></tr>';
    }

    if (prs.length && prsBody) {
      prsBody.innerHTML = prs.slice(0, 5).map(function (pr) {
        var statusIcon = pr.status === 'open' ? '<span class="dot-sm green"></span>' :
                         pr.status === 'draft' ? '<span class="dot-sm amber"></span>' :
                         '<span class="dot-sm grey"></span>';
        var age = relativeTime(pr.created_at);
        return '<tr class="pr-row">' +
          '<td data-label="PR"><a href="' + escapeHtml(pr.url) + '" target="_blank" rel="noopener">#' + pr.number + ' ' + escapeHtml(pr.title) + '</a></td>' +
          '<td class="pr-project" data-label="Project">' + escapeHtml(pr.project) + '</td>' +
          '<td data-label="Author">' + escapeHtml(pr.author) + '</td>' +
          '<td data-label="Status">' + statusIcon + ' ' + escapeHtml(pr.status) + '</td>' +
          '<td data-label="Age">' + escapeHtml(age) + '</td>' +
          '</tr>';
      }).join('');
    } else if (prsBody) {
      prsBody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--color-text-muted);">No open pull requests</td></tr>';
    }

    if (!issues.length && !prs.length) {
      renderEmptyState('issues-prs');
    }
  }

  function getLabelClass(label) {
    var map = { 'bug': 'bug', 'enhancement': 'enhancement', 'docs': 'docs', 'ux': 'ux', 'ui': 'ux', 'logging': 'logging', 'performance': 'performance' };
    return map[label] || '';
  }

  function setupFilters(issues, prs) {
    var projectFilter = document.getElementById('filter-project');
    var labelFilter = document.getElementById('filter-label');
    var statusFilter = document.getElementById('filter-status');
    var clearBtn = document.getElementById('clear-filters');
    if (!projectFilter) return;

    var projects = [];
    issues.forEach(function (i) { if (projects.indexOf(i.project) === -1) projects.push(i.project); });
    prs.forEach(function (p) { if (projects.indexOf(p.project) === -1) projects.push(p.project); });
    projects.sort();

    var currentOptions = Array.from(projectFilter.options).map(function (o) { return o.value; });
    projects.forEach(function (proj) {
      if (currentOptions.indexOf(proj) === -1) {
        var opt = document.createElement('option');
        opt.value = proj;
        opt.textContent = proj;
        projectFilter.appendChild(opt);
      }
    });

    var applyFilter = function () {
      filterTableRows(projectFilter.value,
        labelFilter ? labelFilter.value : 'all',
        statusFilter ? statusFilter.value : 'all');
    };

    projectFilter.addEventListener('change', applyFilter);
    if (labelFilter) labelFilter.addEventListener('change', applyFilter);
    if (statusFilter) statusFilter.addEventListener('change', applyFilter);
    if (clearBtn) {
      clearBtn.addEventListener('click', function () {
        projectFilter.value = 'all';
        if (labelFilter) labelFilter.value = 'all';
        if (statusFilter) statusFilter.value = 'all';
        applyFilter();
      });
    }
  }

  function filterTableRows(project) {
    var rows = document.querySelectorAll('#issues-tbody tr, #prs-tbody tr');
    var visibleCount = 0;
    Array.from(rows).forEach(function (row) {
      var show = true;
      if (project !== 'all') {
        var projCell = row.querySelector('.issue-project, .pr-project');
        if (projCell && projCell.textContent.trim() !== project) show = false;
      }
      if (show) {
        row.style.display = '';
        visibleCount++;
      } else {
        row.style.display = 'none';
      }
    });
    var countEl = document.getElementById('result-count');
    if (countEl) {
      countEl.textContent = 'Showing ' + visibleCount + ' of ' + rows.length + ' items';
    }
  }

  /* ==========================================================
   * 7. Cron Jobs
   * ========================================================== */
  function renderCronJobs(cronJobs) {
    var container = document.getElementById('cron-content');
    if (!container) return;

    if (!cronJobs.length) {
      renderEmptyState('cron-jobs');
      return;
    }

    var rows = cronJobs.map(function (job) {
      var statusDotClass = job.status === 'ok' ? 'green' : (job.status === 'fail' ? 'red' : 'amber');
      var lastRun = job.last_run ? relativeTime(job.last_run) : '—';
      var schedule = job.schedule_human || job.schedule || '—';

      return '<tr>' +
        '<td data-label="Task">' + escapeHtml(job.name) + '</td>' +
        '<td data-label="Schedule">' + escapeHtml(schedule) + '</td>' +
        '<td data-label="Last Run">' + escapeHtml(lastRun) + '</td>' +
        '<td data-label="Status"><span class="dot-sm ' + statusDotClass + '"></span></td>' +
        '</tr>';
    }).join('');

    container.innerHTML =
      '<table>' +
      '<thead><tr><th>Task</th><th>Schedule</th><th>Last Run</th><th></th></tr></thead>' +
      '<tbody>' + rows + '</tbody>' +
      '</table>';
  }

  /* ==========================================================
   * 8. Spending
   * ========================================================== */
  function renderSpending(spending) {
    var container = document.getElementById('spending-content');
    if (!container) return;

    if (!spending || !spending.daily || !spending.daily.length) {
      renderPendingState('spending-usage');
      return;
    }

    var statsHtml =
      '<div class="spending-stats">' +
      '<div class="stat-card"><div class="stat-value">' + formatNumber(spending.total_tokens_7d || 0) + '</div><div class="stat-label">Tokens (7d)</div></div>' +
      '<div class="stat-card"><div class="stat-value">' + (spending.cost_7d != null ? '$' + spending.cost_7d.toFixed(2) : '—') + '</div><div class="stat-label">Cost (7d)</div></div>' +
      '<div class="stat-card"><div class="stat-value">' + formatNumber(spending.api_calls_7d || 0) + '</div><div class="stat-label">API Calls (7d)</div></div>' +
      '<div class="stat-card"><div class="stat-value">' + (spending.active_agents_7d || 0) + '/' + (spending.total_agents || '?') + '</div><div class="stat-label">Active Agents</div></div>' +
      '</div>';

    container.innerHTML =
      '<div class="chart-container"><canvas id="spending-chart" aria-hidden="true"></canvas></div>' +
      statsHtml;

    var canvas = document.getElementById('spending-chart');
    if (!canvas) return;

    var observer = new IntersectionObserver(function (entries) {
      if (entries[0].isIntersecting) {
        if (typeof Chart !== 'undefined') {
          initChart(canvas, spending.daily);
        }
        observer.disconnect();
      }
    }, { rootMargin: '200px' });
    observer.observe(canvas);
  }

  function initChart(canvas, dailyData) {
    if (typeof Chart === 'undefined') return;

    var labels = dailyData.map(function (d) { return d.date.slice(5); });
    var tokens = dailyData.map(function (d) { return d.tokens; });
    var costs = dailyData.map(function (d) { return d.cost || 0; });
    var isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

    new Chart(canvas, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Tokens',
          data: tokens,
          backgroundColor: isDark ? 'rgba(96, 165, 250, 0.7)' : 'rgba(37, 99, 235, 0.7)',
          borderColor: isDark ? '#60a5fa' : '#2563eb',
          borderWidth: 1,
          yAxisID: 'y'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              afterBody: function (items) {
                var idx = items[0].dataIndex;
                return 'Cost: $' + (costs[idx] || 0).toFixed(2);
              }
            }
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: isDark ? '#94a3b8' : '#64748b', font: { size: 10 } }
          },
          y: {
            beginAtZero: true,
            grid: { color: isDark ? '#334155' : '#e2e8f0' },
            ticks: {
              color: isDark ? '#94a3b8' : '#64748b',
              font: { size: 10 },
              callback: function (val) { return formatNumber(val); }
            }
          }
        }
      }
    });
  }

  function syncChartJSToTheme() {
    if (typeof Chart === 'undefined') return;
    var isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    Chart.defaults.color = isDark ? '#94a3b8' : '#64748b';
    Chart.defaults.borderColor = isDark ? '#334155' : '#e2e8f0';
  }

  /* ==========================================================
   * 9. Agent Health
   * ========================================================== */
  function renderAgents(agents) {
    var container = document.getElementById('agents-content');
    if (!container) return;

    if (!agents.length) {
      renderEmptyState('agent-health');
      return;
    }

    var cards = agents.map(function (agent) {
      var statusClass = getAgentStatusClass(agent.status);
      var statusLabel = agent.status || 'unknown';
      var lastActive = agent.last_active ? relativeTime(agent.last_active) : '—';
      var sessionsStr = agent.sessions_24h != null ? agent.sessions_24h + ' sessions' : '';

      return '<article class="agent-card">' +
        '<span class="agent-emoji">' + escapeHtml(agent.emoji || '') + '</span>' +
        '<div class="agent-info">' +
        '<div class="agent-name">' + escapeHtml(agent.name) + '</div>' +
        '<div class="agent-role">' + escapeHtml(agent.role || '') + '</div>' +
        '</div>' +
        '<div class="agent-meta">' +
        '<span class="agent-status"><span class="dot-sm ' + statusClass + '"></span> ' + escapeHtml(statusLabel) + '</span>' +
        '<span class="agent-last">' + escapeHtml(lastActive) + (sessionsStr ? ' · ' + sessionsStr : '') + '</span>' +
        '</div>' +
        '</article>';
    }).join('');

    container.innerHTML = '<div class="agent-grid">' + cards + '</div>';
  }

  function getAgentStatusClass(status) {
    switch (status) {
      case 'active': return 'green';
      case 'busy': return 'amber';
      case 'idle': return 'grey';
      case 'error': case 'fail': return 'red';
      default: return 'grey';
    }
  }

  /* ==========================================================
   * 10. Theme System
   * ========================================================== */
  function initTheme() {
    // Theme auto-follows system/Telegram via @media (prefers-color-scheme)
    // Just sync chart colours and mermaid on theme change
    syncChartJSToTheme();

    var mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    mediaQuery.addEventListener('change', function () {
      syncChartJSToTheme();
      reRenderMermaid();
    });
  }

  /* === Telegram Mini App Integration === */
  function initTelegram() {
    var tg = window.Telegram && window.Telegram.WebApp;
    if (!tg) return;

    // Expand to full height + ready
    if (tg.ready) tg.ready();
    if (tg.expand) tg.expand();

    // MainButton: refresh
    if (tg.MainButton) {
      tg.MainButton.setText('↻ Refresh');
      tg.MainButton.onClick(function () {
        tgHaptic('impact', 'medium');
        loadDashboardData();
      });
      tg.MainButton.show();
    }

    // Listen for Telegram theme changes
    if (tg.onEvent) {
      tg.onEvent('themeChanged', function () {
        var tp = tg.themeParams;
        if (!tp) return;
        var root = document.documentElement;
        root.style.setProperty('--tg-bg', tp.bg_color || '');
        root.style.setProperty('--tg-secondary-bg', tp.secondary_bg_color || '');
        root.style.setProperty('--tg-text', tp.text_color || '');
        root.style.setProperty('--tg-hint', tp.hint_color || '');
        root.style.setProperty('--tg-link', tp.link_color || '');
        root.style.setProperty('--tg-button', tp.button_color || '');
        if (tg.colorScheme === 'dark') {
          root.classList.add('tg-dark');
        } else {
          root.classList.remove('tg-dark');
        }
        syncChartJSToTheme();
        reRenderMermaid();
      });
    }
  }

  function tgHaptic(type, style) {
    var tg = window.Telegram && window.Telegram.WebApp;
    if (!tg || !tg.HapticFeedback) return;
    if (type === 'impact') tg.HapticFeedback.impactOccurred(style || 'light');
    else if (type === 'notification') tg.HapticFeedback.notificationOccurred(style || 'success');
  }

  function tgMainButtonProgress(show) {
    var tg = window.Telegram && window.Telegram.WebApp;
    if (!tg || !tg.MainButton) return;
    if (show) {
      tg.MainButton.showProgress(true);
      tg.MainButton.setText('Refreshing…');
      tg.MainButton.disable();
    } else {
      tg.MainButton.hideProgress();
      tg.MainButton.setText('↻ Refresh');
      tg.MainButton.enable();
    }
 }



  function reRenderMermaid() {
    if (cachedData && cachedData.pipeline) {
      renderPipeline(cachedData.pipeline);
    }
  }

  /* ==========================================================
   * 11. Helpers
   * ========================================================== */
  function escapeHtml(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  function relativeTime(isoString) {
    if (!isoString) return '—';
    var now = Date.now();
    var then = new Date(isoString).getTime();
    if (isNaN(then)) return isoString;

    var diffMs = now - then;
    var absDiff = Math.abs(diffMs);
    var rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });

    var seconds = Math.round(diffMs / 1000);
    var minutes = Math.round(diffMs / 60000);
    var hours = Math.round(diffMs / 3600000);
    var days = Math.round(diffMs / 86400000);

    if (absDiff < 60000) return rtf.format(seconds, 'second');
    if (absDiff < 3600000) return rtf.format(minutes, 'minute');
    if (absDiff < 86400000) return rtf.format(hours, 'hour');
    if (absDiff < 604800000) return rtf.format(days, 'day');
    return new Date(isoString).toLocaleDateString();
  }

  function daysAgo(isoString) {
    var now = Date.now();
    var then = new Date(isoString).getTime();
    if (isNaN(then)) return 999;
    return Math.floor((now - then) / 86400000);
  }

  function formatNumber(num) {
    if (num == null) return '—';
    return num.toLocaleString();
  }

  function skeletonHTML(type) {
    switch (type) {
      case 'projects':
        return '<div class="skeleton-loader skeleton-projects">' +
          '<div class="skeleton-row w-90"></div>' +
          '<div class="skeleton-row w-70"></div>' +
          '<div class="skeleton-row w-80"></div>' +
          '<div class="skeleton-row w-60"></div></div>';
      case 'pipeline':
        return '<div class="skeleton-loader">' +
          '<div class="skeleton-pill" style="width:90%"></div>' +
          '<div class="skeleton-pill" style="width:80%"></div>' +
          '<div class="skeleton-pill" style="width:85%"></div>' +
          '<div class="skeleton-pill" style="width:70%"></div>' +
          '<div class="skeleton-pill" style="width:75%"></div></div>';
      case 'cron':
        return '<div class="skeleton-loader">' +
          '<div class="skeleton-row w-90"></div>' +
          '<div class="skeleton-row w-85"></div>' +
          '<div class="skeleton-row w-80"></div>' +
          '<div class="skeleton-row w-75"></div>' +
          '<div class="skeleton-row w-70"></div></div>';
      case 'issues':
        return '<div class="skeleton-loader">' +
          '<div class="skeleton-row w-95"></div>' +
          '<div class="skeleton-row w-90"></div>' +
          '<div class="skeleton-row w-85"></div>' +
          '<div class="skeleton-row w-80"></div>' +
          '<div class="skeleton-row w-75"></div>' +
          '<div class="skeleton-row w-88"></div></div>';
      case 'spending':
        return '<div class="skeleton-loader">' +
          '<div class="skeleton-chart"></div>' +
          '<div style="display:flex;gap:0.5rem;margin-top:0.5rem;">' +
          '<div class="skeleton-card" style="flex:1"></div>' +
          '<div class="skeleton-card" style="flex:1"></div>' +
          '<div class="skeleton-card" style="flex:1"></div>' +
          '<div class="skeleton-card" style="flex:1"></div></div></div>';
      case 'agents':
        return '<div class="skeleton-loader" style="display:grid;grid-template-columns:1fr 1fr;gap:0.6rem;">' +
          '<div class="skeleton-card"></div>' +
          '<div class="skeleton-card"></div>' +
          '<div class="skeleton-card"></div>' +
          '<div class="skeleton-card"></div>' +
          '<div class="skeleton-card"></div>' +
          '<div class="skeleton-card"></div></div>';
      default: return '<div class="skeleton-loader"><div class="skeleton-row w-80"></div></div>';
    }
  }

  function renderEmptyState(sectionId) {
    var container = document.getElementById(sectionId + '-content');
    if (!container) return;
    var msg = EMPTY_MESSAGES[sectionId];
    if (!msg) return;
    container.innerHTML =
      '<div class="empty-state">' +
      '<div class="empty-icon">' + msg.icon + '</div>' +
      '<p class="empty-msg">' + escapeHtml(msg.msg) + '</p></div>';
  }

  function renderPendingState(sectionId) {
    if (sectionId === 'spending-usage') {
      var container = document.getElementById('spending-content');
      if (!container) return;
      container.innerHTML =
        '<div class="data-pending">' +
        '<div class="pending-icon">⏳</div>' +
        '<p>Data pending — spending tracking coming soon</p></div>';
    }
  }

  function showErrorBanner() {
    var banner = document.getElementById('page-error-banner');
    if (banner) banner.style.display = 'flex';
  }

  function removeErrorBanner() {
    var banner = document.getElementById('page-error-banner');
    if (banner) banner.style.display = 'none';
  }

  /* ==========================================================
   * 12. Init
   * ========================================================== */
  function init() {
    initTheme();
    initTelegram();
    loadDashboardData();
    setInterval(function () {
      loadDashboardData();
    }, REFRESH_INTERVAL * 1000);

    var retryBtn = document.getElementById('retry-btn');
    if (retryBtn) {
      retryBtn.addEventListener('click', function () {
        tgHaptic('impact', 'medium');
        loadDashboardData();
      });
    }
  }

  function onDataLoadComplete(success) {
    tgMainButtonProgress(false);
    if (success) {
      tgHaptic('notification', 'success');
    } else {
      tgHaptic('notification', 'warning');
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
