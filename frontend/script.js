/* ============================================================
 * 校园图书馆自习室座位预约 - 交互逻辑
 * 原生 JS，无框架；全面对接后端 API
 * 后端：FastAPI  默认地址 http://127.0.0.1:8000
 * ============================================================ */

/* ---------- 0. API 配置与请求封装 ---------- */
const API_BASE = 'http://127.0.0.1:8000';

function getToken() {
  return localStorage.getItem('token') || '';
}
function setToken(t) {
  localStorage.setItem('token', t);
}
function clearToken() {
  localStorage.removeItem('token');
}

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
  try {
    resp = await fetch(API_BASE + path, options);
  } catch (e) {
    throw { message: '无法连接服务器，请检查后端是否启动' };
  }
  let json;
  try {
    json = await resp.json();
  } catch (e) {
    throw { message: '服务器返回格式错误（HTTP ' + resp.status + '）' };
  }
  if (json.code && json.code !== 200) {
    throw { message: json.message || '请求失败', code: json.code };
  }
  if (!resp.ok) {
    throw { message: json.message || ('HTTP ' + resp.status), code: resp.status };
  }
  return json.data;
}

/* 时间格式化辅助："08:00:00" -> "08:00" */
function fmtTime(t) {
  if (!t) return '';
  return String(t).slice(0, 5);
}
/* "2026-10-11T10:30:00" -> "2026-10-11 10:30" */
function fmtDateTime(dt) {
  if (!dt) return '';
  return String(dt).replace('T', ' ').slice(0, 16);
}
/* ISO datetime "2026-10-11T10:30:00" -> "2026-10-11" */
function isoDate(dt) {
  if (!dt) return '';
  return String(dt).slice(0, 10);
}
/* ISO datetime "2026-10-11T10:30:00" -> "10:30" */
function isoTime(dt) {
  if (!dt) return '';
  return String(dt).slice(11, 16);
}

/* ---------- 1. 单页视图切换 ---------- */
const navLinks = document.querySelectorAll('.nav-menu a');
const viewEls = document.querySelectorAll('.view');

