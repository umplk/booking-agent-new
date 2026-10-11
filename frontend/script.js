/* ============================================================
 * 校园图书馆自习室座位预约 - 交互逻辑
 * 原生 JS，无框架；数据为前端模拟，无后端依赖
 * ============================================================ */

/* ---------- 0. 单页视图切换 ---------- */
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
  if (name === 'mine') renderReservations();
  if (name === 'profile') renderProfile();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

navLinks.forEach(function (a) {
  a.addEventListener('click', function (e) {
    e.preventDefault();
    switchView(a.dataset.view, a);
  });
});

/* 导航栏用户区点击 -> 个人中心 */
document.getElementById('navUser').addEventListener('click', function () {
  const link = document.querySelector('.nav-menu a[data-view="profile"]');
  switchView('profile', link);
});

/* ---------- 1. 登录弹窗 ---------- */
const loginModal = document.getElementById('loginModal');
const prefModal = document.getElementById('prefModal');
let currentUser = null;

document.getElementById('btnLogin').addEventListener('click', function () {
  const name = document.getElementById('loginName').value.trim();
  const sid = document.getElementById('loginId').value.trim();
  const errEl = document.getElementById('loginError');

  if (!name) {
    errEl.textContent = '请输入姓名';
    document.getElementById('loginName').focus();
    return;
  }
  if (!sid) {
    errEl.textContent = '请输入学号';
    document.getElementById('loginId').focus();
    return;
  }
  if (!/^\d{6,12}$/.test(sid)) {
    errEl.textContent = '学号应为 6-12 位数字';
    return;
  }

  errEl.textContent = '';
  currentUser = { name: name, sid: sid };
  document.getElementById('navUserName').textContent = name + ' 同学';
  document.getElementById('navAvatar').textContent = name.charAt(0);

  loginModal.style.display = 'none';
  prefModal.style.display = 'flex';
});

// 回车键登录
['loginName', 'loginId'].forEach(function (id) {
  document.getElementById(id).addEventListener('keydown', function (e) {
    if (e.key === 'Enter') document.getElementById('btnLogin').click();
  });
});

/* ---------- 2. 楼层配置 ----------
 * 一楼到五楼分别为不同阅览区，每楼独立座位数据。
 */
const FLOORS = [
  {
    id: 1, name: '1F', icon: '📖', area: '文学阅览区',
    desc: '中外文学名著 · 散文诗歌 · 适合静心阅读',
    occupied: ['A1', 'A5', 'B3', 'B8', 'C2', 'C7', 'D4', 'D9', 'E3', 'E6'],
    allPower: false,
  },
  {
    id: 2, name: '2F', icon: '🔬', area: '理工科阅览区',
    desc: '数理化 · 工程技术 · 计算机科学文献',
    occupied: ['A2', 'A6', 'B1', 'B7', 'C4', 'C9', 'D2', 'D8', 'E5', 'E9'],
    allPower: true,
  },
  {
    id: 3, name: '3F', icon: '🌍', area: '外文阅览区',
    desc: '英日韩文原版书 · 进口期刊 · 语言学习专区',
    occupied: ['A3', 'A8', 'B4', 'B9', 'C1', 'C6', 'D3', 'D7', 'E2', 'E8'],
    allPower: false,
  },
  {
    id: 4, name: '4F', icon: '🏛️', area: '人文社会学科图书阅览区',
    desc: '历史哲学 · 政治经济 · 社会学法学',
    occupied: ['A4', 'A9', 'B2', 'B6', 'C5', 'C8', 'D5', 'D1', 'E1', 'E7'],
    allPower: false,
  },
  {
    id: 5, name: '5F', icon: '💻', area: '电子文献阅览区',
    desc: '电子数据库 · 在线检索 · 每座配备电源与网口',
    occupied: ['A1', 'A7', 'B5', 'C3', 'C8', 'D6', 'E4'],
    allPower: true,
  },
];

const ROWS = ['A', 'B', 'C', 'D', 'E'];
const COLS = 10;

/* 为指定楼层生成座位数据 */
function buildSeats(floor) {
  const occ = new Set(floor.occupied);
  const arr = [];
  ROWS.forEach(function (r, ri) {
    for (let c = 1; c <= COLS; c++) {
      const id = r + c;
      arr.push({
        id: id,
        row: r,
        col: c,
        baseOccupied: occ.has(id),
        window: ri === 0,
        power: floor.allPower || c % 2 === 0,
        quiet: ri <= 1,
        group: ri === ROWS.length - 1,
        corner: c === 1 || c === COLS,
      });
    }
  });
  return arr;
}

