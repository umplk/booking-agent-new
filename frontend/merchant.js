/* ============================================================
 * 智约 · 商家管理后台 — 前端逻辑
 * 原生 JS · 复用 SaaS 设计系统 · 对接后端管理 API
 * 后端：FastAPI  http://127.0.0.1:8000
 * ============================================================ */

/* ============================================================
 * 0. API 配置与请求封装
 * ============================================================ */
const API_BASE = 'http://127.0.0.1:8000';

function getToken() { return localStorage.getItem('token') || ''; }
function setToken(t) { localStorage.setItem('token', t); }
function clearToken() { localStorage.removeItem('token'); }

async function apiFetch(path, options) {
  options = options || {};
  options.headers = options.headers || {};
  const token = getToken();
  if (token) options.headers['Authorization'] = 'Bearer ' + token;
  if (options.body && typeof options.body !== 'string') {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }
  let resp;
  try { resp = await fetch(API_BASE + path, options); }
  catch (e) { throw { message: '无法连接服务器，请检查后端是否启动' }; }
  let json;
  try { json = await resp.json(); }
  catch (e) { throw { message: '服务器返回格式错误（HTTP ' + resp.status + '）' }; }
  if (json.code && json.code !== 200) throw { message: json.message || '请求失败', code: json.code };
  if (!resp.ok) throw { message: json.message || ('HTTP ' + resp.status), code: resp.status };
  return json.data;
}

/* ============================================================
 * 1. 工具函数
 * ============================================================ */
function fmtTime(t) { return t ? String(t).slice(0, 5) : ''; }
function fmtDateTime(dt) { return dt ? String(dt).replace('T', ' ').slice(0, 16) : ''; }
function isoDate(dt) { return dt ? String(dt).slice(0, 10) : ''; }
function isoTime(dt) { return dt ? String(dt).slice(11, 16) : ''; }
function todayStr() {
  const d = new Date();
  const p = n => n < 10 ? '0' + n : '' + n;
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate());
}
function esc(str) {
  return String(str == null ? '' : str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function mergeSlots(freeSlots) {
  if (!freeSlots || !freeSlots.length) return [];
  const sorted = freeSlots.slice().sort((a, b) => a.start < b.start ? -1 : (a.start > b.start ? 1 : 0));
  const out = [];
  let start = sorted[0].start, prevEnd = sorted[0].end;
  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i].start === prevEnd) prevEnd = sorted[i].end;
    else { out.push({ start, end: prevEnd }); start = sorted[i].start; prevEnd = sorted[i].end; }
  }
  out.push({ start, end: prevEnd });
  return out;
}
function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  return e;
}
function statusText(s) {
  return { confirmed: '已确认', pending: '待确认', cancelled: '已取消', completed: '已完成' }[s] || s;
}
function statusBadgeClass(s) {
  return { confirmed: 'badge-success', pending: 'badge-warning', cancelled: 'badge-danger', completed: 'badge-info' }[s] || 'badge-info';
}

/* ============================================================
 * 2. 路由（页面切换 + 顶栏标题）
 * ============================================================ */
const PAGE_META = {
  dashboard: ['数据概览', '全平台预约数据与运营概览'],
  bookings:   ['预约管理', '查看与处理全平台用户预约'],
  resources:  ['资源管理', '管理各场景下的可预约资源'],
  rules:      ['预约规则', '查看与配置各场景的预约规则'],
  scenarios:  ['预约场景', '创建与管理可配置预约场景'],
  profile:    ['个人中心', '查看与编辑个人信息'],
};

const navItems = document.querySelectorAll('.nav-item');
const pages = document.querySelectorAll('.page');