function switchView(name, linkEl) {
  viewEls.forEach(function (v) { v.classList.remove('active'); });
  const target = document.querySelector('.view[data-name="' + name + '"]');
  if (target) target.classList.add('active');
  navLinks.forEach(function (a) { a.classList.remove('active'); });
  if (linkEl) {
    linkEl.classList.add('active');
  } else {
    const match = document.querySelector('.nav-menu a[data-view="' + name + '"]');
    if (match) match.classList.add('active');
  }
  if (name === 'mine') loadReservations().then(renderReservations);
  if (name === 'profile') loadReservations().then(renderProfile);
  if (name === 'admin') loadAdminView();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

navLinks.forEach(function (a) {
  a.addEventListener('click', function (e) {
    e.preventDefault();
    switchView(a.dataset.view, a);
  });
});

document.getElementById('navUser').addEventListener('click', function () {
  const link = document.querySelector('.nav-menu a[data-view="profile"]');
  switchView('profile', link);
});

/* ---------- 2. 登录 / 注册 ---------- */
const loginModal = document.getElementById('loginModal');
const registerModal = document.getElementById('registerModal');
const prefModal = document.getElementById('prefModal');
let currentUser = null;

function showLoginError(msg) {
  document.getElementById('loginError').textContent = msg;
}
function showRegError(msg) {
  document.getElementById('regError').textContent = msg;
}

document.getElementById('btnGoRegister').addEventListener('click', function () {
  showLoginError('');
  loginModal.style.display = 'none';
  registerModal.style.display = 'flex';
});

document.getElementById('btnBackLogin').addEventListener('click', function () {
  showRegError('');
  registerModal.style.display = 'none';
  loginModal.style.display = 'flex';
});

async function doLogin() {
  const username = document.getElementById('loginUsername').value.trim();
  const password = document.getElementById('loginPassword').value;
  if (!username) { showLoginError('请输入用户名'); return; }
  if (!password) { showLoginError('请输入密码'); return; }
  showLoginError('');

  try {
    const data = await apiFetch('/api/auth/login', {
      method: 'POST',
      body: { username: username, password: password },
    });
    setToken(data.access_token);
    await afterLogin();
  } catch (e) {
    showLoginError(e.message || '登录失败');
  }
}

document.getElementById('btnLogin').addEventListener('click', doLogin);

['loginUsername', 'loginPassword'].forEach(function (id) {
  document.getElementById(id).addEventListener('keydown', function (e) {
    if (e.key === 'Enter') doLogin();
  });
});

async function doRegister() {
  const username = document.getElementById('regUsername').value.trim();
  const name = document.getElementById('regName').value.trim();
  const studentId = document.getElementById('regStudentId').value.trim();
  const email = document.getElementById('regEmail').value.trim();
  const password = document.getElementById('regPassword').value;

  if (!username || username.length < 3) { showRegError('用户名至少 3 位'); return; }
  if (!email) { showRegError('请输入邮箱'); return; }
  if (!password || password.length < 6) { showRegError('密码至少 6 位'); return; }
  showRegError('');

  try {
    await apiFetch('/api/auth/register', {
      method: 'POST',
      body: {
        username: username,
        email: email,
        password: password,
        name: name || null,
        student_id: studentId || null,
      },
    });
    showRegError('');
    registerModal.style.display = 'none';
    document.getElementById('loginUsername').value = username;
    document.getElementById('loginPassword').value = password;
    await doLogin();
  } catch (e) {
    showRegError(e.message || '注册失败');
  }
}

document.getElementById('btnRegister').addEventListener('click', doRegister);

/* 登录成功后的统一流程：拉取用户信息 -> 渲染导航 -> 加载自习室 -> 弹偏好 */
async function afterLogin() {
  try {
    currentUser = await apiFetch('/api/users/me');
  } catch (e) {
    clearToken();
    showLoginError(e.message || '获取用户信息失败');
    loginModal.style.display = 'flex';
    return;
  }

  const displayName = currentUser.name || currentUser.username;
  document.getElementById('navUserName').textContent = displayName;
  document.getElementById('navAvatar').textContent = displayName.charAt(0);
  updateAdminMenuVisibility();

  loginModal.style.display = 'none';
  registerModal.style.display = 'none';

  await loadScenarios();
  prefModal.style.display = 'flex';
}

/* ---------- 3. 场景与资源数据（对接 /api/scenarios + /resources） ---------- */
let scenarios = [];       // 后端 Scenario 列表
let currentScenario = null;
let floors = [];          // 按 resource.attributes.location 分组的楼层
let currentFloorIdx = 0;
let seats = [];           // 当前楼层的座位（前端结构）
let currentDate = '';
let currentTimeStart = '08:00';
let currentTimeEnd = '10:00';

const ICON_MAP = [
  { kw: '文学', icon: '📖' },
  { kw: '理工', icon: '🔬' },
  { kw: '外文', icon: '🌍' },
  { kw: '人文', icon: '🏛️' },
  { kw: '电子', icon: '💻' },
];

function roomIcon(name) {
  for (let i = 0; i < ICON_MAP.length; i++) {
    if (name.indexOf(ICON_MAP[i].kw) >= 0) return ICON_MAP[i].icon;
  }
  return '📚';
}

function currentFloor() {
  return floors[currentFloorIdx] || null;
}

/* 加载场景列表，渲染场景下拉（多场景时显示） */
async function loadScenarios() {
  try {
    const data = await apiFetch('/api/scenarios?page=1&page_size=100&include_inactive=false');
    scenarios = data.items || [];
  } catch (e) {
    scenarios = [];
    showResult({
      type: 'fail',
      title: '加载场景失败',
      desc: e.message || '请检查后端服务',
    });
    return;
  }
  if (scenarios.length === 0) {
    showResult({
      type: 'fail',
      title: '暂无预约场景',
      desc: '后端尚未配置任何预约场景，请联系管理员添加。',
    });
    return;
  }

  const bar = document.getElementById('scenarioBar');
  const sel = document.getElementById('scenarioSelect');
  if (scenarios.length > 1) {
    bar.style.display = 'flex';
    sel.innerHTML = '';
    scenarios.forEach(function (s) {
      const opt = document.createElement('option');
      opt.value = s.id;
      opt.textContent = s.name;
      sel.appendChild(opt);
    });
  } else {
    bar.style.display = 'none';
  }
  currentScenario = scenarios[0];
  await onScenarioReady();
}

async function onScenarioReady() {
  await loadResources();
  renderFloorTabs();
  updatePageHead();
  renderSeats();
}

document.getElementById('scenarioSelect').addEventListener('change', async function () {
  const id = parseInt(this.value, 10);
  currentScenario = scenarios.find(function (s) { return s.id === id; });
  if (!currentScenario) return;
  selectedId = null;
  recommendIds.clear();
  recommendData = {};
  document.getElementById('btnConfirm').disabled = true;
  selTip.style.display = 'none';
  await onScenarioReady();
  if (currentDate) await loadAvailability();
  renderSeats();
  renderRecommendPanel();
});

/* 加载当前场景下所有资源，按 attributes.location 分组为楼层 */
async function loadResources() {
  if (!currentScenario) return;
  try {
    const data = await apiFetch(
      '/api/scenarios/' + currentScenario.id + '/resources?page=1&page_size=500'
    );
    const items = data.items || [];
    const groupMap = {};
    const order = [];
    items.forEach(function (r) {
      const attrs = r.attributes || {};
      const loc = attrs.location || '全部资源';
      if (!groupMap[loc]) { groupMap[loc] = []; order.push(loc); }
      groupMap[loc].push(r);
    });
    floors = order.map(function (loc) {
      const res = groupMap[loc];
      const first = res[0];
      return {
        location: loc,
        name: loc,
        resources: res,
        openStart: fmtTime(first.open_start),
        openEnd: fmtTime(first.open_end),
      };
    });
  } catch (e) {
    floors = [];
    showResult({
      type: 'fail',
      title: '加载资源失败',
      desc: e.message || '请检查后端服务',
    });
    return;
  }
  if (floors.length === 0) {
    showResult({
      type: 'fail',
      title: '暂无资源',
      desc: '该场景下尚未配置任何资源，请联系管理员添加。',
    });
    return;
  }
  currentFloorIdx = 0;
  buildSeatsFromFloor();
  syncTimeInputsToScenario();
}

/* 根据场景规则同步时段选择器的默认值与步长 */
function syncTimeInputsToScenario() {
  if (!currentScenario) return;
  const step = currentScenario.time_step_minutes || 30;
  const startEl = document.getElementById('reserveStart');
  const endEl = document.getElementById('reserveEnd');
  startEl.step = step * 60;
  endEl.step = step * 60;
  const floor = currentFloor();
  if (floor) {
    startEl.min = floor.openStart;
    startEl.max = floor.openEnd;
    endEl.min = floor.openStart;
    endEl.max = floor.openEnd;
  }
}

/* 由当前楼层资源构造前端座位结构（属性来自 attributes） */
function buildSeatsFromFloor() {
  const floor = currentFloor();
  if (!floor) { seats = []; return; }
  seats = floor.resources.map(function (r) {
    const a = r.attributes || {};
    const row = a.row || (r.code || '').split('-')[1] || '?';
    const col = a.col || 0;
    const displayId = row + (col || '');
    return {
      resourceId: r.id,
      code: r.code,
      id: displayId,
      row: row,
      col: col,
      is_available: r.is_active !== false,
      window: !!a.window,
      power: !!a.power,
      quiet: !!a.quiet,
      group: !!a.group,
      corner: !!a.corner,
      openStart: fmtTime(r.open_start),
      openEnd: fmtTime(r.open_end),
      booked: false,
      freeSlots: [],
    };
  });
}

/* ---------- 4. 楼层切换栏渲染 ---------- */
const floorTabsEl = document.getElementById('floorTabs');
const pageTitleEl = document.getElementById('pageTitle');
const pageSubEl = document.getElementById('pageSub');

function renderFloorTabs() {
  floorTabsEl.innerHTML = '';
  floors.forEach(function (f, idx) {
    const tab = document.createElement('div');
    tab.className = 'floor-tab' + (idx === currentFloorIdx ? ' active' : '');
    tab.innerHTML =
      '<span class="ft-icon">' + roomIcon(f.name) + '</span>' +
      '<span class="ft-name">' + f.location + '</span>' +
      '<span class="ft-area">' + f.name + '</span>';
    tab.addEventListener('click', function () { switchFloor(idx); });
    floorTabsEl.appendChild(tab);
  });
}

async function switchFloor(idx) {
  if (idx === currentFloorIdx) return;
  currentFloorIdx = idx;
  selectedId = null;
  recommendIds.clear();
  recommendData = {};
  document.getElementById('btnConfirm').disabled = true;
  selTip.style.display = 'none';
  updatePageHead();
  renderFloorTabs();
  buildSeatsFromFloor();
  syncTimeInputsToScenario();
  if (currentDate) await loadAvailability();
  renderSeats();
  renderRecommendPanel();
}

function updatePageHead() {
  const f = currentFloor();
  if (!f) return;
  const scenarioName = currentScenario ? currentScenario.name : '';
  pageTitleEl.textContent = scenarioName + ' · ' + f.location;
  pageSubEl.textContent =
    '开放时间 ' + f.openStart + ' - ' + f.openEnd +
    ' · 时段 ' + currentTimeStart + '-' + currentTimeEnd +
    ' · 请选择空闲座位后确认预约';
}

/* ---------- 5. 预约日期与时段选择 ---------- */
const dateInput = document.getElementById('reserveDate');
const timeStartInput = document.getElementById('reserveStart');
const timeEndInput = document.getElementById('reserveEnd');
const dateHint = document.getElementById('dateHint');
const roomLock = document.getElementById('roomLock');

function todayStr() {
  const d = new Date();
  const pad = function (n) { return n < 10 ? '0' + n : '' + n; };
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
}

dateInput.min = todayStr();
dateInput.value = '';

function readTimeRange() {
  currentTimeStart = timeStartInput.value || '08:00';
  currentTimeEnd = timeEndInput.value || '10:00';
}

async function onDateOrTimeChange() {
  currentDate = dateInput.value;
  readTimeRange();
  if (currentDate && currentTimeStart && currentTimeEnd && currentTimeStart < currentTimeEnd) {
    dateHint.textContent = '已选 ' + currentDate + ' ' + currentTimeStart + '-' + currentTimeEnd + '，现在可以选择座位';
    dateHint.classList.add('ready');
    roomLock.classList.add('hidden');
    await loadAvailability();
  } else {
    dateHint.textContent = '请先选择预约日期与时段，再选择座位';
    dateHint.classList.remove('ready');
    roomLock.classList.remove('hidden');
    seats.forEach(function (s) { s.booked = false; });
  }
  selectedId = null;
  document.getElementById('btnConfirm').disabled = true;
  selTip.style.display = 'none';
  updatePageHead();
  renderSeats();
  applyRecommend();
}

dateInput.addEventListener('change', onDateOrTimeChange);
timeStartInput.addEventListener('change', onDateOrTimeChange);
timeEndInput.addEventListener('change', onDateOrTimeChange);

/* 查询当前场景在当前日期各资源的空闲时段（对接 /api/scenarios/{id}/availability） */
async function loadAvailability() {
  if (!currentScenario || !currentDate) return;
  try {
    const data = await apiFetch(
      '/api/scenarios/' + currentScenario.id + '/availability?date=' + currentDate
    );
    const freeMap = {};
    (data.resources || []).forEach(function (r) {
      freeMap[r.resource_id] = r.free_slots || [];
    });
    seats.forEach(function (s) {
      s.freeSlots = freeMap[s.resourceId] || [];
      s.booked = !isFreeInRange(s.freeSlots, currentTimeStart, currentTimeEnd);
    });
  } catch (e) {
    /* 查询失败时保持原状 */
  }
}

/* 判断 [start,end] 时段是否被 freeSlots 的连续区间覆盖 */
function isFreeInRange(freeSlots, start, end) {
  if (!freeSlots || freeSlots.length === 0) return false;
  if (start >= end) return false;
  const sorted = freeSlots.slice().sort(function (a, b) {
    return a.start < b.start ? -1 : (a.start > b.start ? 1 : 0);
  });
  let cursor = start;
  for (let i = 0; i < sorted.length; i++) {
    const slot = sorted[i];
    if (slot.end <= cursor) continue;
    if (slot.start > cursor) return false;
    cursor = slot.end;
    if (cursor >= end) return true;
  }
  return cursor >= end;
}

/* 判断座位是否被占用 */
function seatTaken(s) {
  return !s.is_available || s.booked;
}

/* ---------- 6. 渲染座位网格 / 资源卡片 ---------- */
const roomMap = document.getElementById('roomMap');

/* 判断当前楼层资源是否具备 row/col 属性，决定用平面图还是卡片列表 */
function floorHasGrid() {
  const floor = currentFloor();
  if (!floor) return false;
  return floor.resources.some(function (r) {
    const a = r.attributes || {};
    return a.row != null && a.col != null;
  });
}

function renderSeats() {
  if (floorHasGrid()) {
    renderSeatMap();
  } else {
    renderResourceCards();
  }
}

/* 平面图渲染（资源有 row/col 属性时） */
function renderSeatMap() {
  roomMap.innerHTML = '';
  const rowMap = {};
  seats.forEach(function (s) { rowMap[s.row] = rowMap[s.row] || []; rowMap[s.row].push(s); });
  const rows = Object.keys(rowMap).sort();

  rows.forEach(function (r) {
    const rowEl = document.createElement('div');
    rowEl.className = 'row';

    const label = document.createElement('div');
    label.className = 'row-label';
    label.textContent = r + '排';
    rowEl.appendChild(label);

    const seatsWrap = document.createElement('div');
    seatsWrap.className = 'seats';

    const rowSeats = rowMap[r].slice().sort(function (a, b) { return a.col - b.col; });
    const maxCol = rowSeats.length;

    rowSeats.forEach(function (s, idx) {
      const taken = seatTaken(s);
      const el = document.createElement('div');
      el.className = 'seat';
      el.dataset.id = s.id;
      el.classList.add(taken ? 'occupied' : 'free');
      if (s.power) el.classList.add('has-power');

      let icons = '';
      if (s.window) icons += '🪟';
      if (s.power) icons += '🔌';
      if (icons) {
        const ic = document.createElement('div');
        ic.className = 'icons';
        ic.textContent = icons;
        el.appendChild(ic);
      }

      const num = document.createElement('div');
      num.className = 'num';
      num.textContent = s.id;
      el.appendChild(num);

      const tag = document.createElement('div');
      tag.className = 'tag';
      tag.textContent = s.group ? '讨论' : (s.quiet ? '安静' : '');
      el.appendChild(tag);

      el.addEventListener('click', function () { onSeatClick(s.id, el); });
      seatsWrap.appendChild(el);

      if (idx === Math.floor(maxCol / 2) - 1) {
        const aisle = document.createElement('div');
        aisle.className = 'aisle';
        seatsWrap.appendChild(aisle);
      }
    });
    rowEl.appendChild(seatsWrap);
    roomMap.appendChild(rowEl);
  });
  updateStat();
  applyRecommend();
}

/* 卡片列表渲染（资源无 row/col 属性时，适配场地/设备等通用场景） */
function renderResourceCards() {
  roomMap.innerHTML = '';
  const grid = document.createElement('div');
  grid.className = 'resource-card-grid';

  const sorted = seats.slice().sort(function (a, b) {
    return (a.code || a.id) < (b.code || b.id) ? -1 : 1;
  });

  sorted.forEach(function (s) {
    const taken = seatTaken(s);
    const card = document.createElement('div');
    card.className = 'resource-card' + (taken ? ' occupied' : ' free');
    card.dataset.id = s.id;

    const head = document.createElement('div');
    head.className = 'rc-head';
    head.innerHTML =
      '<span class="rc-code">' + esc(s.code || s.id) + '</span>' +
      '<span class="rc-name">' + esc(s.id) + '</span>' +
      '<span class="badge-status ' + (taken ? 'badge-off' : 'badge-on') + '">' + (taken ? '占用' : '空闲') + '</span>';
    card.appendChild(head);

    const meta = document.createElement('div');
    meta.className = 'rc-meta';
    meta.textContent = '开放 ' + s.openStart + '-' + s.openEnd;
    card.appendChild(meta);

    const attrKeys = ['window', 'power', 'quiet', 'group', 'corner'];
    const attrLabels = { window: '🪟靠窗', power: '🔌电源', quiet: '安静', group: '讨论', corner: '角落' };
    const chips = document.createElement('div');
    chips.className = 'rc-chips';
    attrKeys.forEach(function (k) {
      if (s[k]) {
        const chip = document.createElement('span');
        chip.className = 'attr-chip bool-true';
        chip.textContent = attrLabels[k];
        chips.appendChild(chip);
      }
    });
    card.appendChild(chips);

    const slotsWrap = document.createElement('div');
    slotsWrap.className = 'rc-slots';
    if (s.freeSlots && s.freeSlots.length) {
      const merged = mergeSlots(s.freeSlots);
      const label = document.createElement('span');
      label.className = 'rc-slots-label';
      label.textContent = '可约:';
      slotsWrap.appendChild(label);
      merged.slice(0, 12).forEach(function (m) {
        const tag = document.createElement('span');
        tag.className = 'avail-slot';
        tag.textContent = m.start + '-' + m.end;
        slotsWrap.appendChild(tag);
      });
      if (merged.length > 12) {
        const more = document.createElement('span');
        more.className = 'rc-slots-more';
        more.textContent = '等' + merged.length + '段';
        slotsWrap.appendChild(more);
      }
    } else if (currentDate) {
      const none = document.createElement('span');
      none.className = 'avail-slot none';
      none.textContent = '当天无空闲';
      slotsWrap.appendChild(none);
    } else {
      const hint = document.createElement('span');
      hint.className = 'rc-slots-label';
      hint.textContent = '选择日期后查看可约时段';
      slotsWrap.appendChild(hint);
    }
    card.appendChild(slotsWrap);

    card.addEventListener('click', function () { onSeatClick(s.id, card); });
    grid.appendChild(card);
  });
  roomMap.appendChild(grid);
  updateStat();
  applyRecommend();
}

/* ---------- 7. 座位点击：选中 / 取消 ---------- */
let selectedId = null;

function onSeatClick(id, el) {
  if (!currentDate) return;
  const s = seats.find(function (x) { return x.id === id; });
  if (!s || seatTaken(s)) return;

  document.querySelectorAll('.seat.selected, .resource-card.selected').forEach(function (e) {
    e.classList.remove('selected');
  });

  if (selectedId === id) {
    selectedId = null;
  } else {
    selectedId = id;
    el.classList.add('selected');
  }
  updateTip();
  document.getElementById('btnConfirm').disabled = !selectedId;
}

/* ---------- 8. 智能推荐（含匹配度） ---------- */
let recommendIds = new Set();
let recommendData = {};
let currentPrefLabels = [];

const PREF_LABELS = {
  quiet: '安静', window: '靠窗', power: '有电源', corner: '角落', group: '讨论',
};

function recommend(prefs, major) {
  recommendIds.clear();
  recommendData = {};

  const majorPref = {
    cs: ['power'],
    math: ['quiet'],
    literature: ['window'],
    art: ['window', 'corner'],
    science: ['power'],
  };
  const allPrefs = new Set(prefs);
  if (major && majorPref[major]) {
    majorPref[major].forEach(function (p) { allPrefs.add(p); });
  }

  currentPrefLabels = [];
  allPrefs.forEach(function (p) {
    if (PREF_LABELS[p]) currentPrefLabels.push(PREF_LABELS[p]);
  });

  const total = allPrefs.size;
  if (total === 0) {
    applyRecommend();
    renderRecommendPanel();
    return;
  }

  const candidates = seats
    .filter(function (s) { return !seatTaken(s); })
    .map(function (s) {
      let score = 0;
      const matched = [];
      allPrefs.forEach(function (p) {
        if (s[p]) {
          score++;
          if (PREF_LABELS[p]) matched.push(PREF_LABELS[p]);
        }
      });
      return { s: s, score: score, matched: matched };
    })
    .sort(function (a, b) { return b.score - a.score; });

  const maxScore = candidates.length ? candidates[0].score : 0;
  if (maxScore > 0) {
    candidates
      .filter(function (x) { return x.score === maxScore; })
      .slice(0, 5)
      .forEach(function (x) {
        recommendIds.add(x.s.id);
        recommendData[x.s.id] = {
          score: x.score,
          total: total,
          percent: Math.round(x.score / total * 100),
          matched: x.matched,
        };
      });
  }
  applyRecommend();
  renderRecommendPanel();
}

function applyRecommend() {
  document.querySelectorAll('.seat.recommend, .resource-card.recommend').forEach(function (e) {
    e.classList.remove('recommend');
    e.removeAttribute('data-match');
  });
  recommendIds.forEach(function (id) {
    const el = document.querySelector('.seat[data-id="' + id + '"], .resource-card[data-id="' + id + '"]');
    if (el && !el.classList.contains('selected') && !el.classList.contains('occupied')) {
      el.classList.add('recommend');
      const d = recommendData[id];
      if (d) el.setAttribute('data-match', d.percent + '%');
    }
  });
  updateStat();
}

function renderRecommendPanel() {
  const panel = document.getElementById('recommendPanel');
  panel.innerHTML = '';

  if (recommendIds.size === 0) {
    panel.classList.remove('show');
    return;
  }
  panel.classList.add('show');

  const head = document.createElement('div');
  head.className = 'rp-head';
  head.textContent = '🎯 为你推荐以下座位（按匹配度排序，点击可选中）';
  panel.appendChild(head);

  if (currentPrefLabels.length) {
    const cond = document.createElement('div');
    cond.className = 'rp-cond';
    cond.innerHTML = '预期条件：<b>' + currentPrefLabels.join(' · ') + '</b>';
    panel.appendChild(cond);
  }

  const list = document.createElement('div');
  list.className = 'recommend-list';

  Array.from(recommendIds).forEach(function (id) {
    const d = recommendData[id];
    const item = document.createElement('div');
    item.className = 'recommend-item';

    const seat = document.createElement('span');
    seat.className = 'ri-seat';
    seat.textContent = id;

    const barWrap = document.createElement('div');
    barWrap.className = 'ri-bar-wrap';
    const bar = document.createElement('div');
    bar.className = 'ri-bar';
    bar.style.width = d.percent + '%';
    barWrap.appendChild(bar);

    const percent = document.createElement('span');
    percent.className = 'ri-percent';
    percent.textContent = d.percent + '%';

    const tags = document.createElement('span');
    tags.className = 'ri-tags';
    tags.textContent = d.matched.length ? d.matched.join(' · ') : '无匹配';

    item.appendChild(seat);
    item.appendChild(barWrap);
    item.appendChild(percent);
    item.appendChild(tags);

    item.addEventListener('click', function () {
      const el = document.querySelector('.seat[data-id="' + id + '"]');
      if (el) {
        onSeatClick(id, el);
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    });
    list.appendChild(item);
  });
  panel.appendChild(list);
}

/* ---------- 9. 统计 & 提示 ---------- */
function updateStat() {
  const free = seats.filter(function (s) { return !seatTaken(s); }).length;
  document.getElementById('statFree').textContent = free;
  document.getElementById('statOcc').textContent = seats.length - free;
  document.getElementById('statRec').textContent = recommendIds.size;
}

const selTip = document.getElementById('selTip');
function updateTip() {
  if (selectedId) {
    const f = currentFloor();
    selTip.textContent = '已选中座位：' + (f ? f.location : '') + ' · ' + selectedId +
      '（' + currentDate + ' ' + currentTimeStart + '-' + currentTimeEnd + '）';
    selTip.style.display = 'block';
  } else {
    selTip.style.display = 'none';
  }
}

/* ---------- 10. 偏好弹窗交互 ---------- */
const chips = document.querySelectorAll('#prefChips .chip');
let selectedPrefs = [];

chips.forEach(function (chip) {
  chip.addEventListener('click', function () {
    chip.classList.toggle('on');
  });
});

function getSelectedPrefs() {
  return Array.from(document.querySelectorAll('#prefChips .chip.on'))
    .map(function (c) { return c.dataset.pref; });
}

document.getElementById('btnRecommend').addEventListener('click', function () {
  selectedPrefs = getSelectedPrefs();
  const major = document.getElementById('majorSelect').value;
  recommend(selectedPrefs, major);
  prefModal.style.display = 'none';
  if (recommendIds.size) {
    const first = Array.from(recommendIds)[0];
    const el = document.querySelector('.seat[data-id="' + first + '"]');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
});

document.getElementById('btnSkip').addEventListener('click', function () {
  prefModal.style.display = 'none';
});

document.getElementById('btnReopen').addEventListener('click', function () {
  prefModal.style.display = 'flex';
});

/* ---------- 11. 我的预约数据与渲染 ---------- */
let myReservations = [];

async function loadReservations() {
  try {
    myReservations = await apiFetch('/api/reservations?status=all');
  } catch (e) {
    myReservations = [];
  }
  return myReservations;
}

function seatAreaText(s) {
  if (s.group) return '讨论区';
  if (s.quiet) return '安静区';
  if (s.window) return '靠窗区';
  return '普通区';
}

function renderReservations() {
  const listEl = document.getElementById('reservationList');
  const emptyEl = document.getElementById('reservationEmpty');
  const countEl = document.getElementById('resCount');
  listEl.innerHTML = '';

  const validList = myReservations.filter(function (r) {
    return r.status === 'confirmed' || r.status === 'pending';
  });
  countEl.textContent = validList.length + ' 条预约';

  if (validList.length === 0) {
    emptyEl.classList.remove('hidden');
    return;
  }
  emptyEl.classList.add('hidden');

  validList.forEach(function (res) {
    const card = document.createElement('div');
    card.className = 'res-card';

    const seatLabel = res.resource_code || res.resource_name || '';
    const scenarioLabel = res.scenario_name || '';

    const seat = document.createElement('div');
    seat.className = 'res-seat';
    seat.innerHTML =
      '<span class="rs-floor">' + scenarioLabel + '</span>' +
      '<span class="rs-id">' + seatLabel + '</span>';
    card.appendChild(seat);

    const info = document.createElement('div');
    info.className = 'res-info';

    const top = document.createElement('div');
    top.className = 'res-top';
    const name = document.createElement('span');
    name.className = 'res-name';
    name.textContent = scenarioLabel + ' · ' + seatLabel;
    const badge = document.createElement('span');
    badge.className = 'res-badge valid';
    badge.textContent = '有效';
    top.appendChild(name);
    top.appendChild(badge);

    const meta = document.createElement('div');
    meta.className = 'res-meta';
    meta.textContent =
      '预约日期：' + isoDate(res.start_time) +
      ' · 时段：' + isoTime(res.start_time) + '-' + isoTime(res.end_time);

    info.appendChild(top);
    info.appendChild(meta);
    card.appendChild(info);

    const actions = document.createElement('div');
    actions.className = 'res-actions';
    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'btn-cancel';
    cancelBtn.textContent = '取消预约';
    cancelBtn.addEventListener('click', function () { cancelReservation(res); });
    actions.appendChild(cancelBtn);
    card.appendChild(actions);

    listEl.appendChild(card);
  });
}

async function cancelReservation(res) {
  try {
    await apiFetch('/api/reservations/' + res.id + '/cancel', { method: 'PUT' });
    await loadReservations();
    if (currentDate) await loadAvailability();
    renderReservations();
    renderSeats();
    showResult({
      type: 'success',
      title: '已取消预约',
      desc: '座位已释放，可在历史记录中查看。',
      detail: [
        { k: '预约场景', v: res.scenario_name || '' },
        { k: '资源', v: res.resource_code || res.resource_name || '' },
        { k: '预约日期', v: isoDate(res.start_time) },
      ],
    });
  } catch (e) {
    showResult({
      type: 'fail',
      title: '取消失败',
      desc: e.message || '请稍后重试',
    });
  }
}

document.getElementById('btnGoReserve').addEventListener('click', function () {
  const link = document.querySelector('.nav-menu a[data-view="reserve"]');
  switchView('reserve', link);
});

/* ---------- 12. 个人中心渲染 ---------- */
function renderProfile() {
  if (!currentUser) return;

  const displayName = currentUser.name || currentUser.username;
  document.getElementById('profileAvatar').textContent = displayName.charAt(0);
  document.getElementById('profileName').textContent = displayName;
  document.getElementById('profileSid').textContent = currentUser.student_id || currentUser.username;

  const total = myReservations.length;
  const valid = myReservations.filter(function (r) {
    return r.status === 'confirmed' || r.status === 'pending';
  }).length;
  const cancelled = myReservations.filter(function (r) {
    return r.status === 'cancelled';
  }).length;

  document.getElementById('statTotal').textContent = total;
  document.getElementById('statValid').textContent = valid;
  document.getElementById('statCancel').textContent = cancelled;

  const listEl = document.getElementById('historyList');
  const emptyEl = document.getElementById('historyEmpty');
  listEl.innerHTML = '';

  const sorted = myReservations.slice().sort(function (a, b) {
    return new Date(b.created_at) - new Date(a.created_at);
  });

  if (sorted.length === 0) {
    emptyEl.classList.remove('hidden');
    return;
  }
  emptyEl.classList.add('hidden');

  sorted.forEach(function (r) {
    const isCancel = r.status === 'cancelled';
    const item = document.createElement('div');
    item.className = 'history-item';

    const icon = document.createElement('div');
    icon.className = 'hi-icon ' + (isCancel ? 'cancel' : 'reserve');
    icon.textContent = isCancel ? '❌' : '✅';

    const body = document.createElement('div');
    body.className = 'hi-body';

    const title = document.createElement('div');
    title.className = 'hi-title';
    const seatLabel = (r.scenario_name || '') + ' · ' + (r.resource_code || r.resource_name || '');
    if (isCancel) {
      title.innerHTML = '取消预约 <span class="hi-cancel">' + seatLabel + '</span>';
    } else {
      title.innerHTML = '预约资源 <span class="hi-seat">' + seatLabel + '</span>';
    }

    const meta = document.createElement('div');
    meta.className = 'hi-meta';
    meta.innerHTML =
      '预约日期：<b>' + isoDate(r.start_time) + '</b> · 时段：<b>' +
      isoTime(r.start_time) + '-' + isoTime(r.end_time) + '</b><br>' +
      '状态：<b>' + r.status + '</b> · 创建时间：<b>' + fmtDateTime(r.created_at) + '</b>';

    body.appendChild(title);
    body.appendChild(meta);
    item.appendChild(icon);
    item.appendChild(body);
    listEl.appendChild(item);
  });
}

/* ---------- 13. 预约结果弹窗 ---------- */
const resultModal = document.getElementById('resultModal');

function showResult(opt) {
  document.getElementById('resultIcon').className = 'result-icon ' + opt.type;
  document.getElementById('resultIcon').textContent = opt.type === 'success' ? '✅' : '⚠️';
  document.getElementById('resultTitle').textContent = opt.title;
  document.getElementById('resultDesc').textContent = opt.desc;

  const resultDetail = document.getElementById('resultDetail');
  resultDetail.innerHTML = '';
  if (opt.detail && opt.detail.length) {
    opt.detail.forEach(function (d) {
      const row = document.createElement('div');
      row.className = 'row-item';
      row.innerHTML = '<span>' + d.k + '</span><span>' + d.v + '</span>';
      resultDetail.appendChild(row);
    });
    resultDetail.style.display = 'block';
  } else {
    resultDetail.style.display = 'none';
  }

  const actionBtn = document.getElementById('resultAction');
  actionBtn.textContent = opt.actionText || '好的';
  actionBtn.className = 'btn btn-primary';
  actionBtn.onclick = function () {
    resultModal.style.display = 'none';
    if (opt.onAction) opt.onAction();
  };
  const closeBtn = document.getElementById('resultClose');
  closeBtn.textContent = opt.closeText || '关闭';
  closeBtn.onclick = function () {
    resultModal.style.display = 'none';
    if (opt.onClose) opt.onClose();
  };

  resultModal.style.display = 'flex';
}

/* ---------- 14. 确认预约 ---------- */
document.getElementById('btnConfirm').addEventListener('click', async function () {
  if (!selectedId) return;
  if (!currentDate) {
    showResult({ type: 'fail', title: '请先选择日期', desc: '预约前请先在顶部选择预约日期与时段。', actionText: '知道了' });
    return;
  }
  if (!currentTimeStart || !currentTimeEnd || currentTimeStart >= currentTimeEnd) {
    showResult({ type: 'fail', title: '时段无效', desc: '请选择有效的开始与结束时间（开始早于结束）。', actionText: '知道了' });
    return;
  }

  const s = seats.find(function (x) { return x.id === selectedId; });
  if (!s) return;
  const f = currentFloor();
  if (!f) return;

  if (seatTaken(s)) {
    showResult({
      type: 'fail',
      title: '预约失败',
      desc: '该资源在所选时段已被预约，请重新选择。',
      detail: [
        { k: '所在区域', v: f.location },
        { k: '资源编号', v: s.code || selectedId },
        { k: '预约日期', v: currentDate },
        { k: '预约时段', v: currentTimeStart + ' - ' + currentTimeEnd },
        { k: '失败原因', v: '资源已被占用' },
      ],
      actionText: '重新选择',
    });
    selectedId = null;
    document.getElementById('btnConfirm').disabled = true;
    selTip.style.display = 'none';
    return;
  }

  const startTimeIso = currentDate + 'T' + currentTimeStart + ':00';
  const endTimeIso = currentDate + 'T' + currentTimeEnd + ':00';

  try {
    await apiFetch('/api/reservations', {
      method: 'POST',
      body: {
        scenario_id: currentScenario.id,
        resource_id: s.resourceId,
        start_time: startTimeIso,
        end_time: endTimeIso,
      },
    });

    const bookedId = selectedId;
    const bookedDate = currentDate;
    const bookedRange = currentTimeStart + ' - ' + currentTimeEnd;
    selectedId = null;
    document.getElementById('btnConfirm').disabled = true;
    selTip.style.display = 'none';

    await loadAvailability();
    await loadReservations();
    renderSeats();
    renderReservations();

    showResult({
      type: 'success',
      title: '预约成功！',
      desc: '请在预约时段内到达，逾期可能被系统取消。',
      detail: [
        { k: '预约人', v: currentUser ? (currentUser.name || currentUser.username) : '—' },
        { k: '预约场景', v: currentScenario ? currentScenario.name : '' },
        { k: '所在区域', v: f.location },
        { k: '资源编号', v: s.code || bookedId },
        { k: '资源区域', v: seatAreaText(s) },
        { k: '预约日期', v: bookedDate },
        { k: '预约时段', v: bookedRange },
      ],
      closeText: '查看我的预约',
      onClose: function () {
        const link = document.querySelector('.nav-menu a[data-view="mine"]');
        switchView('mine', link);
      },
      actionText: '继续预约',
    });
  } catch (e) {
    showResult({
      type: 'fail',
      title: '预约失败',
      desc: e.message || '请稍后重试',
      detail: [
        { k: '所在区域', v: f.location },
        { k: '资源编号', v: s.code || selectedId },
        { k: '预约日期', v: currentDate },
        { k: '预约时段', v: currentTimeStart + ' - ' + currentTimeEnd },
      ],
      actionText: '重新选择',
    });
  }
});

/* ---------- 15. 初始化 ---------- */
async function init() {
  const token = getToken();
  if (token) {
    try {
      currentUser = await apiFetch('/api/users/me');
      const displayName = currentUser.name || currentUser.username;
      document.getElementById('navUserName').textContent = displayName;
      document.getElementById('navAvatar').textContent = displayName.charAt(0);
      updateAdminMenuVisibility();
      await loadScenarios();
      return;
    } catch (e) {
      clearToken();
    }
  }
  loginModal.style.display = 'flex';
}

init();

/* ============================================================
 * 16. AI 智能体交互窗口（前端占位，后端 agent 接口待接入）
 * ============================================================ */
const AGENT_API = '/api/agent/chat';   // 后端 agent 对话接口（SSE 流式）
const AGENT_DEMO = false;              // 演示模式：后端未就绪时用本地模拟回复

function getAgentSessionId() {
  let id = localStorage.getItem('agent_session_id');
  if (!id) {
    id = 'session_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8);
    localStorage.setItem('agent_session_id', id);
  }
  return id;
}

const agentFab = document.getElementById('agentFab');
const agentPanel = document.getElementById('agentPanel');
const agentMsgs = document.getElementById('agentMsgs');
const agentInput = document.getElementById('agentInput');
const agentSend = document.getElementById('agentSend');
const agentStatus = document.getElementById('agentStatus');
const agentClose = document.getElementById('agentClose');

const SUGGESTIONS = [
  '帮我推荐一个安静靠窗的座位',
  '今天有哪些空闲座位',
  '怎么预约座位',
  '我的预约记录',
];

/* ---------- 16.1 打开 / 关闭窗口 ---------- */
function openAgent() {
  agentPanel.classList.add('show');
  agentFab.classList.add('open');
  agentFab.textContent = '✕';
  if (!agentMsgs.childElementCount) renderSuggestions();
  setTimeout(function () { agentInput.focus(); }, 60);
}

function closeAgent() {
  agentPanel.classList.remove('show');
  agentFab.classList.remove('open');
  agentFab.textContent = '🤖';
}

agentFab.addEventListener('click', function () {
  agentPanel.classList.contains('show') ? closeAgent() : openAgent();
});
agentClose.addEventListener('click', closeAgent);

/* ---------- 16.2 消息渲染 ---------- */
function appendMsg(role, text) {
  const div = document.createElement('div');
  div.className = 'agent-msg ' + role;
  div.textContent = text;
  agentMsgs.appendChild(div);
  agentMsgs.scrollTop = agentMsgs.scrollHeight;
  return div;
}

function renderSuggestions() {
  const wrap = document.createElement('div');
  wrap.className = 'agent-suggest';
  SUGGESTIONS.forEach(function (s) {
    const b = document.createElement('button');
    b.textContent = s;
    b.addEventListener('click', function () {
      agentInput.value = s;
      sendMessage();
    });
    wrap.appendChild(b);
  });
  agentMsgs.appendChild(wrap);
  agentMsgs.scrollTop = agentMsgs.scrollHeight;
}

/* ---------- 16.3 发送消息 ---------- */
async function sendMessage() {
  const text = agentInput.value.trim();
  if (!text) return;
  agentInput.value = '';
  appendMsg('user', text);

  agentSend.disabled = true;
  agentStatus.textContent = '思考中…';
  const thinking = appendMsg('bot', '…');

  let reply;
  try {
    if (AGENT_DEMO) {
      await new Promise(function (r) { setTimeout(r, 500); });
      reply = demoReply(text);
      thinking.textContent = reply;
    } else {
      reply = await streamChat(text, function (partial) {
        thinking.textContent = partial;
        agentMsgs.scrollTop = agentMsgs.scrollHeight;
      });
    }
  } catch (e) {
    reply = '⚠️ 智能体服务异常：' + (e.message || '未知错误') + '（请确认后端已启动并已配置 DeepSeek API Key）';
    thinking.textContent = reply;
  }

  agentStatus.textContent = '在线 · 帮你选座、查预约';
  agentSend.disabled = false;
}

async function streamChat(text, onPartial) {
  const token = getToken();
  const resp = await fetch(API_BASE + AGENT_API, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + token,
    },
    body: JSON.stringify({ message: text, session_id: getAgentSessionId() }),
  });

  if (!resp.ok) {
    let msg = 'HTTP ' + resp.status;
    try {
      const j = await resp.json();
      if (j && j.message) msg = j.message;
    } catch (e) {}
    throw { message: msg };
  }
  if (!resp.body) throw { message: '浏览器不支持流式响应' };

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let full = '';

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
      try {
        payload = JSON.parse(line.slice(5).trim());
      } catch (e) {
        continue;
      }
      if (payload.error) throw { message: payload.error };
      if (payload.content) {
        full += payload.content;
        if (onPartial) onPartial(full);
      }
      if (payload.done) return full || '（无回复内容）';
    }
  }
  return full || '（无回复内容）';
}