const floorSeats = {};
FLOORS.forEach(function (f) { floorSeats[f.id] = buildSeats(f); });

let currentFloorId = 1;
let seats = floorSeats[currentFloorId];

/* ---------- 2b. 预约日期选择 ---------- */
let currentDate = '';
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

dateInput.addEventListener('change', function () {
  currentDate = dateInput.value;
  if (currentDate) {
    dateHint.textContent = '已选 ' + currentDate + '，现在可以选择座位';
    dateHint.classList.add('ready');
    roomLock.classList.add('hidden');
  } else {
    dateHint.textContent = '请先选择预约日期，再选择座位';
    dateHint.classList.remove('ready');
    roomLock.classList.remove('hidden');
  }
  selectedId = null;
  document.getElementById('btnConfirm').disabled = true;
  selTip.style.display = 'none';
  renderSeats();
  applyRecommend();
});

/* 判断某座位在当前日期是否被占用（基础占用 + 我的预约） */
function seatTaken(s, floorId, date) {
  if (s.baseOccupied) return true;
  var fid = floorId !== undefined ? floorId : currentFloorId;
  var dt = date || currentDate;
  if (!dt) return false;
  return myReservations.some(function (r) {
    return r.floorId === fid && r.id === s.id && r.date === dt && r.status === 'valid';
  });
}

/* ---------- 3. 楼层切换栏渲染 ---------- */
const floorTabsEl = document.getElementById('floorTabs');
const pageTitleEl = document.getElementById('pageTitle');
const pageSubEl = document.getElementById('pageSub');

function renderFloorTabs() {
  floorTabsEl.innerHTML = '';
  FLOORS.forEach(function (f) {
    const tab = document.createElement('div');
    tab.className = 'floor-tab' + (f.id === currentFloorId ? ' active' : '');
    tab.innerHTML =
      '<span class="ft-icon">' + f.icon + '</span>' +
      '<span class="ft-name">' + f.name + '</span>' +
      '<span class="ft-area">' + f.area + '</span>';
    tab.addEventListener('click', function () { switchFloor(f.id); });
    floorTabsEl.appendChild(tab);
  });
}

function currentFloor() {
  return FLOORS.find(function (f) { return f.id === currentFloorId; });
}

function switchFloor(id) {
  if (id === currentFloorId) return;
  currentFloorId = id;
  seats = floorSeats[id];
  selectedId = null;
  recommendIds.clear();
  recommendData = {};
  document.getElementById('btnConfirm').disabled = true;
  selTip.style.display = 'none';
  updatePageHead();
  renderFloorTabs();
  renderSeats();
  renderRecommendPanel();
}

function updatePageHead() {
  const f = currentFloor();
  pageTitleEl.textContent = 'A栋 · ' + f.name + ' · ' + f.area;
  pageSubEl.textContent = '开放时间 08:00 - 22:00 · ' + f.desc + ' · 预约后15分钟内入座';
}

/* ---------- 4. 渲染座位网格 ---------- */
const roomMap = document.getElementById('roomMap');

function renderSeats() {
  roomMap.innerHTML = '';
  ROWS.forEach(function (r) {
    const rowEl = document.createElement('div');
    rowEl.className = 'row';

    const label = document.createElement('div');
    label.className = 'row-label';
    label.textContent = r + '排';
    rowEl.appendChild(label);

    const seatsWrap = document.createElement('div');
    seatsWrap.className = 'seats';

    for (let c = 1; c <= COLS; c++) {
      const id = r + c;
      const s = seats.find(function (x) { return x.id === id; });
      const taken = seatTaken(s);

      const el = document.createElement('div');
      el.className = 'seat';
      el.dataset.id = id;
      el.classList.add(taken ? 'occupied' : 'free');
      if (s.power) el.classList.add('has-power');

      // 属性小图标（靠窗/电源）
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
      num.textContent = id;
      el.appendChild(num);

      const tag = document.createElement('div');
      tag.className = 'tag';
      tag.textContent = s.group ? '讨论' : (s.quiet ? '安静' : '');
      el.appendChild(tag);

      el.addEventListener('click', function () { onSeatClick(id, el); });
      seatsWrap.appendChild(el);

      if (c === 5) {
        const aisle = document.createElement('div');
        aisle.className = 'aisle';
        seatsWrap.appendChild(aisle);
      }
    }
    rowEl.appendChild(seatsWrap);
    roomMap.appendChild(rowEl);
  });
  updateStat();
  applyRecommend();
}

