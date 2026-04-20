// Super Memory Desktop — TerminalPool, page router, API client, Quick Capture.

(function () {
  'use strict';

  const UI_TOKEN = window.UI_TOKEN || '';

  // ------------------------------------------------------------
  // API client
  // ------------------------------------------------------------
  const api = {
    async _fetch(url, opts) {
      opts = opts || {};
      opts.credentials = 'include';  // send httponly cookie for session auth
      if (UI_TOKEN) {
        opts.headers = Object.assign({}, opts.headers || {}, {
          'Authorization': 'Bearer ' + UI_TOKEN,
        });
      }
      if (opts.body && typeof opts.body !== 'string') {
        opts.headers = opts.headers || {};
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(opts.body);
      }
      const r = await fetch(url, opts);
      const ct = r.headers.get('content-type') || '';
      const payload = ct.includes('json') ? await r.json().catch(() => ({})) : await r.text();
      if (!r.ok) {
        const err = (payload && payload.error) || r.statusText;
        throw new Error(err);
      }
      return payload;
    },
    get(url) { return this._fetch(url); },
    post(url, body) { return this._fetch(url, { method: 'POST', body: body || {} }); },
    proxyGet(name, params) {
      const qs = params ? '?' + new URLSearchParams(params).toString() : '';
      return this._fetch('/api/proxy/' + name + qs);
    },
    proxyPost(name, body) {
      return this._fetch('/api/proxy/' + name, { method: 'POST', body: body || {} });
    },
  };

  // ------------------------------------------------------------
  // Toast
  // ------------------------------------------------------------
  function ensureToasts() {
    let el = document.getElementById('toasts');
    if (!el) {
      el = document.createElement('div');
      el.id = 'toasts';
      document.body.appendChild(el);
    }
    return el;
  }
  function toast(message, kind) {
    const host = ensureToasts();
    const t = document.createElement('div');
    t.className = 'toast ' + (kind || '');
    t.textContent = message;
    host.appendChild(t);
    setTimeout(() => {
      t.style.transition = 'opacity .25s';
      t.style.opacity = '0';
      setTimeout(() => t.remove(), 300);
    }, 3500);
  }

  // ------------------------------------------------------------
  // Skeletons & helpers
  // ------------------------------------------------------------
  function skeleton(n) {
    const items = [];
    for (let i = 0; i < n; i++) items.push('<div class="skel-line"></div>');
    return '<div class="skel-card">' + items.join('') + '</div>';
  }
  function escapeHtml(s) {
    if (s == null) return '';
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function fmtDate(iso) {
    if (!iso) return '';
    try {
      const d = new Date(iso);
      return d.toLocaleString();
    } catch (_) { return iso; }
  }

  // ------------------------------------------------------------
  // Page router
  // ------------------------------------------------------------
  const pages = {};
  function registerPage(name, loader) { pages[name] = loader; }

  async function showPage(name, btn) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    const page = document.getElementById('page-' + name);
    if (page) page.classList.add('active');
    if (btn) btn.classList.add('active');
    else {
      const auto = document.querySelector('[data-nav="' + name + '"]');
      if (auto) auto.classList.add('active');
    }
    const loader = pages[name];
    if (loader) {
      try { await loader(page); }
      catch (e) { toast('Ошибка: ' + e.message, 'error'); }
    }
  }
  window.showPage = showPage;

  // ------------------------------------------------------------
  // Project dashboard
  // ------------------------------------------------------------
  registerPage('project', async (page) => {
    const summaryEl = page.querySelector('#proj-summary');
    const contextEl = page.querySelector('#proj-context');
    const statsEl = page.querySelector('#proj-stats');
    summaryEl.innerHTML = skeleton(3);
    contextEl.innerHTML = skeleton(4);
    try {
      const data = await api.get('/api/project/summary');
      const totals = data.totals || {};
      const totalCount = Object.values(totals).reduce((s, v) => s + (Array.isArray(v) ? v.length : 0), 0);
      statsEl.innerHTML = `
        <div class="stat"><div class="stat-value">${totalCount}</div><div class="stat-label">Entries</div></div>
        <div class="stat"><div class="stat-value">${(data.completed || []).length}</div><div class="stat-label">Completed</div></div>
        <div class="stat"><div class="stat-value">${(data.decisions || []).length}</div><div class="stat-label">Decisions</div></div>
        <div class="stat"><div class="stat-value">${(data.blockers || []).length}</div><div class="stat-label">Blockers</div></div>`;
      summaryEl.textContent = data.context || '(no context)';
      contextEl.textContent = data.context || '(no context)';
    } catch (e) {
      summaryEl.textContent = 'Error: ' + e.message;
      contextEl.textContent = '';
    }
  });

  // ------------------------------------------------------------
  // Activity feed
  // ------------------------------------------------------------
  registerPage('activity', async (page) => {
    const list = page.querySelector('#activity-list');
    list.innerHTML = skeleton(5);
    try {
      const data = await api.proxyGet('recent', { limit: 50 });
      const items = data.memories || data.items || data.recent || [];
      if (!items.length) { list.innerHTML = '<div class="card">Пусто.</div>'; return; }
      list.innerHTML = items.map(it => `
        <div class="entry">
          <div class="entry-meta">
            <span class="badge ${escapeHtml(it.type || 'note')}">${escapeHtml(it.type || 'note')}</span>
            <span>${fmtDate(it.timestamp || it.created_at)}</span>
          </div>
          <div class="entry-text">${escapeHtml(it.text || it.content || '')}</div>
        </div>`).join('');
    } catch (e) {
      list.innerHTML = '<div class="card">Ошибка: ' + escapeHtml(e.message) + '</div>';
    }
  });

  // ------------------------------------------------------------
  // Files
  // ------------------------------------------------------------
  registerPage('files', async (page) => {
    const list = page.querySelector('#files-list');
    list.innerHTML = skeleton(4);
    try {
      const data = await api.proxyGet('files_list');
      const items = data.files || data.items || [];
      if (!items.length) { list.innerHTML = '<div class="card">Нет файлов.</div>'; return; }
      list.innerHTML = items.map(f => `
        <div class="entry" data-path="${escapeHtml(f.path || f.file_path || '')}">
          <div class="entry-meta">
            <strong>${escapeHtml(f.path || f.file_path || '')}</strong>
            <span>${escapeHtml(f.language || f.project || '')}</span>
          </div>
          <div class="entry-text">${escapeHtml(f.description || f.summary || '')}</div>
        </div>`).join('');
      list.querySelectorAll('.entry').forEach(el => {
        el.style.cursor = 'pointer';
        el.addEventListener('click', async () => {
          const p = el.dataset.path;
          const ctxBox = page.querySelector('#files-context');
          ctxBox.innerHTML = skeleton(3);
          try {
            const c = await api.proxyGet('file_context', { path: p });
            ctxBox.textContent = c.context || c.text || JSON.stringify(c, null, 2);
          } catch (e) { ctxBox.textContent = 'Ошибка: ' + e.message; }
        });
      });
    } catch (e) {
      list.innerHTML = '<div class="card">Ошибка: ' + escapeHtml(e.message) + '</div>';
    }
  });

  window.filesSearch = async function () {
    const q = document.getElementById('files-q').value.trim();
    const list = document.getElementById('files-list');
    list.innerHTML = skeleton(3);
    try {
      const data = await api.proxyGet('files_search', { q });
      const items = data.files || data.items || [];
      list.innerHTML = items.length
        ? items.map(f => `<div class="entry"><strong>${escapeHtml(f.path)}</strong><div>${escapeHtml(f.description || '')}</div></div>`).join('')
        : '<div class="card">Ничего не найдено.</div>';
    } catch (e) { toast('Ошибка: ' + e.message, 'error'); }
  };

  window.filesAdd = async function () {
    const path = document.getElementById('files-path').value.trim();
    const desc = document.getElementById('files-desc').value.trim();
    const proj = document.getElementById('files-project').value.trim();
    if (!path) { toast('Путь обязателен', 'error'); return; }
    try {
      await api.proxyPost('files_add', { path, description: desc, project: proj });
      toast('Файл добавлен', 'success');
      document.getElementById('files-path').value = '';
      document.getElementById('files-desc').value = '';
      showPage('files');
    } catch (e) { toast('Ошибка: ' + e.message, 'error'); }
  };

  // ------------------------------------------------------------
  // Folders
  // ------------------------------------------------------------
  registerPage('folders', async (page) => {
    const list = page.querySelector('#folders-list');
    list.innerHTML = skeleton(3);
    try {
      const data = await api.proxyGet('folders_list');
      const items = data.folders || data.items || [];
      list.innerHTML = items.length
        ? items.map(f => `<div class="entry"><strong>${escapeHtml(f.path || f.folder_path)}</strong><div>${escapeHtml(f.description || '')}</div></div>`).join('')
        : '<div class="card">Пусто.</div>';
    } catch (e) {
      list.innerHTML = '<div class="card">Ошибка: ' + escapeHtml(e.message) + '</div>';
    }
  });

  window.foldersAdd = async function () {
    const path = document.getElementById('folders-path').value.trim();
    const desc = document.getElementById('folders-desc').value.trim();
    if (!path) { toast('Путь обязателен', 'error'); return; }
    try {
      await api.proxyPost('folders_add', { path, description: desc });
      toast('Папка добавлена', 'success');
      document.getElementById('folders-path').value = '';
      document.getElementById('folders-desc').value = '';
      showPage('folders');
    } catch (e) { toast('Ошибка: ' + e.message, 'error'); }
  };

  // ------------------------------------------------------------
  // Projects
  // ------------------------------------------------------------
  registerPage('projects', async (page) => {
    const list = page.querySelector('#projects-list');
    list.innerHTML = skeleton(3);
    try {
      const data = await api.proxyGet('projects_list');
      const items = data.projects || data.items || [];
      list.innerHTML = items.length
        ? items.map(p => `<div class="entry"><strong>${escapeHtml(p.name)}</strong><div>${escapeHtml(p.description || p.path || '')}</div></div>`).join('')
        : '<div class="card">Пусто.</div>';
    } catch (e) {
      list.innerHTML = '<div class="card">Ошибка: ' + escapeHtml(e.message) + '</div>';
    }
  });

  window.projectsAdd = async function () {
    const name = document.getElementById('proj-name').value.trim();
    const path = document.getElementById('proj-path').value.trim();
    const desc = document.getElementById('proj-desc').value.trim();
    if (!name) { toast('Имя обязательно', 'error'); return; }
    try {
      await api.proxyPost('projects_add', { name, path, description: desc });
      toast('Проект добавлен', 'success');
      document.getElementById('proj-name').value = '';
      document.getElementById('proj-path').value = '';
      document.getElementById('proj-desc').value = '';
      showPage('projects');
    } catch (e) { toast('Ошибка: ' + e.message, 'error'); }
  };

  // ------------------------------------------------------------
  // Tokens
  // ------------------------------------------------------------
  registerPage('tokens', async (page) => {
    const sumEl = page.querySelector('#tokens-summary');
    const dailyEl = page.querySelector('#tokens-daily');
    const recentEl = page.querySelector('#tokens-recent');
    sumEl.innerHTML = skeleton(3);
    dailyEl.innerHTML = skeleton(4);
    recentEl.innerHTML = skeleton(5);
    try {
      const s = await api.get('/api/tokens/summary');
      sumEl.innerHTML = `
        <div class="stat"><div class="stat-value">${(s.total_input_tokens || 0).toLocaleString()}</div><div class="stat-label">Input</div></div>
        <div class="stat"><div class="stat-value">${(s.total_output_tokens || 0).toLocaleString()}</div><div class="stat-label">Output</div></div>
        <div class="stat"><div class="stat-value">$${(s.total_cost_usd || 0).toFixed(2)}</div><div class="stat-label">Spent</div></div>
        <div class="stat"><div class="stat-value">$${(s.total_cache_savings_usd || 0).toFixed(2)}</div><div class="stat-label">Cache saved</div></div>`;
    } catch (e) { sumEl.textContent = 'Ошибка: ' + e.message; }
    try {
      const d = await api.proxyGet('tokens_daily');
      const days = Object.entries(d.daily || {}).map(([date, cost]) => ({ date, cost }));
      dailyEl.innerHTML = days.length
        ? '<table class="table"><thead><tr><th>Date</th><th>Cost</th></tr></thead><tbody>'
          + days.map(x => `<tr><td>${escapeHtml(x.date)}</td><td>$${(x.cost || 0).toFixed(4)}</td></tr>`).join('')
          + '</tbody></table>'
        : '<div class="card">Нет данных.</div>';
    } catch (e) { dailyEl.textContent = 'Ошибка: ' + e.message; }
    try {
      const r = await api.get('/api/tokens/recent?limit=20');
      const items = r.entries || [];
      recentEl.innerHTML = items.length
        ? '<table class="table"><thead><tr><th>Time</th><th>Model</th><th>In</th><th>Out</th><th>Cost</th></tr></thead><tbody>'
          + items.map(x => `<tr><td>${escapeHtml(fmtDate(x.timestamp))}</td><td>${escapeHtml(x.model || '')}</td><td>${x.input_tokens || 0}</td><td>${x.output_tokens || 0}</td><td>$${(x.estimated_cost_usd || 0).toFixed(4)}</td></tr>`).join('')
          + '</tbody></table>'
        : '<div class="card">Пока нет запросов.</div>';
    } catch (e) { recentEl.textContent = 'Ошибка: ' + e.message; }
  });

  // ------------------------------------------------------------
  // Agent control
  // ------------------------------------------------------------
  registerPage('agent', async (page) => {
    const statusEl = page.querySelector('#agent-status');
    statusEl.innerHTML = skeleton(2);
    try {
      const s = await api.get('/api/agent/status');
      statusEl.innerHTML = `
        <div class="stat"><div class="stat-value">${s.running ? 'UP' : 'DOWN'}</div><div class="stat-label">Agent</div></div>
        <div class="stat"><div class="stat-value">${escapeHtml(s.api || '')}</div><div class="stat-label">API</div></div>`;
    } catch (e) { statusEl.textContent = 'Ошибка: ' + e.message; }
  });

  window.agentAction = async function (action) {
    try {
      await api.post('/api/agent/' + action);
      toast('Agent ' + action + ' OK', 'success');
      showPage('agent');
    } catch (e) { toast('Ошибка: ' + e.message, 'error'); }
  };

  // ------------------------------------------------------------
  // SQL playground
  // ------------------------------------------------------------
  registerPage('sql', async (page) => {
    const schemaEl = page.querySelector('#sql-schema');
    schemaEl.innerHTML = skeleton(3);
    try {
      const s = await api.get('/api/sql/schema');
      const schemas = s.schemas || [];
      if (!schemas.length) { schemaEl.innerHTML = '<div class="card">Нет таблиц.</div>'; return; }
      schemaEl.innerHTML = schemas.map(sql => {
        const nameMatch = sql.match(/CREATE TABLE\s+(\w+)/i);
        const name = nameMatch ? nameMatch[1] : 'unknown';
        const colMatches = [...sql.matchAll(/\n\s+(\w+)\s+\w+/g)];
        const cols = colMatches.map(m => m[1]).join(', ');
        return `<div class="entry"><strong>${escapeHtml(name)}</strong><div>${escapeHtml(cols)}</div></div>`;
      }).join('');
    } catch (e) { schemaEl.textContent = 'Ошибка: ' + e.message; }
  });

  window.sqlRun = async function () {
    const query = document.getElementById('sql-editor').value.trim();
    const out = document.getElementById('sql-result');
    if (!query) { out.innerHTML = '<div class="sql-error">Пустой запрос.</div>'; return; }
    out.innerHTML = skeleton(3);
    try {
      const r = await api.post('/api/sql/query', { query });
      const cols = r.columns || [];
      const rows = r.rows || [];
      if (!rows.length) { out.innerHTML = '<div class="card">Нет строк.</div>'; return; }
      out.innerHTML = '<table class="table"><thead><tr>'
        + cols.map(c => `<th>${escapeHtml(c)}</th>`).join('')
        + '</tr></thead><tbody>'
        + rows.map(row => '<tr>' + cols.map(c => `<td>${escapeHtml(String(row[c] ?? ''))}</td>`).join('') + '</tr>').join('')
        + '</tbody></table>';
    } catch (e) { out.innerHTML = '<div class="sql-error">' + escapeHtml(e.message) + '</div>'; }
  };

  // ------------------------------------------------------------
  // Quick Capture modal
  // ------------------------------------------------------------
  const QC_TABS = [
    { key: 'note', label: 'Note', endpoint: 'add', field: 'text' },
    { key: 'done', label: 'Done', endpoint: 'add_completed', field: 'text' },
    { key: 'decision', label: 'Decision', endpoint: 'add_decision', field: 'text' },
    { key: 'blocker', label: 'Blocker', endpoint: 'add_blocker', field: 'text' },
  ];
  let qcActive = 'note';

  window.openQuickCapture = function () {
    document.getElementById('qc-backdrop').classList.add('open');
    renderQCTabs();
    setTimeout(() => document.getElementById('qc-text').focus(), 50);
  };
  window.closeQuickCapture = function () {
    document.getElementById('qc-backdrop').classList.remove('open');
  };
  function renderQCTabs() {
    const host = document.getElementById('qc-tabs');
    host.innerHTML = QC_TABS.map(t =>
      `<button class="modal-tab ${t.key === qcActive ? 'active' : ''}" data-key="${t.key}">${t.label}</button>`
    ).join('');
    host.querySelectorAll('button').forEach(b => {
      b.onclick = () => { qcActive = b.dataset.key; renderQCTabs(); };
    });
  }
  window.qcSubmit = async function () {
    const tab = QC_TABS.find(t => t.key === qcActive);
    const text = document.getElementById('qc-text').value.trim();
    if (!text) { toast('Пустой текст', 'error'); return; }
    try {
      const body = {}; body[tab.field] = text;
      await api.proxyPost(tab.endpoint, body);
      toast(tab.label + ' сохранено', 'success');
      document.getElementById('qc-text').value = '';
      closeQuickCapture();
      const active = document.querySelector('.page.active');
      if (active && active.id === 'page-activity') showPage('activity');
    } catch (e) { toast('Ошибка: ' + e.message, 'error'); }
  };

  // ------------------------------------------------------------
  // TerminalPool (xterm.js + JSON WebSocket)
  // ------------------------------------------------------------
  const TerminalPool = {
    ws: null,
    pool: {},
    active: null,
    connected: false,
    queue: [],
    reconnectTimer: null,

    async connect() {
      let wsToken = UI_TOKEN;
      if (!wsToken) {
        try {
          const resp = await api.get('/api/ws-token');
          wsToken = resp.token;
        } catch (e) {
          console.error('Failed to get WS token', e);
          return;
        }
      }
      const url = 'ws://127.0.0.1:5001/?token=' + encodeURIComponent(wsToken);
      this.ws = new WebSocket(url);
      this.ws.onopen = () => {
        this.connected = true;
        while (this.queue.length) this.ws.send(this.queue.shift());
        this.send({ type: 'list' });
      };
      this.ws.onmessage = (ev) => {
        let msg; try { msg = JSON.parse(ev.data); } catch (_) { return; }
        this.handle(msg);
      };
      this.ws.onclose = () => {
        this.connected = false;
        Object.values(this.pool).forEach(t => { t.dead = true; this.markTab(t.id); });
        if (!this.reconnectTimer) {
          this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            this.connect();
          }, 2000);
        }
      };
      this.ws.onerror = () => toast('WebSocket error', 'error');
    },

    send(msg) {
      const s = JSON.stringify(msg);
      if (this.connected) this.ws.send(s);
      else this.queue.push(s);
    },

    new(shell) {
      const pane = document.createElement('div');
      pane.className = 'term-pane';
      document.getElementById('termPanes').appendChild(pane);

      const term = new Terminal({
        fontFamily: 'IBM Plex Mono, monospace',
        fontSize: 13,
        cursorBlink: true,
        theme: {
          background: '#0c0b09',
          foreground: '#e8ded0',
          cursor: '#e8a84c',
          selectionBackground: 'rgba(232,168,76,.3)',
        },
        convertEol: true,
        scrollback: 10000,
      });
      const fit = new FitAddon.FitAddon();
      term.loadAddon(fit);
      term.open(pane);
      try { term.loadAddon(new WebglAddon.WebglAddon()); } catch (_) { /* webgl unavail */ }

      fit.fit();
      const dims = { cols: term.cols, rows: term.rows };

      const localId = 'pending-' + Math.random().toString(36).slice(2, 8);
      const rec = {
        id: localId, term, fit, pane,
        shell: shell || 'bash',
        title: (shell || 'shell') + ' …',
        dead: false,
        onData: null,
      };
      this.pool[localId] = rec;

      rec.onData = term.onData((data) => {
        if (rec.dead) return;
        this.send({ type: 'input', id: rec.id, data });
      });

      this.send({ type: 'open', id: localId, shell: shell || 'bash', cols: dims.cols, rows: dims.rows });
      this.renderTabs();
      this.activate(localId);

      const ro = new ResizeObserver(() => {
        try { fit.fit(); } catch (_) { /* pane not in DOM */ }
        this.send({ type: 'resize', id: rec.id, cols: term.cols, rows: term.rows });
      });
      ro.observe(pane);
      rec.ro = ro;
    },

    close(id) {
      const rec = this.pool[id];
      if (!rec) return;
      this.send({ type: 'close', id });
      try { rec.onData && rec.onData.dispose(); } catch (_) {}
      try { rec.ro && rec.ro.disconnect(); } catch (_) {}
      try { rec.term.dispose(); } catch (_) {}
      rec.pane.remove();
      delete this.pool[id];
      const ids = Object.keys(this.pool);
      this.active = ids[0] || null;
      this.renderTabs();
      if (this.active) this.activate(this.active);
    },

    activate(id) {
      this.active = id;
      Object.entries(this.pool).forEach(([k, v]) => {
        v.pane.classList.toggle('active', k === id);
      });
      const rec = this.pool[id];
      if (rec) {
        try { rec.fit.fit(); } catch (_) {}
        rec.term.focus();
      }
      this.renderTabs();
    },

    renderTabs() {
      const host = document.getElementById('termTabs');
      if (!host) return;
      host.innerHTML = Object.values(this.pool).map(t => `
        <div class="term-tab ${t.id === this.active ? 'active' : ''} ${t.dead ? 'dead' : ''}" data-id="${t.id}">
          <span>${escapeHtml(t.title)}</span>
          <button class="term-tab-close" data-close="${t.id}" title="Закрыть">×</button>
        </div>`).join('');
      host.querySelectorAll('.term-tab').forEach(el => {
        el.onclick = (e) => {
          if (e.target.dataset.close) { this.close(e.target.dataset.close); return; }
          this.activate(el.dataset.id);
        };
      });
    },

    markTab(id) { this.renderTabs(); },

    handle(msg) {
      if (msg.type === 'opened') {
        // resolve pending local id to server id
        const oldId = msg.local_id || msg.requested_id;
        const rec = this.pool[oldId] || this.pool[msg.id];
        if (rec && rec.id !== msg.id) {
          delete this.pool[rec.id];
          rec.id = msg.id;
          this.pool[msg.id] = rec;
        }
        if (rec) {
          rec.title = (msg.shell || rec.shell) + ' · ' + msg.id.slice(0, 4);
        }
        if (this.active && this.active.startsWith('pending-')) this.active = msg.id;
        this.renderTabs();
      } else if (msg.type === 'output') {
        const rec = this.pool[msg.id];
        if (rec) rec.term.write(msg.data);
      } else if (msg.type === 'exit') {
        const rec = this.pool[msg.id];
        if (rec) {
          rec.dead = true;
          rec.term.write('\r\n\x1b[33m[exit code ' + msg.code + ']\x1b[0m\r\n');
          this.markTab(msg.id);
        }
      } else if (msg.type === 'sessions') {
        // ignore for now — pool is source of truth for this client
      } else if (msg.type === 'error') {
        toast('Terminal: ' + (msg.message || 'error'), 'error');
      }
    },
  };
  window.TerminalPool = TerminalPool;
  window.newTerminal = (shell) => TerminalPool.new(shell);

  // ------------------------------------------------------------
  // Keyboard shortcuts
  // ------------------------------------------------------------
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault(); openQuickCapture();
    } else if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 't') {
      e.preventDefault(); TerminalPool.new('bash');
    } else if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'w') {
      e.preventDefault();
      if (TerminalPool.active) TerminalPool.close(TerminalPool.active);
    } else if (e.key === 'Escape') {
      closeQuickCapture();
    }
  });

  // ------------------------------------------------------------
  // Boot
  // ------------------------------------------------------------
  window.addEventListener('DOMContentLoaded', () => {
    TerminalPool.connect();
    showPage('project');
  });

})();