agentSend.addEventListener('click', sendMessage);
agentInput.addEventListener('keydown', function (e) {
  if (e.key === 'Enter') sendMessage();
});

/* ---------- 16.4 演示模式本地回复（后端未接入时的占位） ---------- */
function demoReply(text) {
  const t = text || '';
  const floor = currentFloor();
  if (t.indexOf('座位') >= 0 || t.indexOf('推荐') >= 0 || t.indexOf('选座') >= 0) {
    const freeList = seats.filter(function (s) { return !seatTaken(s); }).slice(0, 5);
    if (freeList.length) {
      return '为你找到以下空闲资源：\n' +
        freeList.map(function (s) {
          return '· ' + (floor ? floor.location : '') + ' ' + (s.code || s.id) +
            (s.window ? ' 🪟靠窗' : '') +
            (s.power ? ' 🔌电源' : '') +
            (s.quiet ? ' 安静区' : '') +
            (s.group ? ' 讨论区' : '');
        }).join('\n') +
        '\n\n点击座位图上的座位即可选中预约。';
    }
    return '当前区域暂时没有空闲资源，可以切换其他区域看看～';
  }
  if (t.indexOf('预约') >= 0 && t.indexOf('怎么') >= 0) {
    return '预约步骤很简单：\n① 顶部选择预约日期与时段\n② 选择区域\n③ 点击空闲座位（或让我推荐）\n④ 点击「确认预约」\n\n请在预约时段内到达哦～';
  }
  if (t.indexOf('预约记录') >= 0 || t.indexOf('我的预约') >= 0) {
    if (myReservations.length) {
      return '你当前有 ' + myReservations.length + ' 条预约记录，可以在「我的预约」页面查看详情。';
    }
    return '你暂时还没有预约记录，先去预约一个座位吧～';
  }
  if (t.indexOf('你好') >= 0 || t.indexOf('hi') >= 0 || t.indexOf('hello') >= 0) {
    return '你好呀！我是图书馆智能助手 🤖\n我可以帮你推荐座位、查询空闲情况、解答预约问题。\n目前为前端演示模式，接入后端后我还能直接操作数据库为你服务。';
  }
  return '收到你的问题：「' + t + '」\n\n目前处于演示模式，我会在接入后端接口后提供更智能的回答。你可以试着问我：推荐座位、空闲查询、预约流程。';
}