function switchPage(name) {
  pages.forEach(p => p.classList.remove('active'));
  const target = document.querySelector('.page[data-page="' + name + '"]');
  if (target) target.classList.add('active');
  navItems.forEach(a => a.classList.toggle('active', a.dataset.page === name));
  const meta = PAGE_META[name] || ['', ''];
  document.getElementById('pageTitle').textContent = meta[0];
  document.getElementById('pageSubtitle').textContent = meta[1];
  document.getElementById('userDropdown').classList.remove('show');
  closeSidebarMobile();

  if (name === 'dashboard') loadDashboard();
  if (name === 'bookings') loadBookingsPage();
  if (name === 'resources') loadResourcesPage();
  if (name === 'rules') loadRulesPage();
  if (name === 'scenarios') loadScenariosPage();
  if (name === 'profile') loadProfilePage();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

navItems.forEach(a => a.addEventListener('click', e => { e.preventDefault(); switchPage(a.dataset.page); }));

document.querySelectorAll('[data-quick]').forEach(b => b.addEventListener('click', () => {
  const q = b.dataset.quick;
  if (q === 'agent') openAgent();
  else switchPage(q);
}));

/* 侧栏响应式 */
const sidebar = document.getElementById('sidebar');
document.getElementById('sidebarToggle').addEventListener('click', () => sidebar.classList.toggle('show'));
function closeSidebarMobile() { sidebar.classList.remove('show'); }

/* 用户下拉 */
const userDropdown = document.getElementById('userDropdown');
document.getElementById('userChip').addEventListener('click', e => {
  e.stopPropagation();
  userDropdown.classList.toggle('show');
});
document.addEventListener('click', () => userDropdown.classList.remove('show'));
document.getElementById('udProfile').addEventListener('click', () => switchPage('profile'));
document.getElementById('udLogout').addEventListener('click', logout);

/* ============================================================
 * 3. 认证
 * ============================================================ */
let currentUser = null;
const loginModal = document.getElementById('loginModal');
const registerModal = document.getElementById('registerModal');

function showLoginError(m) { document.getElementById('loginError').textContent = m; }
function showRegError(m) { document.getElementById('regError').textContent = m; }

document.getElementById('btnGoRegister').addEventListener('click', () => {
  showLoginError(''); loginModal.classList.add('hidden'); registerModal.classList.remove('hidden');
});
document.getElementById('btnBackLogin').addEventListener('click', () => {
  showRegError(''); registerModal.classList.add('hidden'); loginModal.classList.remove('hidden');
});

async function doLogin() {
  const u = document.getElementById('loginUsername').value.trim();
  const p = document.getElementById('loginPassword').value;
  if (!u) return showLoginError('请输入用户名');
  if (!p) return showLoginError('请输入密码');
  showLoginError('');
  try {
    const data = await apiFetch('/api/auth/login', { method: 'POST', body: { username: u, password: p } });
    setToken(data.access_token);
    await afterLogin();
  } catch (e) { showLoginError(e.message || '登录失败'); }
}
document.getElementById('btnLogin').addEventListener('click', doLogin);
['loginUsername', 'loginPassword'].forEach(id => document.getElementById(id).addEventListener('keydown', e => { if (e.key === 'Enter') doLogin(); }));

async function doRegister() {
  const u = document.getElementById('regUsername').value.trim();
  const name = document.getElementById('regName').value.trim();
  const sid = document.getElementById('regStudentId').value.trim();
  const email = document.getElementById('regEmail').value.trim();
  const p = document.getElementById('regPassword').value;
  if (!u || u.length < 3) return showRegError('用户名至少 3 位');
  if (!email) return showRegError('请输入邮箱');
  if (!p || p.length < 6) return showRegError('密码至少 6 位');
  showRegError('');
  try {
    await apiFetch('/api/auth/register', { method: 'POST', body: { username: u, email, password: p, name: name || null, student_id: sid || null } });
    registerModal.classList.add('hidden');
    document.getElementById('loginUsername').value = u;
    document.getElementById('loginPassword').value = p;
    await doLogin();
  } catch (e) { showRegError(e.message || '注册失败'); }
}
document.getElementById('btnRegister').addEventListener('click', doRegister);

async function afterLogin() {
  try { currentUser = await apiFetch('/api/users/me'); }
  catch (e) { clearToken(); showLoginError(e.message || '获取用户信息失败'); loginModal.classList.remove('hidden'); return; }
  renderUserChip();
  loginModal.classList.add('hidden');
  registerModal.classList.add('hidden');
  switchPage('dashboard');
}

function renderUserChip() {
  const name = currentUser ? (currentUser.name || currentUser.username) : '未登录';
  document.getElementById('userName').textContent = name;
  document.getElementById('userRole').textContent = currentUser ? (currentUser.role === 'admin' ? '管理员' : '普通用户') : '点击登录';
  document.getElementById('userAvatar').textContent = name.charAt(0);
  document.getElementById('udName').textContent = name;
  document.getElementById('udEmail').textContent = currentUser ? (currentUser.email || '—') : '—';
  document.getElementById('udAvatar').textContent = name.charAt(0);
}

function logout() {
  clearToken();
  currentUser = null;
  renderUserChip();
  userDropdown.classList.remove('show');
  loginModal.classList.remove('hidden');
}

/* ============================================================
 * 4. 数据概览页（商家视角）
 * ============================================================ */
async function loadDashboard() {
  let scenarios = [];
  try {
    const data = await apiFetch('/api/scenarios?page=1&page_size=200&include_inactive=true');
    scenarios = data.items || [];
  } catch (e) {}

  /* 资源总数 */
  const resCounts = await Promise.all(scenarios.map(s =>
    apiFetch('/api/scenarios/' + s.id + '/resources?page=1&page_size=1').then(d => d.total || 0).catch(() => 0)
  ));
  document.getElementById('dashResourceCount').textContent = resCounts.reduce((a, b) => a + b, 0);

  /* 全平台预约（admin API） */
  let allRes = [];
  try { allRes = await apiFetch('/api/reservations/admin?status=all'); } catch (e) {}
  document.getElementById('dashTotalCount').textContent = allRes.length;
  document.getElementById('dashActiveCount').textContent = allRes.filter(r => r.status === 'confirmed' || r.status === 'pending').length;
  const today = todayStr();
  document.getElementById('dashTodayCount').textContent = allRes.filter(r => isoDate(r.start_time) === today && r.status !== 'cancelled').length;

  /* 最近预约 */
  const recentWrap = document.getElementById('dashRecent');
  const recentEmpty = document.getElementById('dashRecentEmpty');
  recentWrap.innerHTML = '';
  const recent = allRes.slice().sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, 5);
  if (!recent.length) { recentEmpty.classList.remove('hidden'); }
  else {
    recentEmpty.classList.add('hidden');
    recent.forEach(r => {
      const isCancel = r.status === 'cancelled';
      const item = el('div', 'recent-item');
      item.appendChild(el('div', 'ri-tag ' + (isCancel ? 'cancel' : 'valid'), isCancel ? '❌' : '✅'));
      const main = el('div', 'ri-main');
      main.appendChild(el('div', 'ri-title', esc((r.scenario_name || '') + ' · ' + (r.resource_code || r.resource_name || ''))));
      main.appendChild(el('div', 'ri-meta', esc((r.user_name || r.user_username || '—')) + ' · ' + isoDate(r.start_time) + ' ' + isoTime(r.start_time) + '-' + isoTime(r.end_time) + ' · ' + statusText(r.status)));
      item.appendChild(main);
      recentWrap.appendChild(item);
    });
  }

  /* 场景一览 */
  const grid = document.getElementById('dashScenarioGrid');
  grid.innerHTML = '';
  if (!scenarios.length) {
    grid.appendChild(el('div', 'empty-state sm', '<span class="empty-icon">🎯</span><p>暂无场景</p>'));
    return;
  }
  scenarios.forEach(s => {
    const card = el('div', 'so-card');
    card.innerHTML =
      '<div class="so-head"><span class="so-name">' + esc(s.name) + '</span>' +
      '<span class="badge ' + (s.is_active ? 'badge-success' : 'badge-danger') + '">' + (s.is_active ? '启用' : '停用') + '</span></div>' +
      '<div class="so-desc">' + esc(s.description || '暂无描述') + '</div>' +
      '<div class="so-meta"><span>步长 <b>' + s.time_step_minutes + '</b>分</span><span>时长 <b>' + s.min_duration_minutes + '-' + s.max_duration_minutes + '</b>分</span><span>最多提前 <b>' + s.max_advance_days + '</b>天</span></div>';
    card.addEventListener('click', () => { switchPage('resources'); });
    grid.appendChild(card);
  });
}

