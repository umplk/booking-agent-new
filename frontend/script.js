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

  loginModal.style.display = 'none';
  registerModal.style.display = 'none';

  await loadRooms();
  prefModal.style.display = 'flex';
}

/* ---------- 3. 自习室（楼层）数据 ---------- */
let rooms = [];          // 后端返回的 room 列表
let currentRoomId = null;
let seats = [];          // 当前楼层的座位（前端结构）
let currentDate = '';

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

function currentRoom() {
  return rooms.find(function (r) { return r.id === currentRoomId; });
}

async function loadRooms() {
  try {
    const data = await apiFetch('/api/rooms?page=1&page_size=100');
    rooms = data.items || [];
  } catch (e) {
    rooms = [];
    showResult({
      type: 'fail',
      title: '加载自习室失败',
      desc: e.message || '请检查后端服务',
    });
    return;
  }
  if (rooms.length === 0) {
    showResult({
      type: 'fail',
      title: '暂无自习室',
      desc: '后端尚未配置任何自习室，请联系管理员添加。',
    });
    return;
  }
  currentRoomId = rooms[0].id;
  await loadSeats();
  renderFloorTabs();
  updatePageHead();
  renderSeats();
}

/* 加载当前楼层的座位基础数据 */
async function loadSeats() {
  try {
    const data = await apiFetch('/api/rooms/' + currentRoomId);
    seats = (data.seats || []).map(function (s) {
      const num = s.seat_number;
      return {
        seatId: s.id,
        id: num,
        row: num.charAt(0),
        col: parseInt(num.slice(1), 10) || 0,
        is_available: s.is_available,
        window: s.window,
        power: s.power,
        quiet: s.quiet,
        group: s.is_group,
        corner: s.corner,
        booked: false,
      };
    });
  } catch (e) {
    seats = [];
  }
}

/* ---------- 4. 楼层切换栏渲染 ---------- */
const floorTabsEl = document.getElementById('floorTabs');
const pageTitleEl = document.getElementById('pageTitle');
const pageSubEl = document.getElementById('pageSub');

function renderFloorTabs() {
  floorTabsEl.innerHTML = '';
  rooms.forEach(function (r) {
    const tab = document.createElement('div');
    tab.className = 'floor-tab' + (r.id === currentRoomId ? ' active' : '');
    tab.innerHTML =
      '<span class="ft-icon">' + roomIcon(r.name) + '</span>' +
      '<span class="ft-name">' + (r.location || r.name) + '</span>' +
      '<span class="ft-area">' + r.name + '</span>';
    tab.addEventListener('click', function () { switchFloor(r.id); });
    floorTabsEl.appendChild(tab);
  });
}

async function switchFloor(id) {
  if (id === currentRoomId) return;
  currentRoomId = id;
  selectedId = null;
  recommendIds.clear();
  recommendData = {};
  document.getElementById('btnConfirm').disabled = true;
  selTip.style.display = 'none';
  updatePageHead();
  renderFloorTabs();
  await loadSeats();
  if (currentDate) await loadAvailability();
  renderSeats();
  renderRecommendPanel();
}

function updatePageHead() {
  const r = currentRoom();
  if (!r) return;
  pageTitleEl.textContent = (r.location || 'A栋') + ' · ' + r.name;
  pageSubEl.textContent =
    '开放时间 ' + fmtTime(r.open_time) + ' - ' + fmtTime(r.close_time) +
    ' · 预约后15分钟内入座';
}

/* ---------- 5. 预约日期选择 ---------- */
const dateInput = document.getElementById('reserveDate');
const dateHint = document.getElementById('dateHint');
const roomLock = document.getElementById('roomLock');

function todayStr() {
  const d = new Date();
  const pad = function (n) { return n < 10 ? '0' + n : '' + n; };
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
}

dateInput.min = todayStr();
dateInput.value = '';