/* ============================================================
 * 17. 管理后台（场景/资源 CRUD + 可预约状态查询）
 *    仅 admin 角色可用，复用 apiFetch / showResult / fmtTime
 * ============================================================ */
function updateAdminMenuVisibility() {
  const item = document.getElementById('navAdminItem');
  if (!item) return;
  item.style.display = currentUser ? '' : 'none';
}

/* ---------- 17.1 管理视图状态与加载 ---------- */
let adminScenarios = [];
let adminCurrentScenario = null;
let adminResources = [];
let editingScenarioId = null;     // null=新建，否则=编辑
let editingResourceId = null;     // null=新建，否则=编辑

async function loadAdminView() {
  if (!currentUser) {
    showResult({ type: 'fail', title: '请先登录', desc: '登录后可管理你的预约场景。', actionText: '知道了' });
    return;
  }
  await loadAdminScenarios();
  document.getElementById('adminResourcePanel').style.display = 'none';
  adminCurrentScenario = null;
}

async function loadAdminScenarios() {
  try {
    const data = await apiFetch('/api/scenarios?page=1&page_size=200&mine=true');
    adminScenarios = data.items || [];
  } catch (e) {
    adminScenarios = [];
    showResult({ type: 'fail', title: '加载场景失败', desc: e.message || '请检查后端服务' });
  }
  renderAdminScenarios();
}