/* ---------- 5. 座位点击：选中 / 取消 ---------- */
let selectedId = null;

function onSeatClick(id, el) {
  if (!currentDate) return;
  const s = seats.find(function (x) { return x.id === id; });
  if (seatTaken(s)) return;

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

/* ---------- 6. 智能推荐（含匹配度） ---------- */
let recommendIds = new Set();
let recommendData = {}; // id -> { score, total, percent, matched:[] }
let currentPrefLabels = [];

const PREF_LABELS = {
  quiet: '安静', window: '靠窗', power: '有电源', corner: '角落', group: '讨论',
};

function recommend(prefs, major) {
  recommendIds.clear();
  recommendData = {};

  // 专业 -> 默认偏好补充
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

  // 记算预期条件标签（用于面板展示）
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

  // 给每个空闲座位打分
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

/* 应用推荐高亮到 DOM */
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

/* 渲染推荐结果面板 */
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

/* ---------- 7. 统计 & 提示 ---------- */
function updateStat() {
  const free = seats.filter(function (s) { return !seatTaken(s); }).length;
  document.getElementById('statFree').textContent = free;
  document.getElementById('statOcc').textContent = seats.length - free;
  document.getElementById('statRec').textContent = recommendIds.size;
}

const selTip = document.getElementById('selTip');
function updateTip() {
  if (selectedId) {
    selTip.textContent = '已选中座位：' + currentFloor().name + ' · ' + selectedId + '（' + currentDate + '）';
    selTip.style.display = 'block';
  } else {
    selTip.style.display = 'none';
  }
}

/* ---------- 8. 偏好弹窗交互 ---------- */
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

/* ---------- 9. 我的预约数据与渲染 ---------- */
let myReservations = [];
let historyRecords = [];

function seatAreaText(s) {
  if (s.group) return '讨论区';
  if (s.quiet) return '安静区';
  if (s.window) return '靠窗区';
  return '普通区';
}

function nowText() {
  const d = new Date();
  const pad = function (n) { return n < 10 ? '0' + n : '' + n; };
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) +
    ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
}

function nowTextFull() {
  const d = new Date();
  const pad = function (n) { return n < 10 ? '0' + n : '' + n; };
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) +
    ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
}