/* ============================================================
 * 5. 预约管理页
 * ============================================================ */
let bmScenarios = [];
let bmAllRes = [];

async function loadBookingsPage() {
  if (!bmScenarios.length) {
    try {
      const data = await apiFetch('/api/scenarios?page=1&page_size=200&include_inactive=true');
      bmScenarios = data.items || [];
    } catch (e) { bmScenarios = []; }
    const sel = document.getElementById('bmScenario');
    bmScenarios.forEach(s => { const o = el('option'); o.value = s.id; o.textContent = s.name; sel.appendChild(o); });
  }
  await queryBookings();
}

document.getElementById('btnBmQuery').addEventListener('click', queryBookings);
document.getElementById('bmSearch').addEventListener('input', renderBookingsTable);
document.getElementById('bmScenario').addEventListener('change', queryBookings);
document.getElementById('bmStatus').addEventListener('change', queryBookings);
document.getElementById('bmDate').addEventListener('change', queryBookings);

async function queryBookings() {
  const scenarioId = document.getElementById('bmScenario').value;
  const status = document.getElementById('bmStatus').value;
  const date = document.getElementById('bmDate').value;
  let path = '/api/reservations/admin?status=' + encodeURIComponent(status);
  if (scenarioId) path += '&scenario_id=' + scenarioId;
  if (date) path += '&date=' + encodeURIComponent(date);
  try { bmAllRes = await apiFetch(path); }
  catch (e) { bmAllRes = []; showResult({ type: 'fail', title: '查询失败', desc: e.message || '请检查权限' }); }
  renderBookingsTable();
}

function renderBookingsTable() {
  const tbody = document.getElementById('bmTbody');
  const empty = document.getElementById('bmEmpty');
  const count = document.getElementById('bmCount');
  const kw = document.getElementById('bmSearch').value.trim().toLowerCase();
  tbody.innerHTML = '';
  let list = bmAllRes;
  if (kw) list = list.filter(r => ((r.user_name || '') + (r.user_username || '') + (r.resource_code || '') + (r.resource_name || '')).toLowerCase().indexOf(kw) >= 0);
  count.textContent = list.length + ' 条记录';
  if (!list.length) { empty.classList.remove('hidden'); return; }
  empty.classList.add('hidden');
  list.forEach(r => {
    const tr = el('tr');
    tr.innerHTML =
      '<td class="col-id">' + r.id + '</td>' +
      '<td>' + esc(r.user_name || r.user_username || '—') + '</td>' +
      '<td>' + esc(r.scenario_name || '—') + '</td>' +
      '<td class="col-code">' + esc(r.resource_code || r.resource_name || '—') + '</td>' +
      '<td>' + isoDate(r.start_time) + '</td>' +
      '<td>' + isoTime(r.start_time) + '-' + isoTime(r.end_time) + '</td>' +
      '<td><span class="badge ' + statusBadgeClass(r.status) + '">' + statusText(r.status) + '</span></td>' +
      '<td>' + fmtDateTime(r.created_at) + '</td>' +
      '<td><div class="admin-actions"></div></td>';
    const act = tr.querySelector('.admin-actions');
    act.style.display = 'flex'; act.style.gap = '6px';
    if (r.status !== 'cancelled' && r.status !== 'completed') {
      const btn = el('button', 'btn-act danger', '取消');
      btn.addEventListener('click', () => cancelBooking(r));
      act.appendChild(btn);
    } else {
      act.appendChild(el('span', 'attr-chip', '—'));
    }
    tbody.appendChild(tr);
  });
}

async function cancelBooking(r) {
  if (!confirm('确认取消该预约？\n用户：' + (r.user_name || r.user_username || '—') + '\n资源：' + (r.resource_code || r.resource_name) + '\n时段：' + isoDate(r.start_time) + ' ' + isoTime(r.start_time) + '-' + isoTime(r.end_time))) return;
  try {
    await apiFetch('/api/reservations/' + r.id + '/cancel', { method: 'PUT' });
    await queryBookings();
    showResult({ type: 'success', title: '已取消预约', desc: '资源已释放。' });
  } catch (e) { showResult({ type: 'fail', title: '取消失败', desc: e.message }); }
}

/* ============================================================
 * 6. 预约场景页（配置管理）
 * ============================================================ */
let scenarioPageList = [];

async function loadScenariosPage() {
  try {
    const data = await apiFetch('/api/scenarios?page=1&page_size=200&mine=false&include_inactive=true');
    scenarioPageList = data.items || [];
  } catch (e) { scenarioPageList = []; }
  renderScenarioCards();
}

document.getElementById('scenarioSearch').addEventListener('input', renderScenarioCards);