function renderAdminScenarios() {
  const tbody = document.getElementById('adminScenarioTbody');
  const empty = document.getElementById('adminScenarioEmpty');
  const count = document.getElementById('adminScenarioCount');
  tbody.innerHTML = '';
  count.textContent = adminScenarios.length + ' 个场景';

  if (adminScenarios.length === 0) {
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');

  adminScenarios.forEach(function (s) {
    const tr = document.createElement('tr');
    tr.innerHTML =
      '<td class="col-id">' + s.id + '</td>' +
      '<td>' + esc(s.name) + (s.description ? '<br><span class="form-tip">' + esc(s.description) + '</span>' : '') + '</td>' +
      '<td>' + s.time_step_minutes + '</td>' +
      '<td>' + s.min_duration_minutes + '-' + s.max_duration_minutes + '</td>' +
      '<td>' + (s.allow_same_day ? '可当日' : '不可当日') + ' / 最多' + s.max_advance_days + '天' + (s.min_advance_minutes ? ' / 至少' + s.min_advance_minutes + '分' : '') + '</td>' +
      '<td>活跃' + s.max_active_per_user + (s.max_minutes_per_day ? ' / 日' + s.max_minutes_per_day + '分' : '') + '</td>' +
      '<td><span class="badge-status ' + (s.is_active ? 'badge-on' : 'badge-off') + '">' + (s.is_active ? '启用' : '停用') + '</span></td>' +
      '<td><div class="admin-actions"></div></td>';

    const actions = tr.querySelector('.admin-actions');
    const btnEdit = document.createElement('button');
    btnEdit.className = 'btn-act primary';
    btnEdit.textContent = '编辑';
    btnEdit.addEventListener('click', function () { openScenarioModal(s); });
    actions.appendChild(btnEdit);

    const btnRes = document.createElement('button');
    btnRes.className = 'btn-act';
    btnRes.textContent = '管理资源';
    btnRes.addEventListener('click', function () { openResourcePanel(s); });
    actions.appendChild(btnRes);

    const btnDel = document.createElement('button');
    btnDel.className = 'btn-act danger';
    btnDel.textContent = '删除';
    btnDel.addEventListener('click', function () { deleteAdminScenario(s); });
    actions.appendChild(btnDel);

    tbody.appendChild(tr);
  });
}

/* 简单 HTML 转义，避免名称中含特殊字符破坏表格 */
function esc(str) {
  return String(str == null ? '' : str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ---------- 17.2 场景编辑弹窗 ---------- */
const scenarioModal = document.getElementById('scenarioModal');

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

  scenarioModal.style.display = 'flex';
}

document.getElementById('btnNewScenario').addEventListener('click', function () { openScenarioModal(null); });
document.getElementById('btnScenarioCancel').addEventListener('click', function () { scenarioModal.style.display = 'none'; });

async function saveScenario() {
  const errEl = document.getElementById('scenarioFormError');
  const name = document.getElementById('sfName').value.trim();
  if (!name) { errEl.textContent = '请输入场景名称'; return; }

  const minD = parseInt(document.getElementById('sfMinDuration').value, 10);
  const maxD = parseInt(document.getElementById('sfMaxDuration').value, 10);
  if (!(minD > 0) || !(maxD > 0)) { errEl.textContent = '请输入有效的时长范围'; return; }
  if (minD > maxD) { errEl.textContent = '最小时长不能大于最大时长'; return; }

  const body = {
    name: name,
    description: document.getElementById('sfDescription').value.trim() || null,
    is_active: document.getElementById('sfIsActive').value === 'true',
    time_step_minutes: parseInt(document.getElementById('sfTimeStep').value, 10) || 30,
    min_duration_minutes: minD,
    max_duration_minutes: maxD,
    max_advance_days: parseInt(document.getElementById('sfMaxAdvanceDays').value, 10) || 0,
    min_advance_minutes: parseInt(document.getElementById('sfMinAdvanceMinutes').value, 10) || 0,
    allow_same_day: document.getElementById('sfAllowSameDay').value === 'true',
    max_active_per_user: parseInt(document.getElementById('sfMaxActivePerUser').value, 10) || 5,
  };
  const mmpd = document.getElementById('sfMaxMinutesPerDay').value.trim();
  body.max_minutes_per_day = mmpd ? parseInt(mmpd, 10) : null;
  const cbm = document.getElementById('sfCancelBeforeMinutes').value.trim();
  body.cancel_before_minutes = cbm ? parseInt(cbm, 10) : null;

  errEl.textContent = '';
  try {
    if (editingScenarioId) {
      await apiFetch('/api/scenarios/' + editingScenarioId, { method: 'PUT', body: body });
    } else {
      await apiFetch('/api/scenarios', { method: 'POST', body: body });
    }
    scenarioModal.style.display = 'none';
    await loadAdminScenarios();
    showResult({ type: 'success', title: '保存成功', desc: '场景「' + name + '」已保存。' });
  } catch (e) {
    errEl.textContent = e.message || '保存失败';
  }
}
document.getElementById('btnScenarioSave').addEventListener('click', saveScenario);

async function deleteAdminScenario(s) {
  if (!confirm('确认删除场景「' + s.name + '」？\n该场景下所有资源与预约将一并删除，此操作不可恢复。')) return;
  try {
    await apiFetch('/api/scenarios/' + s.id, { method: 'DELETE' });
    await loadAdminScenarios();
    showResult({ type: 'success', title: '已删除', desc: '场景「' + s.name + '」已删除。' });
  } catch (e) {
    showResult({ type: 'fail', title: '删除失败', desc: e.message || '请稍后重试' });
  }
}

/* ---------- 17.3 资源管理面板 ---------- */
const resourceModal = document.getElementById('resourceModal');

async function openResourcePanel(s) {
  adminCurrentScenario = s;
  document.getElementById('adminResourcePanel').style.display = '';
  document.getElementById('adminResourceScenarioName').textContent = '· ' + s.name;
  document.getElementById('adminAvailDate').value = todayStr();
  document.getElementById('adminAvailResult').innerHTML = '';
  document.getElementById('adminAvailHint').textContent = '选择日期后查看各资源当天空闲时段';
  await loadAdminResources();
  /* 资源面板滚动到视口顶部 */
  document.getElementById('adminResourcePanel').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function loadAdminResources() {
  if (!adminCurrentScenario) return;
  try {
    const data = await apiFetch(
      '/api/scenarios/' + adminCurrentScenario.id + '/resources?page=1&page_size=500'
    );
    adminResources = data.items || [];
  } catch (e) {
    adminResources = [];
    showResult({ type: 'fail', title: '加载资源失败', desc: e.message || '请检查后端服务' });
  }
  renderAdminResources();
}

function renderAdminResources() {
  const tbody = document.getElementById('adminResourceTbody');
  const empty = document.getElementById('adminResourceEmpty');
  const count = document.getElementById('adminResourceCount');
  tbody.innerHTML = '';
  count.textContent = adminResources.length + ' 个资源';

  if (adminResources.length === 0) {
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');

  adminResources.forEach(function (r) {
    const tr = document.createElement('tr');
    tr.innerHTML =
      '<td class="col-id">' + r.id + '</td>' +
      '<td class="col-code">' + esc(r.code) + '</td>' +
      '<td>' + esc(r.name) + '</td>' +
      '<td>' + fmtTime(r.open_start) + '-' + fmtTime(r.open_end) + '</td>' +
      '<td class="col-attrs"><div class="attr-chips"></div></td>' +
      '<td><span class="badge-status ' + (r.is_active ? 'badge-on' : 'badge-off') + '">' + (r.is_active ? '启用' : '停用') + '</span></td>' +
      '<td><div class="admin-actions"></div></td>';

    /* 属性标签 */
    const chips = tr.querySelector('.attr-chips');
    const attrs = r.attributes || {};
    Object.keys(attrs).forEach(function (k) {
      const v = attrs[k];
      const chip = document.createElement('span');
      let cls = 'attr-chip';
      let text = k + '=' + String(v);
      if (v === true) { cls += ' bool-true'; text = k; }
      else if (v === false) { cls += ' bool-false'; text = '¬' + k; }
      chip.className = cls;
      chip.textContent = text;
      chips.appendChild(chip);
    });

    const actions = tr.querySelector('.admin-actions');
    const btnEdit = document.createElement('button');
    btnEdit.className = 'btn-act primary';
    btnEdit.textContent = '编辑';
    btnEdit.addEventListener('click', function () { openResourceModal(r); });
    actions.appendChild(btnEdit);

    const btnDel = document.createElement('button');
    btnDel.className = 'btn-act danger';
    btnDel.textContent = '删除';
    btnDel.addEventListener('click', function () { deleteAdminResource(r); });
    actions.appendChild(btnDel);

    tbody.appendChild(tr);
  });
}

document.getElementById('btnBackToScenarios').addEventListener('click', function () {
  document.getElementById('adminResourcePanel').style.display = 'none';
  adminCurrentScenario = null;
  document.querySelector('.admin-card').scrollIntoView({ behavior: 'smooth', block: 'start' });
});

/* ---------- 17.4 资源编辑弹窗 ---------- */
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
  resourceModal.style.display = 'flex';
}

document.getElementById('btnNewResource').addEventListener('click', function () { openResourceModal(null); });
document.getElementById('btnResourceCancel').addEventListener('click', function () { resourceModal.style.display = 'none'; });

/* attributes 键值对编辑器 */
function renderAttrEditor(attrs) {
  const wrap = document.getElementById('attrEditor');
  wrap.innerHTML = '';
  const keys = Object.keys(attrs || {});
  if (keys.length === 0) {
    const tip = document.createElement('div');
    tip.className = 'attr-empty';
    tip.textContent = '暂无扩展属性，点击「添加属性」可新增（如 location、row、col、window 等）';
    wrap.appendChild(tip);
    return;
  }
  keys.forEach(function (k) { wrap.appendChild(buildAttrRow(k, attrs[k])); });
}

function buildAttrRow(key, val) {
  const row = document.createElement('div');
  row.className = 'attr-row';

  const keyInput = document.createElement('input');
  keyInput.className = 'attr-key';
  keyInput.type = 'text';
  keyInput.value = key;
  keyInput.placeholder = '属性名';

  const valInput = document.createElement('input');
  valInput.className = 'attr-val';
  valInput.type = 'text';
  valInput.value = val === true ? 'true' : (val === false ? 'false' : String(val));
  valInput.placeholder = '属性值';

  const rm = document.createElement('button');
  rm.className = 'attr-remove';
  rm.type = 'button';
  rm.textContent = '✕';
  rm.addEventListener('click', function () { row.remove(); });

  row.appendChild(keyInput);
  row.appendChild(valInput);
  row.appendChild(rm);
  return row;
}

document.getElementById('btnAddAttr').addEventListener('click', function () {
  const wrap = document.getElementById('attrEditor');
  const empty = wrap.querySelector('.attr-empty');
  if (empty) empty.remove();
  wrap.appendChild(buildAttrRow('', ''));
});

function collectAttrs() {
  const wrap = document.getElementById('attrEditor');
  const rows = wrap.querySelectorAll('.attr-row');
  const obj = {};
  rows.forEach(function (row) {
    const k = row.querySelector('.attr-key').value.trim();
    const v = row.querySelector('.attr-val').value.trim();
    if (!k) return;
    /* 尝试解析 bool / number，否则保留字符串 */
    if (v === 'true') obj[k] = true;
    else if (v === 'false') obj[k] = false;
    else if (v !== '' && !isNaN(Number(v)) && /^-?\d+(\.\d+)?$/.test(v)) obj[k] = Number(v);
    else obj[k] = v;
  });
  return obj;
}

async function saveResource() {
  const errEl = document.getElementById('resourceFormError');
  if (!adminCurrentScenario) { errEl.textContent = '未选择场景'; return; }

  const name = document.getElementById('rfName').value.trim();
  const code = document.getElementById('rfCode').value.trim();
  if (!name) { errEl.textContent = '请输入资源名称'; return; }
  if (!code) { errEl.textContent = '请输入资源编号'; return; }

  const openStart = document.getElementById('rfOpenStart').value;
  const openEnd = document.getElementById('rfOpenEnd').value;
  if (!openStart || !openEnd) { errEl.textContent = '请输入开放时间'; return; }
  if (openStart >= openEnd) { errEl.textContent = '开放起始必须早于结束'; return; }

  const body = {
    name: name,
    code: code,
    open_start: openStart + ':00',
    open_end: openEnd + ':00',
    attributes: collectAttrs(),
    is_active: document.getElementById('rfIsActive').value === 'true',
  };

  errEl.textContent = '';
  try {
    if (editingResourceId) {
      await apiFetch(
        '/api/scenarios/' + adminCurrentScenario.id + '/resources/' + editingResourceId,
        { method: 'PUT', body: body }
      );
    } else {
      await apiFetch(
        '/api/scenarios/' + adminCurrentScenario.id + '/resources',
        { method: 'POST', body: body }
      );
    }
    resourceModal.style.display = 'none';
    await loadAdminResources();
    showResult({ type: 'success', title: '保存成功', desc: '资源「' + code + '」已保存。' });
  } catch (e) {
    errEl.textContent = e.message || '保存失败';
  }
}
document.getElementById('btnResourceSave').addEventListener('click', saveResource);

async function deleteAdminResource(r) {
  if (!confirm('确认删除资源「' + r.code + ' ' + r.name + '」？\n相关预约将一并删除，此操作不可恢复。')) return;
  try {
    await apiFetch(
      '/api/scenarios/' + adminCurrentScenario.id + '/resources/' + r.id,
      { method: 'DELETE' }
    );
    await loadAdminResources();
    showResult({ type: 'success', title: '已删除', desc: '资源「' + r.code + '」已删除。' });
  } catch (e) {
    showResult({ type: 'fail', title: '删除失败', desc: e.message || '请稍后重试' });
  }
}

/* ---------- 17.5 可预约状态查询（对接 /availability，与 Agent 同源） ---------- */
async function queryAdminAvailability() {
  if (!adminCurrentScenario) return;
  const date = document.getElementById('adminAvailDate').value;
  const hint = document.getElementById('adminAvailHint');
  const result = document.getElementById('adminAvailResult');
  result.innerHTML = '';
  if (!date) {
    hint.textContent = '请先选择查询日期';
    return;
  }
  hint.textContent = '查询中…';
  try {
    const data = await apiFetch(
      '/api/scenarios/' + adminCurrentScenario.id + '/availability?date=' + date
    );
    renderAdminAvailability(data, date);
    hint.textContent = '已加载 ' + (data.resources || []).length + ' 个资源在 ' + date + ' 的可预约状态';
  } catch (e) {
    hint.textContent = '查询失败';
    showResult({ type: 'fail', title: '查询失败', desc: e.message || '请稍后重试' });
  }
}

function renderAdminAvailability(data, date) {
  const wrap = document.getElementById('adminAvailResult');
  wrap.innerHTML = '';

  const summary = document.createElement('div');
  summary.className = 'admin-avail-summary';
  summary.textContent = '📅 ' + date + ' · 共 ' + (data.resources || []).length + ' 个资源 · 合计 ' + (data.free_slots_count || 0) + ' 个空闲时段';
  wrap.appendChild(summary);

  (data.resources || []).forEach(function (r) {
    const card = document.createElement('div');
    card.className = 'admin-avail-resource';

    const head = document.createElement('div');
    head.className = 'ar-head';
    head.innerHTML =
      '<span class="ar-code">' + esc(r.code) + '</span>' +
      '<span class="ar-name">' + esc(r.name) + '</span>' +
      '<span class="badge-status ' + (r.is_active ? 'badge-on' : 'badge-off') + '">' + (r.is_active ? '启用' : '停用') + '</span>';
    card.appendChild(head);

    const slots = document.createElement('div');
    slots.className = 'admin-avail-slots';
    const free = r.free_slots || [];
    if (free.length === 0) {
      const none = document.createElement('span');
      none.className = 'avail-slot none';
      none.textContent = '当天无空闲时段';
      slots.appendChild(none);
    } else {
      /* 合并连续时段便于阅读 */
      const merged = mergeSlots(free);
      merged.forEach(function (m) {
        const tag = document.createElement('span');
        tag.className = 'avail-slot';
        tag.textContent = m.start + '-' + m.end;
        slots.appendChild(tag);
      });
    }
    card.appendChild(slots);
    wrap.appendChild(card);
  });
}

function mergeSlots(freeSlots) {
  if (!freeSlots || freeSlots.length === 0) return [];
  const sorted = freeSlots.slice().sort(function (a, b) {
    return a.start < b.start ? -1 : (a.start > b.start ? 1 : 0);
  });
  const out = [];
  let start = sorted[0].start;
  let prevEnd = sorted[0].end;
  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i].start === prevEnd) {
      prevEnd = sorted[i].end;
    } else {
      out.push({ start: start, end: prevEnd });
      start = sorted[i].start;
      prevEnd = sorted[i].end;
    }
  }
  out.push({ start: start, end: prevEnd });
  return out;
}