dateInput.addEventListener('change', async function () {
  currentDate = dateInput.value;
  if (currentDate) {
    dateHint.textContent = '已选 ' + currentDate + '，现在可以选择座位';
    dateHint.classList.add('ready');
    roomLock.classList.add('hidden');
    await loadAvailability();
  } else {
    dateHint.textContent = '请先选择预约日期，再选择座位';
    dateHint.classList.remove('ready');
    roomLock.classList.remove('hidden');
    seats.forEach(function (s) { s.booked = false; });
  }
  selectedId = null;
  document.getElementById('btnConfirm').disabled = true;
  selTip.style.display = 'none';
  renderSeats();
  applyRecommend();
});

/* 查询当前楼层在当前日期的座位占用情况 */
async function loadAvailability() {
  if (!currentRoomId || !currentDate) return;
  try {
    const data = await apiFetch(
      '/api/rooms/' + currentRoomId + '/availability?date=' + currentDate
    );
    const bookedMap = {};
    (data.seats || []).forEach(function (s) {
      bookedMap[s.seat_id] = (s.booked_slots && s.booked_slots.length > 0);
    });
    seats.forEach(function (s) {
      s.booked = !!bookedMap[s.seatId];
    });
  } catch (e) {
    /* 查询失败时保持原状 */
  }
}

/* 判断座位是否被占用 */
function seatTaken(s) {
  return !s.is_available || s.booked;
}

/* ---------- 6. 渲染座位网格 ---------- */
const roomMap = document.getElementById('roomMap');