function renderScenarioCards() {
  const grid = document.getElementById('scenarioCardGrid');
  const empty = document.getElementById('scenarioEmpty');
  const kw = document.getElementById('scenarioSearch').value.trim().toLowerCase();
  grid.innerHTML = '';
  const list = kw ? scenarioPageList.filter(s => s.name.toLowerCase().indexOf(kw) >= 0) : scenarioPageList;
  if (!list.length) { empty.classList.remove('hidden'); return; }
  empty.classList.add('hidden');
  list.forEach(s => {
    const card = el('div', 'scen-card');
    card.innerHTML =
      '<div class="scen-card-head">' +
        '<div class="scen-card-name">' + esc(s.name) + '</div>' +
        '<div class="scen-card-desc">' + esc(s.description || '暂无描述') + '</div>' +
      '</div>' +
      '<div class="scen-card-body"><div class="scen-rules">' +
        '<div class="scen-rule"><span>时段步长</span><span>' + s.time_step_minutes + ' 分钟</span></div>' +
        '<div class="scen-rule"><span>时长范围</span><span>' + s.min_duration_minutes + '-' + s.max_duration_minutes + ' 分钟</span></div>' +
        '<div class="scen-rule"><span>最多提前</span><span>' + s.max_advance_days + ' 天</span></div>' +
        '<div class="scen-rule"><span>活跃预约上限</span><span>' + s.max_active_per_user + ' 个</span></div>' +
        '<div class="scen-rule"><span>当日预约</span><span>' + (s.allow_same_day ? '允许' : '不允许') + '</span></div>' +
        '<div class="scen-rule"><span>状态</span><span>' + (s.is_active ? '启用' : '停用') + '</span></div>' +
      '</div></div>' +
      '<div class="scen-card-foot">' +
        '<button class="btn-act" data-act="res">管理资源</button>' +
        '<button class="btn-act primary" data-act="edit">编辑</button>' +
        '<button class="btn-act danger" data-act="del">删除</button>' +
      '</div>';
    card.querySelector('[data-act="res"]').addEventListener('click', () => switchPage('resources'));
    card.querySelector('[data-act="edit"]').addEventListener('click', () => openScenarioModal(s));
    card.querySelector('[data-act="del"]').addEventListener('click', () => deleteScenario(s));
    grid.appendChild(card);
  });
}

document.getElementById('btnNewScenario').addEventListener('click', () => openScenarioModal(null));

/* ============================================================
 * 7. 资源管理页
 * ============================================================ */
let resMgmtScenarios = [];
let resMgmtCurrent = null;
let resMgmtResources = [];
let editingResourceId = null;

async function loadResourcesPage() {
  if (!resMgmtScenarios.length) {
    try {
      const data = await apiFetch('/api/scenarios?page=1&page_size=200&include_inactive=true');
      resMgmtScenarios = data.items || [];
    } catch (e) { resMgmtScenarios = []; }
    const sel = document.getElementById('resMgmtScenario');
    sel.innerHTML = '';
    resMgmtScenarios.forEach(s => { const o = el('option'); o.value = s.id; o.textContent = s.name; sel.appendChild(o); });
  }
  if (resMgmtScenarios.length) {
    resMgmtCurrent = resMgmtScenarios[0];
    await loadResMgmtResources();
  } else {
    document.getElementById('resMgmtTbody').innerHTML = '';
    document.getElementById('resMgmtEmpty').classList.remove('hidden');
  }
}

document.getElementById('resMgmtScenario').addEventListener('change', async function () {
  const id = parseInt(this.value, 10);
  resMgmtCurrent = resMgmtScenarios.find(s => s.id === id);
  await loadResMgmtResources();
});
document.getElementById('resSearch').addEventListener('input', renderResMgmtTable);
document.getElementById('btnNewResource').addEventListener('click', () => openResourceModal(null));

async function loadResMgmtResources() {
  if (!resMgmtCurrent) return;
  try {
    const data = await apiFetch('/api/scenarios/' + resMgmtCurrent.id + '/resources?page=1&page_size=500');
    resMgmtResources = data.items || [];
  } catch (e) { resMgmtResources = []; }
  renderResMgmtTable();
}

function renderResMgmtTable() {
  const tbody = document.getElementById('resMgmtTbody');
  const empty = document.getElementById('resMgmtEmpty');
  const count = document.getElementById('resMgmtCount');
  const kw = document.getElementById('resSearch').value.trim().toLowerCase();
  tbody.innerHTML = '';
  const list = kw ? resMgmtResources.filter(r => (r.name + r.code).toLowerCase().indexOf(kw) >= 0) : resMgmtResources;
  count.textContent = list.length + ' 个资源';
  if (!list.length) { empty.classList.remove('hidden'); return; }
  empty.classList.add('hidden');
  list.forEach(r => {
    const tr = el('tr');
    tr.innerHTML =
      '<td class="col-id">' + r.id + '</td>' +
      '<td class="col-code">' + esc(r.code) + '</td>' +
      '<td>' + esc(r.name) + '</td>' +
      '<td>' + fmtTime(r.open_start) + '-' + fmtTime(r.open_end) + '</td>' +
      '<td class="col-attrs"><div class="attr-chips"></div></td>' +
      '<td><span class="badge ' + (r.is_active ? 'badge-success' : 'badge-danger') + '">' + (r.is_active ? '启用' : '停用') + '</span></td>' +
      '<td><div class="admin-actions"></div></td>';
    const chips = tr.querySelector('.attr-chips');
    Object.keys(r.attributes || {}).forEach(k => {
      const v = r.attributes[k];
      const chip = el('span', 'attr-chip' + (v === true ? ' bool-true' : (v === false ? ' bool-false' : '')));
      chip.textContent = v === true ? k : (v === false ? '¬' + k : k + '=' + v);
      chips.appendChild(chip);
    });
    const act = tr.querySelector('.admin-actions');
    act.style.display = 'flex'; act.style.gap = '6px';
    const edit = el('button', 'btn-act primary', '编辑'); edit.addEventListener('click', () => openResourceModal(r));
    const del = el('button', 'btn-act danger', '删除'); del.addEventListener('click', () => deleteResource(r));
    act.appendChild(edit); act.appendChild(del);
    tbody.appendChild(tr);
  });
}