function renderReservations() {
  const listEl = document.getElementById('reservationList');
  const emptyEl = document.getElementById('reservationEmpty');
  const countEl = document.getElementById('resCount');
  listEl.innerHTML = '';

  var validList = myReservations.filter(function (r) { return r.status === 'valid'; });
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
    seat.innerHTML = '<span class="rs-floor">' + res.floorName + '</span><span class="rs-id">' + res.id + '</span>';
    card.appendChild(seat);

    const info = document.createElement('div');
    info.className = 'res-info';

    const top = document.createElement('div');
    top.className = 'res-top';
    const name = document.createElement('span');
    name.className = 'res-name';
    name.textContent = res.area + ' · 座位 ' + res.id;
    const badge = document.createElement('span');
    badge.className = 'res-badge valid';
    badge.textContent = '有效';
    top.appendChild(name);
    top.appendChild(badge);

    const meta = document.createElement('div');
    meta.className = 'res-meta';
    meta.textContent = '预约日期：' + res.date + ' · 预约时间：' + res.time + ' · 请15分钟内入座';

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

function cancelReservation(res) {
  res.status = 'cancelled';
  res.cancelTime = nowTextFull();
  historyRecords.unshift({
    type: 'cancel',
    seatId: res.id,
    floorName: res.floorName,
    area: res.area,
    date: res.date,
    opTime: res.cancelTime,
  });
  if (res.floorId === currentFloorId) {
    renderSeats();
    applyRecommend();
  }
  renderReservations();
}

document.getElementById('btnGoReserve').addEventListener('click', function () {
  const link = document.querySelector('.nav-menu a[data-view="reserve"]');
  switchView('reserve', link);
});

/* ---------- 10. 个人中心渲染 ---------- */
function renderProfile() {
  if (!currentUser) return;

  document.getElementById('profileAvatar').textContent = currentUser.name.charAt(0);
  document.getElementById('profileName').textContent = currentUser.name;
  document.getElementById('profileSid').textContent = currentUser.sid;

  var total = historyRecords.filter(function (h) { return h.type === 'reserve'; }).length;
  var valid = myReservations.filter(function (r) { return r.status === 'valid'; }).length;
  var cancelled = historyRecords.filter(function (h) { return h.type === 'cancel'; }).length;

  document.getElementById('statTotal').textContent = total;
  document.getElementById('statValid').textContent = valid;
  document.getElementById('statCancel').textContent = cancelled;

  var listEl = document.getElementById('historyList');
  var emptyEl = document.getElementById('historyEmpty');
  listEl.innerHTML = '';

  if (historyRecords.length === 0) {
    emptyEl.classList.remove('hidden');
    return;
  }
  emptyEl.classList.add('hidden');

  historyRecords.forEach(function (h) {
    var item = document.createElement('div');
    item.className = 'history-item';

    var icon = document.createElement('div');
    icon.className = 'hi-icon ' + h.type;
    icon.textContent = h.type === 'reserve' ? '✅' : '❌';

    var body = document.createElement('div');
    body.className = 'hi-body';

    var title = document.createElement('div');
    title.className = 'hi-title';
    if (h.type === 'reserve') {
      title.innerHTML = '预约座位 <span class="hi-seat">' + h.floorName + ' · ' + h.seatId + '</span>';
    } else {
      title.innerHTML = '取消预约 <span class="hi-cancel">' + h.floorName + ' · ' + h.seatId + '</span>';
    }

    var meta = document.createElement('div');
    meta.className = 'hi-meta';
    meta.innerHTML = '区域：<b>' + h.area + '</b> · 预约日期：<b>' + h.date + '</b><br>操作时间：<b>' + h.opTime + '</b>';

    body.appendChild(title);
    body.appendChild(meta);
    item.appendChild(icon);
    item.appendChild(body);
    listEl.appendChild(item);
  });
}

/* ---------- 11. 预约结果弹窗 ---------- */
const resultModal = document.getElementById('resultModal');
const resultIcon = document.getElementById('resultIcon');
const resultTitle = document.getElementById('resultTitle');
const resultDesc = document.getElementById('resultDesc');
const resultDetail = document.getElementById('resultDetail');

function showResult(opt) {
  resultIcon.className = 'result-icon ' + opt.type;
  resultIcon.textContent = opt.type === 'success' ? '✅' : '⚠️';
  resultTitle.textContent = opt.title;
  resultDesc.textContent = opt.desc;

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

/* ---------- 12. 确认预约 ---------- */
document.getElementById('btnConfirm').addEventListener('click', function () {
  if (!selectedId) return;
  if (!currentDate) {
    showResult({
      type: 'fail',
      title: '请先选择日期',
      desc: '预约前请先在顶部选择预约日期。',
      actionText: '知道了',
    });
    return;
  }

  const s = seats.find(function (x) { return x.id === selectedId; });
  if (!s) return;

  const f = currentFloor();

  if (seatTaken(s)) {
    showResult({
      type: 'fail',
      title: '预约失败',
      desc: '该座位在此日期已被预约，请重新选择。',
      detail: [
        { k: '所在楼层', v: f.name + ' · ' + f.area },
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

  const area = seatAreaText(s);
  const time = nowText();
  const opTime = nowTextFull();

  myReservations.unshift({
    id: selectedId,
    floorId: f.id,
    floorName: f.name,
    area: f.area,
    date: currentDate,
    time: time,
    status: 'valid',
  });

  historyRecords.unshift({
    type: 'reserve',
    seatId: selectedId,
    floorName: f.name,
    area: f.area,
    date: currentDate,
    opTime: opTime,
  });

  const bookedId = selectedId;
  const bookedDate = currentDate;
  selectedId = null;
  document.getElementById('btnConfirm').disabled = true;
  selTip.style.display = 'none';
  renderSeats();
  renderReservations();

  showResult({
    type: 'success',
    title: '预约成功！',
    desc: '请在 15 分钟内入座，逾期将自动释放。',
    detail: [
      { k: '预约人', v: currentUser ? currentUser.name + '（' + currentUser.sid + '）' : '—' },
      { k: '所在楼层', v: f.name + ' · ' + f.area },
      { k: '座位编号', v: bookedId },
      { k: '座位区域', v: area },
      { k: '预约日期', v: bookedDate },
      { k: '预约时间', v: time },
    ],
    closeText: '查看我的预约',
    onClose: function () {
      const link = document.querySelector('.nav-menu a[data-view="mine"]');
      switchView('mine', link);
    },
    actionText: '继续预约',
  });
});

/* ---------- 13. 初始化 ---------- */
updatePageHead();
renderFloorTabs();
renderSeats();
renderReservations();
// 进入页面即弹出登录弹窗（登录成功后再弹偏好弹窗）
loginModal.style.display = 'flex';