document.getElementById('btnQueryAvail').addEventListener('click', queryAdminAvailability);

/* ---------- 17.6 AI 批量生成资源（对接 /resources/generate） ---------- */
async function aiGenerateResources() {
  if (!adminCurrentScenario) return;
  const input = document.getElementById('adminGenInput');
  const hint = document.getElementById('adminGenHint');
  const desc = input.value.trim();
  if (!desc) { hint.textContent = '请先输入资源描述'; return; }
  hint.textContent = 'AI 生成中…';
  try {
    const data = await apiFetch(
      '/api/scenarios/' + adminCurrentScenario.id + '/resources/generate',
      { method: 'POST', body: { description: desc } }
    );
    input.value = '';
    const cnt = data.count || 0;
    hint.textContent = cnt ? '已生成 ' + cnt + ' 个资源' : '未生成新资源（编号可能已存在）';
    await loadAdminResources();
    showResult({
      type: 'success',
      title: '生成成功',
      desc: 'AI 已根据「' + desc + '」生成 ' + cnt + ' 个资源，可在下方列表查看或编辑。',
    });
  } catch (e) {
    hint.textContent = '生成失败';
    showResult({ type: 'fail', title: '生成失败', desc: e.message || '请稍后重试' });
  }
}
document.getElementById('btnAiGenerate').addEventListener('click', aiGenerateResources);