/* AI 生成 */
document.getElementById('btnAiGenerate').addEventListener('click', async () => {
  if (!resMgmtCurrent) return;
  const input = document.getElementById('adminGenInput');
  const hint = document.getElementById('adminGenHint');
  const desc = input.value.trim();
  if (!desc) { hint.textContent = '请先输入资源描述'; return; }
  hint.textContent = 'AI 生成中…';
  try {
    const data = await apiFetch('/api/scenarios/' + resMgmtCurrent.id + '/resources/generate', { method: 'POST', body: { description: desc } });
    input.value = '';
    hint.textContent = (data.count || 0) ? '已生成 ' + data.count + ' 个资源' : '未生成新资源（编号可能已存在）';
    await loadResMgmtResources();
    showResult({ type: 'success', title: '生成成功', desc: 'AI 已根据「' + desc + '」生成 ' + (data.count || 0) + ' 个资源。' });
  } catch (e) { hint.textContent = '生成失败'; showResult({ type: 'fail', title: '生成失败', desc: e.message || '请稍后重试' }); }
});

/* 可用性查询 */
document.getElementById('btnQueryAvail').addEventListener('click', async () => {
  if (!resMgmtCurrent) return;
  const date = document.getElementById('adminAvailDate').value;
  const hint = document.getElementById('adminAvailHint');
  const result = document.getElementById('adminAvailResult');
  result.innerHTML = '';
  if (!date) { hint.textContent = '请先选择查询日期'; return; }
  hint.textContent = '查询中…';
  try {
    const data = await apiFetch('/api/scenarios/' + resMgmtCurrent.id + '/availability?date=' + date);
    result.appendChild(el('div', 'admin-avail-summary', '📅 ' + date + ' · 共 ' + (data.resources || []).length + ' 个资源 · 合计 ' + (data.free_slots_count || 0) + ' 个空闲时段'));
    (data.resources || []).forEach(r => {
      const card = el('div', 'admin-avail-resource');
      card.innerHTML =
        '<div class="ar-head"><span class="ar-code">' + esc(r.code) + '</span><span class="ar-name">' + esc(r.name) + '</span>' +
        '<span class="badge ' + (r.is_active ? 'badge-success' : 'badge-danger') + '">' + (r.is_active ? '启用' : '停用') + '</span></div>';
      const slots = el('div', 'admin-avail-slots');
      const free = r.free_slots || [];
      if (!free.length) slots.appendChild(el('span', 'avail-slot none', '当天无空闲'));
      else mergeSlots(free).forEach(m => slots.appendChild(el('span', 'avail-slot', m.start + '-' + m.end)));
      card.appendChild(slots);
      result.appendChild(card);
    });
    hint.textContent = '已加载 ' + (data.resources || []).length + ' 个资源在 ' + date + ' 的可预约状态';
  } catch (e) { hint.textContent = '查询失败'; showResult({ type: 'fail', title: '查询失败', desc: e.message }); }
});

/* ============================================================
 * 8. 预约规则页
 * ============================================================ */
async function loadRulesPage() {
  const grid = document.getElementById('rulesGrid');
  let list = [];
  try { const data = await apiFetch('/api/scenarios?page=1&page_size=200&include_inactive=true'); list = data.items || []; }
  catch (e) {}
  grid.innerHTML = '';
  if (!list.length) { grid.appendChild(el('div', 'empty-state', '<span class="empty-icon">⚙️</span><p>暂无场景规则</p>')); return; }
  list.forEach(s => {
    const card = el('div', 'rule-card');
    card.innerHTML =
      '<div class="rule-card-head"><span class="rule-card-name">' + esc(s.name) + '</span>' +
      '<span class="badge ' + (s.is_active ? 'badge-success' : 'badge-danger') + '">' + (s.is_active ? '启用' : '停用') + '</span></div>' +
      '<div class="rule-card-body">' +
        ruleField('时段步长', s.time_step_minutes + ' 分钟') +
        ruleField('最小时长', s.min_duration_minutes + ' 分钟') +
        ruleField('最大时长', s.max_duration_minutes + ' 分钟') +
        ruleField('最多提前天数', s.max_advance_days + ' 天') +
        ruleField('至少提前', s.min_advance_minutes ? s.min_advance_minutes + ' 分钟' : '即时预约', !s.min_advance_minutes) +
        ruleField('每日上限', s.max_minutes_per_day ? s.max_minutes_per_day + ' 分钟' : '不限制', !s.max_minutes_per_day) +
        ruleField('允许当日预约', s.allow_same_day ? '允许' : '不允许', !s.allow_same_day) +
        ruleField('活跃预约上限', s.max_active_per_user + ' 个') +
        ruleField('取消需提前', s.cancel_before_minutes != null ? s.cancel_before_minutes + ' 分钟' : '不限制', s.cancel_before_minutes == null) +
      '</div>' +
      '<div class="rule-card-foot"><button class="btn-act primary">编辑规则</button></div>';
    card.querySelector('button').addEventListener('click', () => openScenarioModal(s));
    grid.appendChild(card);
  });
}

function ruleField(label, value, muted) {
  return '<div class="rule-field"><span class="rf-label">' + label + '</span><span class="rf-value' + (muted ? ' muted' : '') + '">' + value + '</span></div>';
}

/* ============================================================
 * 9. 个人中心页
 * ============================================================ */