function renderSeats() {
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

/* ---------- 7. 座位点击：选中 / 取消 ---------- */
let selectedId = null;

function onSeatClick(id, el) {
  if (!currentDate) return;
  const s = seats.find(function (x) { return x.id === id; });
  if (!s || seatTaken(s)) return;

  document.querySelectorAll('.seat.selected').forEach(function (e) {
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
  document.querySelectorAll('.seat.recommend').forEach(function (e) {
    e.classList.remove('recommend');
    e.removeAttribute('data-match');
  });
  recommendIds.forEach(function (id) {
    const el = document.querySelector('.seat[data-id="' + id + '"]');
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
    const r = currentRoom();
    selTip.textContent = '已选中座位：' + (r ? r.name : '') + ' · ' + selectedId + '（' + currentDate + '）';
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

    const seat = document.createElement('div');
    seat.className = 'res-seat';
    seat.innerHTML =
      '<span class="rs-floor">' + (res.room_name || '') + '</span>' +
      '<span class="rs-id">' + (res.seat_number || '') + '</span>';
    card.appendChild(seat);

    const info = document.createElement('div');
    info.className = 'res-info';

    const top = document.createElement('div');
    top.className = 'res-top';
    const name = document.createElement('span');
    name.className = 'res-name';
    name.textContent = (res.room_name || '') + ' · 座位 ' + (res.seat_number || '');
    const badge = document.createElement('span');
    badge.className = 'res-badge valid';
    badge.textContent = '有效';
    top.appendChild(name);
    top.appendChild(badge);

    const meta = document.createElement('div');
    meta.className = 'res-meta';
    meta.textContent =
      '预约日期：' + res.reservation_date +
      ' · 时段：' + fmtTime(res.start_time) + '-' + fmtTime(res.end_time) +
      ' · 请15分钟内入座';

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
        { k: '自习室', v: res.room_name || '' },
        { k: '座位编号', v: res.seat_number || '' },
        { k: '预约日期', v: res.reservation_date },
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
    const seatLabel = (r.room_name || '') + ' · ' + (r.seat_number || '');
    if (isCancel) {
      title.innerHTML = '取消预约 <span class="hi-cancel">' + seatLabel + '</span>';
    } else {
      title.innerHTML = '预约座位 <span class="hi-seat">' + seatLabel + '</span>';
    }

    const meta = document.createElement('div');
    meta.className = 'hi-meta';
    meta.innerHTML =
      '预约日期：<b>' + r.reservation_date + '</b> · 时段：<b>' +
      fmtTime(r.start_time) + '-' + fmtTime(r.end_time) + '</b><br>' +
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
    showResult({ type: 'fail', title: '请先选择日期', desc: '预约前请先在顶部选择预约日期。', actionText: '知道了' });
    return;
  }

  const s = seats.find(function (x) { return x.id === selectedId; });
  if (!s) return;
  const r = currentRoom();
  if (!r) return;

  if (seatTaken(s)) {
    showResult({
      type: 'fail',
      title: '预约失败',
      desc: '该座位在此日期已被预约，请重新选择。',
      detail: [
        { k: '所在楼层', v: r.name },
        { k: '座位编号', v: selectedId },
        { k: '预约日期', v: currentDate },
        { k: '失败原因', v: '座位已被占用' },
      ],
      actionText: '重新选择',
    });
    selectedId = null;
    document.getElementById('btnConfirm').disabled = true;
    selTip.style.display = 'none';
    return;
  }

  const startTime = fmtTime(r.open_time) + ':00';
  const endTime = fmtTime(r.close_time) + ':00';

  try {
    const data = await apiFetch('/api/reservations', {
      method: 'POST',
      body: {
        seat_id: s.seatId,
        room_id: currentRoomId,
        reservation_date: currentDate,
        start_time: startTime,
        end_time: endTime,
        status: 'confirmed',
      },
    });

    const bookedId = selectedId;
    const bookedDate = currentDate;
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
      desc: '请在 15 分钟内入座，逾期将自动释放。',
      detail: [
        { k: '预约人', v: currentUser ? (currentUser.name || currentUser.username) : '—' },
        { k: '所在楼层', v: r.name },
        { k: '座位编号', v: bookedId },
        { k: '座位区域', v: seatAreaText(s) },
        { k: '预约日期', v: bookedDate },
        { k: '预约时段', v: fmtTime(r.open_time) + ' - ' + fmtTime(r.close_time) },
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
        { k: '所在楼层', v: r.name },
        { k: '座位编号', v: selectedId },
        { k: '预约日期', v: currentDate },
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
      await loadRooms();
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
const AGENT_API = '/api/agent/chat';   // 后端 agent 对话接口（待实现）
const AGENT_DEMO = true;               // 演示模式：后端未就绪时用本地模拟回复

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
    } else {
      const data = await apiFetch(AGENT_API, {
        method: 'POST',
        body: { message: text },
      });
      reply = (data && (data.reply || data.message)) || '（接口未返回有效内容）';
    }
  } catch (e) {
    reply = '⚠️ 暂时无法连接智能体服务：' + (e.message || '未知错误') +
      '\n\n这是一次前端演示回复。后端 agent 接口就绪后，将 `AGENT_DEMO` 置为 `false` 即可切换到真实对话。';
  }

  thinking.textContent = reply;
  agentStatus.textContent = '在线 · 帮你选座、查预约';
  agentSend.disabled = false;
}

agentSend.addEventListener('click', sendMessage);
agentInput.addEventListener('keydown', function (e) {
  if (e.key === 'Enter') sendMessage();
});

/* ---------- 16.4 演示模式本地回复（后端未接入时的占位） ---------- */
function demoReply(text) {
  const t = text || '';
  const room = currentRoom();
  if (t.indexOf('座位') >= 0 || t.indexOf('推荐') >= 0 || t.indexOf('选座') >= 0) {
    const freeList = seats.filter(function (s) { return !seatTaken(s); }).slice(0, 5);
    if (freeList.length) {
      return '为你找到以下空闲座位：\n' +
        freeList.map(function (s) {
          return '· ' + (room ? room.name : '') + ' ' + s.id +
            (s.window ? ' 🪟靠窗' : '') +
            (s.power ? ' 🔌电源' : '') +
            (s.quiet ? ' 安静区' : '') +
            (s.group ? ' 讨论区' : '');
        }).join('\n') +
        '\n\n点击座位图上的座位即可选中预约。';
    }
    return '当前楼层暂时没有空闲座位，可以切换其他楼层看看～';
  }
  if (t.indexOf('预约') >= 0 && t.indexOf('怎么') >= 0) {
    return '预约步骤很简单：\n① 顶部选择预约日期\n② 选择楼层\n③ 点击空闲座位（或让我推荐）\n④ 点击「确认预约」\n\n预约后请在 15 分钟内入座哦～';
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
