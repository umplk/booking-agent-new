/* ============================================================
 * 智约 · 可配置智能预约平台 — 前端逻辑
 * 原生 JS · 模块化组织 · 全面对接后端 API
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

/* ============================================================
 * 2. 路由（页面切换 + 顶栏标题）
 * ============================================================ */
const PAGE_META = {
  dashboard:   ['首页', '查看你的预约数据与可预约场景'],
  booking:     ['我要预约', '选择场景与资源，完成自助预约'],
  reservations:['我的预约', '查看与管理你的预约记录'],
  scenarios:   ['预约场景', '浏览可预约场景'],
  profile:     ['个人中心', '查看与编辑个人信息'],
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
  if (name === 'booking') ensureBookingLoaded();
  if (name === 'reservations') loadReservationsPage();
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
 * 4. 数据概览页
 * ============================================================ */
async function loadDashboard() {
  let scenarioCount = 0, resourceCount = 0;
  let scenarios = [];
  try {
    const data = await apiFetch('/api/scenarios?page=1&page_size=200&include_inactive=false');
    scenarios = data.items || [];
    scenarioCount = data.total || scenarios.length;
  } catch (e) {}
  document.getElementById('dashScenarioCount').textContent = scenarioCount;

  /* 资源数：并发查询各场景资源 */
  const resCounts = await Promise.all(scenarios.map(s =>
    apiFetch('/api/scenarios/' + s.id + '/resources?page=1&page_size=1').then(d => d.total || 0).catch(() => 0)
  ));
  resourceCount = resCounts.reduce((a, b) => a + b, 0);
  document.getElementById('dashResourceCount').textContent = resourceCount;

  /* 我的预约 */
  let myRes = [];
  try { myRes = await apiFetch('/api/reservations?status=all'); } catch (e) {}
  const active = myRes.filter(r => r.status === 'confirmed' || r.status === 'pending');
  document.getElementById('dashActiveCount').textContent = active.length;

  /* 今日可约时段（取第一个场景） */
  document.getElementById('dashTodayCount').textContent = '—';
  if (scenarios.length) {
    try {
      const av = await apiFetch('/api/scenarios/' + scenarios[0].id + '/availability?date=' + todayStr());
      document.getElementById('dashTodayCount').textContent = av.free_slots_count || 0;
    } catch (e) {}
  }

  /* 最近预约 */
  const recentWrap = document.getElementById('dashRecent');
  const recentEmpty = document.getElementById('dashRecentEmpty');
  recentWrap.innerHTML = '';
  const recent = myRes.slice().sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, 5);
  if (!recent.length) { recentEmpty.classList.remove('hidden'); }
  else {
    recentEmpty.classList.add('hidden');
    recent.forEach(r => {
      const isCancel = r.status === 'cancelled';
      const item = el('div', 'recent-item');
      item.appendChild(el('div', 'ri-tag ' + (isCancel ? 'cancel' : 'valid'), isCancel ? '❌' : '✅'));
      const main = el('div', 'ri-main');
      main.appendChild(el('div', 'ri-title', esc((r.scenario_name || '') + ' · ' + (r.resource_code || r.resource_name || ''))));
      main.appendChild(el('div', 'ri-meta', isoDate(r.start_time) + ' ' + isoTime(r.start_time) + '-' + isoTime(r.end_time) + ' · ' + statusText(r.status)));
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
    card.addEventListener('click', () => { switchPage('booking'); });
    grid.appendChild(card);
  });
}

function statusText(s) {
  return { confirmed: '已确认', pending: '待确认', cancelled: '已取消', completed: '已完成' }[s] || s;
}

/* ============================================================
 * 5. 我要预约页
 * ============================================================ */
let bookingScenarios = [];
let currentScenario = null;
let floors = [];
let currentFloorIdx = 0;
let seats = [];
let currentDate = '';
let currentTimeStart = '08:00';
let currentTimeEnd = '10:00';
let selectedId = null;
let recommendIds = new Set();
let recommendData = {};
let currentPrefLabels = [];
let bookingInited = false;

const ICON_MAP = [
  { kw: '文学', icon: '📖' }, { kw: '理工', icon: '🔬' }, { kw: '外文', icon: '🌍' },
  { kw: '人文', icon: '🏛️' }, { kw: '电子', icon: '💻' },
];
function roomIcon(name) {
  for (const it of ICON_MAP) if (name.indexOf(it.kw) >= 0) return it.icon;
  return '📚';
}
function currentFloor() { return floors[currentFloorIdx] || null; }

async function ensureBookingLoaded() {
  if (!bookingScenarios.length) await loadBookingScenarios();
}

async function loadBookingScenarios() {
  try {
    const data = await apiFetch('/api/scenarios?page=1&page_size=100&include_inactive=false');
    bookingScenarios = data.items || [];
  } catch (e) {
    bookingScenarios = [];
    showResult({ type: 'fail', title: '加载场景失败', desc: e.message || '请检查后端服务' });
    return;
  }
  const sel = document.getElementById('bookingScenario');
  sel.innerHTML = '';
  bookingScenarios.forEach(s => {
    const o = el('option'); o.value = s.id; o.textContent = s.name; sel.appendChild(o);
  });
  if (!bookingScenarios.length) {
    showResult({ type: 'fail', title: '暂无预约场景', desc: '请先在「预约场景」页创建场景。', actionText: '去创建', onAction: () => switchPage('scenarios') });
    return;
  }
  currentScenario = bookingScenarios[0];
  await onScenarioReady();
}

document.getElementById('bookingScenario').addEventListener('change', async function () {
  const id = parseInt(this.value, 10);
  currentScenario = bookingScenarios.find(s => s.id === id);
  if (!currentScenario) return;
  resetSelection();
  await onScenarioReady();
  if (currentDate) await loadAvailability();
  renderSeats();
  renderRecommendPanel();
});

async function onScenarioReady() {
  await loadResources();
  renderFloorTabs();
  renderSeats();
}

function resetSelection() {
  selectedId = null;
  recommendIds.clear();
  recommendData = {};
  document.getElementById('btnConfirm').disabled = true;
  document.getElementById('selTip').textContent = '';
}

async function loadResources() {
  if (!currentScenario) return;
  try {
    const data = await apiFetch('/api/scenarios/' + currentScenario.id + '/resources?page=1&page_size=500');
    const items = data.items || [];
    const groupMap = {}, order = [];
    items.forEach(r => {
      const loc = (r.attributes || {}).location || '全部资源';
      if (!groupMap[loc]) { groupMap[loc] = []; order.push(loc); }
      groupMap[loc].push(r);
    });
    floors = order.map(loc => {
      const res = groupMap[loc];
      return { location: loc, name: loc, resources: res, openStart: fmtTime(res[0].open_start), openEnd: fmtTime(res[0].open_end) };
    });
  } catch (e) {
    floors = [];
    showResult({ type: 'fail', title: '加载资源失败', desc: e.message || '请检查后端服务' });
    return;
  }
  currentFloorIdx = 0;
  buildSeatsFromFloor();
  syncTimeInputs();
}

function syncTimeInputs() {
  if (!currentScenario) return;
  const step = currentScenario.time_step_minutes || 30;
  const s = document.getElementById('bookingStart'), e = document.getElementById('bookingEnd');
  s.step = step * 60; e.step = step * 60;
  const f = currentFloor();
  if (f) { s.min = f.openStart; s.max = f.openEnd; e.min = f.openStart; e.max = f.openEnd; }
}

function buildSeatsFromFloor() {
  const f = currentFloor();
  if (!f) { seats = []; return; }
  seats = f.resources.map(r => {
    const a = r.attributes || {};
    const row = a.row || (r.code || '').split('-')[1] || '?';
    const col = a.col || 0;
    return {
      resourceId: r.id, code: r.code, id: row + (col || ''), row, col,
      is_available: r.is_active !== false,
      window: !!a.window, power: !!a.power, quiet: !!a.quiet, group: !!a.group, corner: !!a.corner,
      openStart: fmtTime(r.open_start), openEnd: fmtTime(r.open_end),
      booked: false, freeSlots: [],
    };
  });
}

function renderFloorTabs() {
  const wrap = document.getElementById('floorTabs');
  wrap.innerHTML = '';
  floors.forEach((f, idx) => {
    const tab = el('div', 'floor-tab' + (idx === currentFloorIdx ? ' active' : ''));
    tab.innerHTML = '<span class="ft-icon">' + roomIcon(f.name) + '</span><span class="ft-name">' + esc(f.location) + '</span>';
    tab.addEventListener('click', () => switchFloor(idx));
    wrap.appendChild(tab);
  });
}

async function switchFloor(idx) {
  if (idx === currentFloorIdx) return;
  currentFloorIdx = idx;
  resetSelection();
  renderFloorTabs();
  buildSeatsFromFloor();
  syncTimeInputs();
  if (currentDate) await loadAvailability();
  renderSeats();
  renderRecommendPanel();
}

/* 日期与时段 */
const dateInput = document.getElementById('bookingDate');
dateInput.min = todayStr();
dateInput.value = '';

function readTimeRange() {
  currentTimeStart = document.getElementById('bookingStart').value || '08:00';
  currentTimeEnd = document.getElementById('bookingEnd').value || '10:00';
}

async function onDateOrTimeChange() {
  currentDate = dateInput.value;
  readTimeRange();
  const hint = document.getElementById('bookingHint');
  const lock = document.getElementById('roomLock');
  if (currentDate && currentTimeStart && currentTimeEnd && currentTimeStart < currentTimeEnd) {
    hint.textContent = '已选 ' + currentDate + ' ' + currentTimeStart + '-' + currentTimeEnd + '，现在可以选择资源';
    hint.classList.add('ready');
    lock.classList.add('hidden');
    await loadAvailability();
  } else {
    hint.textContent = '请先选择预约日期与时段，再选择资源';
    hint.classList.remove('ready');
    lock.classList.remove('hidden');
    seats.forEach(s => s.booked = false);
  }
  resetSelection();
  renderSeats();
  applyRecommend();
}
dateInput.addEventListener('change', onDateOrTimeChange);
document.getElementById('bookingStart').addEventListener('change', onDateOrTimeChange);
document.getElementById('bookingEnd').addEventListener('change', onDateOrTimeChange);

async function loadAvailability() {
  if (!currentScenario || !currentDate) return;
  try {
    const data = await apiFetch('/api/scenarios/' + currentScenario.id + '/availability?date=' + currentDate);
    const freeMap = {};
    (data.resources || []).forEach(r => freeMap[r.resource_id] = r.free_slots || []);
    seats.forEach(s => {
      s.freeSlots = freeMap[s.resourceId] || [];
      s.booked = !isFreeInRange(s.freeSlots, currentTimeStart, currentTimeEnd);
    });
  } catch (e) {}
}

function isFreeInRange(freeSlots, start, end) {
  if (!freeSlots || !freeSlots.length) return false;
  if (start >= end) return false;
  const sorted = freeSlots.slice().sort((a, b) => a.start < b.start ? -1 : (a.start > b.start ? 1 : 0));
  let cursor = start;
  for (const slot of sorted) {
    if (slot.end <= cursor) continue;
    if (slot.start > cursor) return false;
    cursor = slot.end;
    if (cursor >= end) return true;
  }
  return cursor >= end;
}

function seatTaken(s) { return !s.is_available || s.booked; }

/* 渲染资源 */
function renderSeats() {
  const map = document.getElementById('roomMap');
  map.innerHTML = '';
  if (!seats.length) { map.appendChild(el('div', 'empty-state', '<span class="empty-icon">📦</span><p>该分组暂无资源</p>')); return; }
  if (floorHasGrid()) renderSeatMap(); else renderResourceCards();
  updateStat();
  applyRecommend();
}

function floorHasGrid() {
  const f = currentFloor();
  return f && f.resources.some(r => { const a = r.attributes || {}; return a.row != null && a.col != null; });
}

function renderSeatMap() {
  const map = document.getElementById('roomMap');
  const rowMap = {};
  seats.forEach(s => { rowMap[s.row] = rowMap[s.row] || []; rowMap[s.row].push(s); });
  Object.keys(rowMap).sort().forEach(r => {
    const rowEl = el('div', 'row');
    rowEl.appendChild(el('div', 'row-label', r + '排'));
    const sw = el('div', 'seats');
    const rs = rowMap[r].slice().sort((a, b) => a.col - b.col);
    rs.forEach((s, idx) => {
      const taken = seatTaken(s);
      const e = el('div', 'seat ' + (taken ? 'occupied' : 'free'));
      e.dataset.id = s.id;
      if (s.power) e.classList.add('has-power');
      let icons = '';
      if (s.window) icons += '🪟';
      if (s.power) icons += '🔌';
      if (icons) e.appendChild(el('div', 'icons', icons));
      e.appendChild(el('div', 'num', s.id));
      e.appendChild(el('div', 'tag', s.group ? '讨论' : (s.quiet ? '安静' : '')));
      e.addEventListener('click', () => onSeatClick(s.id, e));
      sw.appendChild(e);
      if (idx === Math.floor(rs.length / 2) - 1) sw.appendChild(el('div', 'aisle'));
    });
    rowEl.appendChild(sw);
    map.appendChild(rowEl);
  });
}

function renderResourceCards() {
  const map = document.getElementById('roomMap');
  const grid = el('div', 'resource-card-grid');
  seats.slice().sort((a, b) => (a.code || a.id) < (b.code || b.id) ? -1 : 1).forEach(s => {
    const taken = seatTaken(s);
    const card = el('div', 'resource-card ' + (taken ? 'occupied' : 'free'));
    card.dataset.id = s.id;
    card.innerHTML =
      '<div class="rc-head"><span class="rc-code">' + esc(s.code || s.id) + '</span>' +
      '<span class="rc-name">' + esc(s.id) + '</span>' +
      '<span class="badge ' + (taken ? 'badge-danger' : 'badge-success') + '">' + (taken ? '占用' : '空闲') + '</span></div>' +
      '<div class="rc-meta">开放 ' + s.openStart + '-' + s.openEnd + '</div>';
    const chips = el('div', 'rc-chips');
    [['window', '🪟靠窗'], ['power', '🔌电源'], ['quiet', '安静'], ['group', '讨论'], ['corner', '角落']].forEach(([k, label]) => {
      if (s[k]) chips.appendChild(el('span', 'attr-chip bool-true', label));
    });
    card.appendChild(chips);
    const slots = el('div', 'rc-slots');
    if (s.freeSlots && s.freeSlots.length) {
      slots.appendChild(el('span', 'rc-slots-label', '可约:'));
      mergeSlots(s.freeSlots).slice(0, 12).forEach(m => slots.appendChild(el('span', 'avail-slot', m.start + '-' + m.end)));
    } else if (currentDate) {
      slots.appendChild(el('span', 'avail-slot none', '当天无空闲'));
    } else {
      slots.appendChild(el('span', 'rc-slots-label', '选择日期后查看可约时段'));
    }
    card.appendChild(slots);
    card.addEventListener('click', () => onSeatClick(s.id, card));
    grid.appendChild(card);
  });
  map.appendChild(grid);
}

function onSeatClick(id, e) {
  if (!currentDate) return;
  const s = seats.find(x => x.id === id);
  if (!s || seatTaken(s)) return;
  document.querySelectorAll('.seat.selected, .resource-card.selected').forEach(x => x.classList.remove('selected'));
  if (selectedId === id) { selectedId = null; } else { selectedId = id; e.classList.add('selected'); }
  updateTip();
  document.getElementById('btnConfirm').disabled = !selectedId;
}

/* 智能推荐 */
const PREF_LABELS = { quiet: '安静', window: '靠窗', power: '有电源', corner: '角落', group: '讨论' };

function recommend(prefs, major) {
  recommendIds.clear(); recommendData = {};
  const majorPref = { cs: ['power'], math: ['quiet'], literature: ['window'], art: ['window', 'corner'], science: ['power'] };
  const all = new Set(prefs);
  if (major && majorPref[major]) majorPref[major].forEach(p => all.add(p));
  currentPrefLabels = [];
  all.forEach(p => { if (PREF_LABELS[p]) currentPrefLabels.push(PREF_LABELS[p]); });
  const total = all.size;
  if (!total) { applyRecommend(); renderRecommendPanel(); return; }
  const candidates = seats.filter(s => !seatTaken(s)).map(s => {
    let score = 0; const matched = [];
    all.forEach(p => { if (s[p]) { score++; if (PREF_LABELS[p]) matched.push(PREF_LABELS[p]); } });
    return { s, score, matched };
  }).sort((a, b) => b.score - a.score);
  const maxScore = candidates.length ? candidates[0].score : 0;
  if (maxScore > 0) {
    candidates.filter(x => x.score === maxScore).slice(0, 5).forEach(x => {
      recommendIds.add(x.s.id);
      recommendData[x.s.id] = { score: x.score, total, percent: Math.round(x.score / total * 100), matched: x.matched };
    });
  }
  applyRecommend(); renderRecommendPanel();
}

function applyRecommend() {
  document.querySelectorAll('.seat.recommend, .resource-card.recommend').forEach(e => { e.classList.remove('recommend'); e.removeAttribute('data-match'); });
  recommendIds.forEach(id => {
    const e = document.querySelector('.seat[data-id="' + id + '"], .resource-card[data-id="' + id + '"]');
    if (e && !e.classList.contains('selected') && !e.classList.contains('occupied')) {
      e.classList.add('recommend');
      const d = recommendData[id];
      if (d) e.setAttribute('data-match', d.percent + '%');
    }
  });
  updateStat();
}

function renderRecommendPanel() {
  const panel = document.getElementById('recommendPanel');
  panel.innerHTML = '';
  if (!recommendIds.size) { panel.classList.remove('show'); return; }
  panel.classList.add('show');
  panel.appendChild(el('div', 'rp-head', '🎯 为你推荐以下资源（按匹配度排序，点击可选中）'));
  if (currentPrefLabels.length) panel.appendChild(el('div', 'rp-cond', '预期条件：<b>' + currentPrefLabels.join(' · ') + '</b>'));
  const list = el('div', 'recommend-list');
  Array.from(recommendIds).forEach(id => {
    const d = recommendData[id];
    const item = el('div', 'recommend-item');
    item.appendChild(el('span', 'ri-seat', id));
    const bw = el('div', 'ri-bar-wrap'); bw.appendChild(el('div', 'ri-bar')); bw.firstChild.style.width = d.percent + '%';
    item.appendChild(bw);
    item.appendChild(el('span', 'ri-percent', d.percent + '%'));
    item.appendChild(el('span', 'ri-tags', d.matched.length ? d.matched.join(' · ') : '无匹配'));
    item.addEventListener('click', () => {
      const e = document.querySelector('.seat[data-id="' + id + '"], .resource-card[data-id="' + id + '"]');
      if (e) { onSeatClick(id, e); e.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
    });
    list.appendChild(item);
  });
  panel.appendChild(list);
}

function updateStat() {
  const free = seats.filter(s => !seatTaken(s)).length;
  document.getElementById('statFree').textContent = free;
  document.getElementById('statOcc').textContent = seats.length - free;
  document.getElementById('statRec').textContent = recommendIds.size;
}

function updateTip() {
  const tip = document.getElementById('selTip');
  if (selectedId) {
    const f = currentFloor();
    tip.textContent = '已选中：' + (f ? f.location + ' · ' : '') + selectedId + '（' + currentDate + ' ' + currentTimeStart + '-' + currentTimeEnd + '）';
  } else { tip.textContent = ''; }
}

/* 偏好弹窗 */
document.querySelectorAll('#prefChips .chip').forEach(c => c.addEventListener('click', () => c.classList.toggle('on')));
document.getElementById('btnReopenPref').addEventListener('click', () => document.getElementById('prefModal').classList.remove('hidden'));
document.getElementById('btnSkipPref').addEventListener('click', () => document.getElementById('prefModal').classList.add('hidden'));
document.getElementById('btnRecommend').addEventListener('click', () => {
  const prefs = Array.from(document.querySelectorAll('#prefChips .chip.on')).map(c => c.dataset.pref);
  const major = document.getElementById('majorSelect').value;
  recommend(prefs, major);
  document.getElementById('prefModal').classList.add('hidden');
  if (recommendIds.size) {
    const first = Array.from(recommendIds)[0];
    const e = document.querySelector('.seat[data-id="' + first + '"], .resource-card[data-id="' + first + '"]');
    if (e) e.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
});

/* 确认预约 */
document.getElementById('btnConfirm').addEventListener('click', async () => {
  if (!selectedId) return;
  if (!currentDate) return showResult({ type: 'fail', title: '请先选择日期', desc: '预约前请先选择预约日期与时段。' });
  if (!currentTimeStart || !currentTimeEnd || currentTimeStart >= currentTimeEnd)
    return showResult({ type: 'fail', title: '时段无效', desc: '请选择有效的开始与结束时间。' });
  const s = seats.find(x => x.id === selectedId);
  if (!s) return;
  const f = currentFloor();
  if (seatTaken(s)) {
    showResult({ type: 'fail', title: '预约失败', desc: '该资源在所选时段已被预约，请重新选择。' });
    resetSelection(); renderSeats(); return;
  }
  const startIso = currentDate + 'T' + currentTimeStart + ':00';
  const endIso = currentDate + 'T' + currentTimeEnd + ':00';
  try {
    await apiFetch('/api/reservations', { method: 'POST', body: { scenario_id: currentScenario.id, resource_id: s.resourceId, start_time: startIso, end_time: endIso } });
    resetSelection();
    await loadAvailability();
    renderSeats();
    showResult({
      type: 'success', title: '预约成功！', desc: '请在预约时段内到达，逾期可能被系统取消。',
      detail: [
        { k: '预约人', v: currentUser ? (currentUser.name || currentUser.username) : '—' },
        { k: '预约场景', v: currentScenario.name },
        { k: '所在分组', v: f ? f.location : '' },
        { k: '资源编号', v: s.code || selectedId },
        { k: '预约日期', v: currentDate },
        { k: '预约时段', v: currentTimeStart + ' - ' + currentTimeEnd },
      ],
      closeText: '查看我的预约', onClose: () => switchPage('reservations'),
      actionText: '继续预约',
    });
  } catch (e) {
    showResult({ type: 'fail', title: '预约失败', desc: e.message || '请稍后重试' });
  }
});

/* ============================================================
 * 6. 预约场景页
 * ============================================================ */
let scenarioPageList = [];

async function loadScenariosPage() {
  try {
    const data = await apiFetch('/api/scenarios?page=1&page_size=200&mine=false&include_inactive=false');
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
        '<button class="btn-act primary" data-act="book">去预约</button>' +
      '</div>';
    card.querySelector('[data-act="book"]').addEventListener('click', () => switchPage('booking'));
    grid.appendChild(card);
  });
}


/* ============================================================
 * 9. 我的预约页
 * ============================================================ */
let myReservations = [];

async function loadReservationsPage() {
  try { myReservations = await apiFetch('/api/reservations?status=all'); } catch (e) { myReservations = []; }
  renderReservations();
}

document.querySelectorAll('.res-tab').forEach(t => t.addEventListener('click', () => {
  document.querySelectorAll('.res-tab').forEach(x => x.classList.remove('active'));
  t.classList.add('active');
  const tab = t.dataset.rtab;
  document.getElementById('resActivePanel').classList.toggle('hidden', tab !== 'active');
  document.getElementById('resHistoryPanel').classList.toggle('hidden', tab !== 'history');
}));

function renderReservations() {
  /* 有效 */
  const activeList = myReservations.filter(r => r.status === 'confirmed' || r.status === 'pending');
  const aWrap = document.getElementById('resActiveList');
  const aEmpty = document.getElementById('resActiveEmpty');
  aWrap.innerHTML = '';
  if (!activeList.length) { aEmpty.classList.remove('hidden'); } else {
    aEmpty.classList.add('hidden');
    activeList.forEach(r => aWrap.appendChild(buildResCard(r, true)));
  }
  /* 历史 */
  const history = myReservations.slice().sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  const hWrap = document.getElementById('resHistoryList');
  const hEmpty = document.getElementById('resHistoryEmpty');
  hWrap.innerHTML = '';
  if (!history.length) { hEmpty.classList.remove('hidden'); } else {
    hEmpty.classList.add('hidden');
    history.forEach(r => hWrap.appendChild(buildResCard(r, false)));
  }
}

function buildResCard(r, withCancel) {
  const isCancel = r.status === 'cancelled';
  const card = el('div', 'res-card');
  card.appendChild(el('div', 'res-icon ' + (isCancel ? 'cancel' : 'valid'), isCancel ? '❌' : '✅'));
  const main = el('div', 'res-main');
  main.appendChild(el('div', 'res-title', esc((r.scenario_name || '') + ' · ' + (r.resource_code || r.resource_name || ''))));
  main.appendChild(el('div', 'res-meta', '日期：' + isoDate(r.start_time) + ' · 时段：' + isoTime(r.start_time) + '-' + isoTime(r.end_time) + ' · 状态：' + statusText(r.status) + ' · 创建：' + fmtDateTime(r.created_at)));
  card.appendChild(main);
  if (withCancel && !isCancel) {
    const act = el('div', 'res-actions');
    const btn = el('button', 'btn btn-ghost btn-sm', '取消预约');
    btn.addEventListener('click', () => cancelReservation(r));
    act.appendChild(btn);
    card.appendChild(act);
  }
  return card;
}

async function cancelReservation(r) {
  try {
    await apiFetch('/api/reservations/' + r.id + '/cancel', { method: 'PUT' });
    await loadReservationsPage();
    showResult({ type: 'success', title: '已取消预约', desc: '资源已释放。' });
  } catch (e) { showResult({ type: 'fail', title: '取消失败', desc: e.message }); }
}

/* ============================================================
 * 10. 个人中心页
 * ============================================================ */
function loadProfilePage() {
  if (!currentUser) return;
  const name = currentUser.name || currentUser.username;
  document.getElementById('profileAvatar').textContent = name.charAt(0);
  document.getElementById('profileName').textContent = name;
  document.getElementById('profileEmail').textContent = currentUser.email || '—';
  document.getElementById('profileRoleBadge').textContent = currentUser.role === 'admin' ? '管理员' : '普通用户';
  document.getElementById('profileSidBadge').textContent = '学号：' + (currentUser.student_id || '—');
  const total = myReservations.length;
  const valid = myReservations.filter(r => r.status === 'confirmed' || r.status === 'pending').length;
  const cancel = myReservations.filter(r => r.status === 'cancelled').length;
  document.getElementById('statTotal').textContent = total;
  document.getElementById('statValid').textContent = valid;
  document.getElementById('statCancel').textContent = cancel;
  if (!myReservations.length) loadReservationsPage().then(loadProfilePage);
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
 * 11. 通用结果弹窗
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
 * 14. AI 智能助手抽屉（SSE 流式）
 * ============================================================ */
const AGENT_API = '/api/agent/chat';
const agentDrawer = document.getElementById('agentDrawer');
const agentMask = document.getElementById('agentMask');
const agentMsgs = document.getElementById('agentMsgs');
const agentInput = document.getElementById('agentInput');
const agentSend = document.getElementById('agentSend');
const agentStatus = document.getElementById('agentStatus');
const agentSuggest = document.getElementById('agentSuggest');
const SUGGESTIONS = ['帮我推荐一个安静靠窗的座位', '今天有哪些空闲资源', '怎么预约', '我的预约记录'];

function getAgentSessionId() {
  let id = localStorage.getItem('agent_session_id');
  if (!id) { id = 'session_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8); localStorage.setItem('agent_session_id', id); }
  return id;
}

function openAgent() {
  agentDrawer.classList.add('show');
  agentMask.classList.add('show');
  if (!agentMsgs.childElementCount) {
    appendMsg('bot', '你好！我是 AI 智能预约助手 🤖\n你可以用自然语言让我帮你：查询可预约资源、推荐座位、创建或取消预约。\n试试下方建议问题吧～');
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
 * 15. 初始化
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