function loadProfilePage() {
  if (!currentUser) return;
  const name = currentUser.name || currentUser.username;
  document.getElementById('profileAvatar').textContent = name.charAt(0);
  document.getElementById('profileName').textContent = name;
  document.getElementById('profileEmail').textContent = currentUser.email || '—';
  document.getElementById('profileRoleBadge').textContent = currentUser.role === 'admin' ? '管理员' : '普通用户';
  document.getElementById('profileSidBadge').textContent = '学号：' + (currentUser.student_id || '—');
  if (currentUser.role === 'admin') {
    apiFetch('/api/reservations/admin?status=all').then(list => {
      document.getElementById('statTotal').textContent = list.length;
      document.getElementById('statValid').textContent = list.filter(r => r.status === 'confirmed' || r.status === 'pending').length;
      document.getElementById('statCancel').textContent = list.filter(r => r.status === 'cancelled').length;
    }).catch(() => {});
  } else {
    document.getElementById('statTotal').textContent = '—';
    document.getElementById('statValid').textContent = '—';
    document.getElementById('statCancel').textContent = '—';
  }
}

/* 编辑资料 */
document.getElementById('btnEditProfile').addEventListener('click', () => {
  if (!currentUser) return;
  document.getElementById('peName').value = currentUser.name || '';
  document.getElementById('peStudentId').value = currentUser.student_id || '';
  document.getElementById('peEmail').value = currentUser.email || '';
  document.getElementById('pePassword').value = '';
  document.getElementById('profileEditError').textContent = '';
  document.getElementById('profileEditModal').classList.remove('hidden');
});
document.getElementById('btnProfileEditCancel').addEventListener('click', () => document.getElementById('profileEditModal').classList.add('hidden'));
document.getElementById('btnProfileEditSave').addEventListener('click', async () => {
  const err = document.getElementById('profileEditError');
  const body = {
    name: document.getElementById('peName').value.trim() || null,
    student_id: document.getElementById('peStudentId').value.trim() || null,
    email: document.getElementById('peEmail').value.trim(),
  };
  const pwd = document.getElementById('pePassword').value;
  if (pwd) body.password = pwd;
  err.textContent = '';
  try {
    currentUser = await apiFetch('/api/users/me', { method: 'PUT', body });
    renderUserChip();
    loadProfilePage();
    document.getElementById('profileEditModal').classList.add('hidden');
    showResult({ type: 'success', title: '保存成功', desc: '个人信息已更新。' });
  } catch (e) { err.textContent = e.message || '保存失败'; }
});

/* ============================================================
 * 10. 通用结果弹窗
 * ============================================================ */
const resultModal = document.getElementById('resultModal');
function showResult(opt) {
  const icon = document.getElementById('resultIcon');
  icon.className = 'result-icon ' + opt.type;
  icon.textContent = opt.type === 'success' ? '✅' : '⚠️';
  document.getElementById('resultTitle').textContent = opt.title;
  document.getElementById('resultDesc').textContent = opt.desc;
  const detail = document.getElementById('resultDetail');
  detail.innerHTML = '';
  if (opt.detail && opt.detail.length) {
    opt.detail.forEach(d => {
      const row = el('div', 'row-item');
      row.innerHTML = '<span>' + d.k + '</span><span>' + esc(d.v) + '</span>';
      detail.appendChild(row);
    });
    detail.style.display = 'block';
  } else { detail.style.display = 'none'; }
  const action = document.getElementById('resultAction');
  action.textContent = opt.actionText || '好的';
  action.onclick = () => { resultModal.classList.add('hidden'); if (opt.onAction) opt.onAction(); };
  const close = document.getElementById('resultClose');
  close.textContent = opt.closeText || '关闭';
  close.onclick = () => { resultModal.classList.add('hidden'); if (opt.onClose) opt.onClose(); };
  resultModal.classList.remove('hidden');
}

/* ============================================================
 * 11. 场景编辑弹窗
 * ============================================================ */
const scenarioModal = document.getElementById('scenarioModal');
let editingScenarioId = null;

function openScenarioModal(s) {
  editingScenarioId = s ? s.id : null;
  document.getElementById('scenarioModalTitle').textContent = s ? '编辑预约场景' : '新建预约场景';
  document.getElementById('scenarioFormError').textContent = '';
  document.getElementById('sfName').value = s ? s.name : '';
  document.getElementById('sfDescription').value = s && s.description ? s.description : '';
  document.getElementById('sfIsActive').value = s ? String(s.is_active) : 'true';
  document.getElementById('sfTimeStep').value = s ? s.time_step_minutes : 30;
  document.getElementById('sfMinDuration').value = s ? s.min_duration_minutes : 30;
  document.getElementById('sfMaxDuration').value = s ? s.max_duration_minutes : 240;
  document.getElementById('sfMaxAdvanceDays').value = s ? s.max_advance_days : 30;
  document.getElementById('sfMinAdvanceMinutes').value = s ? s.min_advance_minutes : 0;
  document.getElementById('sfAllowSameDay').value = s ? String(s.allow_same_day) : 'true';
  document.getElementById('sfMaxActivePerUser').value = s ? s.max_active_per_user : 5;
  document.getElementById('sfMaxMinutesPerDay').value = s && s.max_minutes_per_day != null ? s.max_minutes_per_day : '';
  document.getElementById('sfCancelBeforeMinutes').value = s && s.cancel_before_minutes != null ? s.cancel_before_minutes : '';
  scenarioModal.classList.remove('hidden');
}

document.getElementById('btnScenarioCancel').addEventListener('click', () => scenarioModal.classList.add('hidden'));
document.getElementById('btnScenarioSave').addEventListener('click', async () => {
  const err = document.getElementById('scenarioFormError');
  const name = document.getElementById('sfName').value.trim();
  if (!name) return err.textContent = '请输入场景名称';
  const minD = parseInt(document.getElementById('sfMinDuration').value, 10);
  const maxD = parseInt(document.getElementById('sfMaxDuration').value, 10);
  if (!(minD > 0) || !(maxD > 0)) return err.textContent = '请输入有效的时长范围';
  if (minD > maxD) return err.textContent = '最小时长不能大于最大时长';
  const body = {
    name,
    description: document.getElementById('sfDescription').value.trim() || null,
    is_active: document.getElementById('sfIsActive').value === 'true',
    time_step_minutes: parseInt(document.getElementById('sfTimeStep').value, 10) || 30,
    min_duration_minutes: minD, max_duration_minutes: maxD,
    max_advance_days: parseInt(document.getElementById('sfMaxAdvanceDays').value, 10) || 0,
    min_advance_minutes: parseInt(document.getElementById('sfMinAdvanceMinutes').value, 10) || 0,
    allow_same_day: document.getElementById('sfAllowSameDay').value === 'true',
    max_active_per_user: parseInt(document.getElementById('sfMaxActivePerUser').value, 10) || 5,
  };
  const mmpd = document.getElementById('sfMaxMinutesPerDay').value.trim();
  body.max_minutes_per_day = mmpd ? parseInt(mmpd, 10) : null;
  const cbm = document.getElementById('sfCancelBeforeMinutes').value.trim();
  body.cancel_before_minutes = cbm ? parseInt(cbm, 10) : null;
  err.textContent = '';
  try {
    if (editingScenarioId) await apiFetch('/api/scenarios/' + editingScenarioId, { method: 'PUT', body });
    else await apiFetch('/api/scenarios', { method: 'POST', body });
    scenarioModal.classList.add('hidden');
    resMgmtScenarios = []; bmScenarios = [];
    showResult({ type: 'success', title: '保存成功', desc: '场景「' + name + '」已保存。' });
    const activePage = document.querySelector('.page.active').dataset.page;
    if (activePage === 'scenarios') loadScenariosPage();
    if (activePage === 'rules') loadRulesPage();
  } catch (e) { err.textContent = e.message || '保存失败'; }
});

async function deleteScenario(s) {
  if (!confirm('确认删除场景「' + s.name + '」？\n该场景下所有资源与预约将一并删除，此操作不可恢复。')) return;
  try {
    await apiFetch('/api/scenarios/' + s.id, { method: 'DELETE' });
    resMgmtScenarios = []; bmScenarios = [];
    showResult({ type: 'success', title: '已删除', desc: '场景「' + s.name + '」已删除。' });
    loadScenariosPage();
  } catch (e) { showResult({ type: 'fail', title: '删除失败', desc: e.message }); }
}

/* ============================================================
 * 12. 资源编辑弹窗
 * ============================================================ */
const resourceModal = document.getElementById('resourceModal');

function openResourceModal(r) {
  editingResourceId = r ? r.id : null;
  document.getElementById('resourceModalTitle').textContent = r ? '编辑资源' : '新建资源';
  document.getElementById('resourceFormError').textContent = '';
  document.getElementById('rfName').value = r ? r.name : '';
  document.getElementById('rfCode').value = r ? r.code : '';
  document.getElementById('rfOpenStart').value = r ? fmtTime(r.open_start) : '08:00';
  document.getElementById('rfOpenEnd').value = r ? fmtTime(r.open_end) : '22:00';
  document.getElementById('rfIsActive').value = r ? String(r.is_active) : 'true';
  renderAttrEditor(r && r.attributes ? r.attributes : {});
  resourceModal.classList.remove('hidden');
}

function renderAttrEditor(attrs) {
  const wrap = document.getElementById('attrEditor');
  wrap.innerHTML = '';
  const keys = Object.keys(attrs || {});
  if (!keys.length) { wrap.appendChild(el('div', 'attr-empty', '暂无扩展属性，点击「添加」新增（如 location、row、col、window 等）')); return; }
  keys.forEach(k => wrap.appendChild(buildAttrRow(k, attrs[k])));
}
function buildAttrRow(key, val) {
  const row = el('div', 'attr-row');
  const ki = el('input', 'attr-key'); ki.type = 'text'; ki.value = key; ki.placeholder = '属性名';
  const vi = el('input', 'attr-val'); vi.type = 'text'; vi.value = val === true ? 'true' : (val === false ? 'false' : String(val)); vi.placeholder = '属性值';
  const rm = el('button', 'attr-remove', '✕'); rm.type = 'button'; rm.addEventListener('click', () => row.remove());
  row.appendChild(ki); row.appendChild(vi); row.appendChild(rm);
  return row;
}
document.getElementById('btnAddAttr').addEventListener('click', () => {
  const wrap = document.getElementById('attrEditor');
  const empty = wrap.querySelector('.attr-empty');
  if (empty) empty.remove();
  wrap.appendChild(buildAttrRow('', ''));
});
function collectAttrs() {
  const obj = {};
  document.querySelectorAll('#attrEditor .attr-row').forEach(row => {
    const k = row.querySelector('.attr-key').value.trim();
    const v = row.querySelector('.attr-val').value.trim();
    if (!k) return;
    if (v === 'true') obj[k] = true;
    else if (v === 'false') obj[k] = false;
    else if (v !== '' && !isNaN(Number(v)) && /^-?\d+(\.\d+)?$/.test(v)) obj[k] = Number(v);
    else obj[k] = v;
  });
  return obj;
}

document.getElementById('btnResourceCancel').addEventListener('click', () => resourceModal.classList.add('hidden'));
document.getElementById('btnResourceSave').addEventListener('click', async () => {
  const err = document.getElementById('resourceFormError');
  if (!resMgmtCurrent) return err.textContent = '未选择场景';
  const name = document.getElementById('rfName').value.trim();
  const code = document.getElementById('rfCode').value.trim();
  if (!name) return err.textContent = '请输入资源名称';
  if (!code) return err.textContent = '请输入资源编号';
  const os = document.getElementById('rfOpenStart').value, oe = document.getElementById('rfOpenEnd').value;
  if (!os || !oe) return err.textContent = '请输入开放时间';
  if (os >= oe) return err.textContent = '开放起始必须早于结束';
  const body = { name, code, open_start: os + ':00', open_end: oe + ':00', attributes: collectAttrs(), is_active: document.getElementById('rfIsActive').value === 'true' };
  err.textContent = '';
  try {
    if (editingResourceId) await apiFetch('/api/scenarios/' + resMgmtCurrent.id + '/resources/' + editingResourceId, { method: 'PUT', body });
    else await apiFetch('/api/scenarios/' + resMgmtCurrent.id + '/resources', { method: 'POST', body });
    resourceModal.classList.add('hidden');
    await loadResMgmtResources();
    showResult({ type: 'success', title: '保存成功', desc: '资源「' + code + '」已保存。' });
  } catch (e) { err.textContent = e.message || '保存失败'; }
});

async function deleteResource(r) {
  if (!confirm('确认删除资源「' + r.code + ' ' + r.name + '」？\n相关预约将一并删除，此操作不可恢复。')) return;
  try {
    await apiFetch('/api/scenarios/' + resMgmtCurrent.id + '/resources/' + r.id, { method: 'DELETE' });
    await loadResMgmtResources();
    showResult({ type: 'success', title: '已删除', desc: '资源「' + r.code + '」已删除。' });
  } catch (e) { showResult({ type: 'fail', title: '删除失败', desc: e.message }); }
}

/* ============================================================
 * 13. AI 智能助手抽屉（SSE 流式）
 * ============================================================ */
const AGENT_API = '/api/agent/chat';
const agentDrawer = document.getElementById('agentDrawer');
const agentMask = document.getElementById('agentMask');
const agentMsgs = document.getElementById('agentMsgs');
const agentInput = document.getElementById('agentInput');
const agentSend = document.getElementById('agentSend');
const agentStatus = document.getElementById('agentStatus');
const agentSuggest = document.getElementById('agentSuggest');
const SUGGESTIONS = ['查询今天的预约情况', '最近有哪些预约', '帮我取消一个预约', '当前有哪些场景'];

function getAgentSessionId() {
  let id = localStorage.getItem('agent_session_id');
  if (!id) { id = 'session_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8); localStorage.setItem('agent_session_id', id); }
  return id;
}

function openAgent() {
  agentDrawer.classList.add('show');
  agentMask.classList.add('show');
  if (!agentMsgs.childElementCount) {
    appendMsg('bot', '你好！我是 AI 智能预约助手 🤖\n你可以用自然语言让我帮你：查询预约、推荐资源、创建或取消预约。\n试试下方建议问题吧～');
    renderSuggestions();
  }
  setTimeout(() => agentInput.focus(), 100);
}
function closeAgent() { agentDrawer.classList.remove('show'); agentMask.classList.remove('show'); }
document.getElementById('agentLaunchBtn').addEventListener('click', openAgent);
document.getElementById('topbarAgentBtn').addEventListener('click', openAgent);
document.getElementById('agentClose').addEventListener('click', closeAgent);
agentMask.addEventListener('click', closeAgent);

function appendMsg(role, text) {
  const d = el('div', 'agent-msg ' + role); d.textContent = text;
  agentMsgs.appendChild(d); agentMsgs.scrollTop = agentMsgs.scrollHeight; return d;
}
function renderSuggestions() {
  agentSuggest.innerHTML = '';
  SUGGESTIONS.forEach(s => {
    const b = el('button', null, s);
    b.addEventListener('click', () => { agentInput.value = s; sendMessage(); });
    agentSuggest.appendChild(b);
  });
}

async function sendMessage() {
  const text = agentInput.value.trim();
  if (!text) return;
  agentInput.value = '';
  appendMsg('user', text);
  agentSend.disabled = true;
  agentStatus.textContent = '思考中…';
  const thinking = appendMsg('bot', '…');
  try {
    const reply = await streamChat(text, partial => { thinking.textContent = partial; agentMsgs.scrollTop = agentMsgs.scrollHeight; });
    thinking.textContent = reply;
  } catch (e) { thinking.textContent = '⚠️ 智能体服务异常：' + (e.message || '未知错误') + '\n（请确认后端已启动并配置 DeepSeek API Key）'; }
  agentStatus.textContent = '在线 · 自然语言查询 / 预约 / 取消';
  agentSend.disabled = false;
}

async function streamChat(text, onPartial) {
  const resp = await fetch(API_BASE + AGENT_API, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + getToken() },
    body: JSON.stringify({ message: text, session_id: getAgentSessionId() }),
  });
  if (!resp.ok) {
    let msg = 'HTTP ' + resp.status;
    try { const j = await resp.json(); if (j && j.message) msg = j.message; } catch (e) {}
    throw { message: msg };
  }
  if (!resp.body) throw { message: '浏览器不支持流式响应' };
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '', full = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n\n');
    buffer = parts.pop();
    for (const part of parts) {
      const line = part.trim();
      if (line.indexOf('data:') !== 0) continue;
      let payload;
      try { payload = JSON.parse(line.slice(5).trim()); } catch (e) { continue; }
      if (payload.error) throw { message: payload.error };
      if (payload.content) { full += payload.content; if (onPartial) onPartial(full); }
      if (payload.done) return full || '（无回复内容）';
    }
  }
  return full || '（无回复内容）';
}

agentSend.addEventListener('click', sendMessage);
agentInput.addEventListener('keydown', e => { if (e.key === 'Enter') sendMessage(); });

/* ============================================================
 * 14. 初始化
 * ============================================================ */
async function init() {
  const token = getToken();
  if (token) {
    try {
      currentUser = await apiFetch('/api/users/me');
      renderUserChip();
      switchPage('dashboard');
      return;
    } catch (e) { clearToken(); }
  }
  loginModal.classList.remove('hidden');
}
init();
