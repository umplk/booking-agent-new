<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import { apiFetch } from '../../api/request.js';
import { showResult } from '../../composables/useResult.js';
import { useAuth } from '../../composables/useAuth.js';
import { fmtTime, todayStr, mergeSlots } from '../../composables/useUtils.js';

const router = useRouter();
const auth = useAuth();

const bookingScenarios = ref([]);
const currentScenario = ref(null);
const floors = ref([]);
const currentFloorIdx = ref(0);
const seats = ref([]);
const currentDate = ref('');
const currentTimeStart = ref('08:00');
const currentTimeEnd = ref('10:00');
const selectedId = ref(null);
const recommendData = ref({});
const currentPrefLabels = ref([]);
const bookingHint = ref('请先选择预约日期与时段，再选择资源');
const hintReady = ref(false);
const prefOpen = ref(false);
const major = ref('');
const selectedPrefs = ref(new Set());

const PREF_LABELS = { quiet: '安静', window: '靠窗', power: '有电源', corner: '角落', group: '讨论' };
const prefChips = [
  { key: 'quiet', label: '🤫 安静' },
  { key: 'window', label: '🪟 靠窗' },
  { key: 'power', label: '🔌 有电源' },
  { key: 'corner', label: '📐 角落' },
  { key: 'group', label: '👥 讨论区' },
];
const ICON_MAP = [
  { kw: '文学', icon: '📖' }, { kw: '理工', icon: '🔬' }, { kw: '外文', icon: '🌍' },
  { kw: '人文', icon: '🏛️' }, { kw: '电子', icon: '💻' },
];

function roomIcon(name) {
  for (const it of ICON_MAP) if (name.indexOf(it.kw) >= 0) return it.icon;
  return '📚';
}
const currentFloor = computed(() => floors.value[currentFloorIdx.value] || null);
const recommendIds = computed(() => Object.keys(recommendData.value));

function seatTaken(s) { return !s.is_available || s.booked; }
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

const statFree = computed(() => seats.value.filter(s => !seatTaken(s)).length);
const statOcc = computed(() => seats.value.length - statFree.value);
const statRec = computed(() => recommendIds.value.length);

const floorHasGrid = computed(() => {
  const f = currentFloor.value;
  return f && f.resources.some(r => { const a = r.attributes || {}; return a.row != null && a.col != null; });
});

const seatRows = computed(() => {
  const rowMap = {};
  seats.value.forEach(s => { rowMap[s.row] = rowMap[s.row] || []; rowMap[s.row].push(s); });
  return Object.keys(rowMap).sort().map(r => ({
    row: r,
    items: rowMap[r].slice().sort((a, b) => a.col - b.col),
  }));
});

const sortedCardSeats = computed(() => seats.value.slice().sort((a, b) => (a.code || a.id) < (b.code || b.id) ? -1 : 1));

const selTip = computed(() => {
  if (!selectedId.value) return '';
  const f = currentFloor.value;
  return '已选中：' + (f ? f.location + ' · ' : '') + selectedId.value + '（' + currentDate.value + ' ' + currentTimeStart.value + '-' + currentTimeEnd.value + '）';
});

function resetSelection() {
  selectedId.value = null;
  recommendData.value = {};
}

async function loadBookingScenarios() {
  try {
    const data = await apiFetch('/api/scenarios?page=1&page_size=100&include_inactive=false');
    bookingScenarios.value = data.items || [];
  } catch (e) {
    bookingScenarios.value = [];
    showResult({ type: 'fail', title: '加载场景失败', desc: e.message || '请检查后端服务' });
    return;
  }
  if (!bookingScenarios.value.length) {
    showResult({ type: 'fail', title: '暂无预约场景', desc: '请先在「预约场景」页创建场景。' });
    return;
  }
  currentScenario.value = bookingScenarios.value[0];
  await onScenarioReady();
}

async function onScenarioReady() {
  await loadResources();
}

async function loadResources() {
  if (!currentScenario.value) return;
  try {
    const data = await apiFetch('/api/scenarios/' + currentScenario.value.id + '/resources?page=1&page_size=500');
    const items = data.items || [];
    const groupMap = {}, order = [];
    items.forEach(r => {
      const loc = (r.attributes || {}).location || '全部资源';
      if (!groupMap[loc]) { groupMap[loc] = []; order.push(loc); }
      groupMap[loc].push(r);
    });
    floors.value = order.map(loc => {
      const res = groupMap[loc];
      return { location: loc, name: loc, resources: res, openStart: fmtTime(res[0].open_start), openEnd: fmtTime(res[0].open_end) };
    });
  } catch (e) {
    floors.value = [];
    showResult({ type: 'fail', title: '加载资源失败', desc: e.message || '请检查后端服务' });
    return;
  }
  currentFloorIdx.value = 0;
  buildSeatsFromFloor();
  syncTimeInputs();
}

function buildSeatsFromFloor() {
  const f = currentFloor.value;
  if (!f) { seats.value = []; return; }
  seats.value = f.resources.map(r => {
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

function syncTimeInputs() {
  if (!currentScenario.value) return;
  const step = currentScenario.value.time_step_minutes || 30;
  const f = currentFloor.value;
  timeStep.value = step * 60;
  if (f) { timeMin.value = f.openStart; timeMax.value = f.openEnd; }
}

const timeStep = ref(1800);
const timeMin = ref('');
const timeMax = ref('');

async function onScenarioChange() {
  const sel = scenarioSelect.value;
  if (!sel) return;
  currentScenario.value = bookingScenarios.value.find(s => s.id === parseInt(sel, 10));
  if (!currentScenario.value) return;
  resetSelection();
  await onScenarioReady();
  if (currentDate.value) await loadAvailability();
}

const scenarioSelect = ref('');

async function switchFloor(idx) {
  if (idx === currentFloorIdx.value) return;
  currentFloorIdx.value = idx;
  resetSelection();
  buildSeatsFromFloor();
  syncTimeInputs();
  if (currentDate.value) await loadAvailability();
}

async function onDateOrTimeChange() {
  if (currentDate.value && currentTimeStart.value && currentTimeEnd.value && currentTimeStart.value < currentTimeEnd.value) {
    bookingHint.value = '已选 ' + currentDate.value + ' ' + currentTimeStart.value + '-' + currentTimeEnd.value + '，现在可以选择资源';
    hintReady.value = true;
    await loadAvailability();
  } else {
    bookingHint.value = '请先选择预约日期与时段，再选择资源';
    hintReady.value = false;
    seats.value.forEach(s => s.booked = false);
  }
  resetSelection();
  applyRecommend();
}

async function loadAvailability() {
  if (!currentScenario.value || !currentDate.value) return;
  try {
    const data = await apiFetch('/api/scenarios/' + currentScenario.value.id + '/availability?date=' + currentDate.value);
    const freeMap = {};
    (data.resources || []).forEach(r => freeMap[r.resource_id] = r.free_slots || []);
    seats.value.forEach(s => {
      s.freeSlots = freeMap[s.resourceId] || [];
      s.booked = !isFreeInRange(s.freeSlots, currentTimeStart.value, currentTimeEnd.value);
    });
  } catch (e) {}
}

function onSeatClick(s) {
  if (!currentDate.value) return;
  if (seatTaken(s)) return;
  if (selectedId.value === s.id) { selectedId.value = null; }
  else { selectedId.value = s.id; }
}

function togglePref(key) {
  const ns = new Set(selectedPrefs.value);
  if (ns.has(key)) ns.delete(key); else ns.add(key);
  selectedPrefs.value = ns;
}

function runRecommend() {
  const prefs = Array.from(selectedPrefs.value);
  recommendData.value = {};
  const majorPref = { cs: ['power'], math: ['quiet'], literature: ['window'], art: ['window', 'corner'], science: ['power'] };
  const all = new Set(prefs);
  if (major.value && majorPref[major.value]) majorPref[major.value].forEach(p => all.add(p));
  currentPrefLabels.value = [];
  all.forEach(p => { if (PREF_LABELS[p]) currentPrefLabels.value.push(PREF_LABELS[p]); });
  const total = all.size;
  prefOpen.value = false;
  if (!total) { return; }
  const candidates = seats.value.filter(s => !seatTaken(s)).map(s => {
    let score = 0; const matched = [];
    all.forEach(p => { if (s[p]) { score++; if (PREF_LABELS[p]) matched.push(PREF_LABELS[p]); } });
    return { s, score, matched };
  }).sort((a, b) => b.score - a.score);
  const maxScore = candidates.length ? candidates[0].score : 0;
  const newData = {};
  if (maxScore > 0) {
    candidates.filter(x => x.score === maxScore).slice(0, 5).forEach(x => {
      newData[x.s.id] = { score: x.score, total, percent: Math.round(x.score / total * 100), matched: x.matched };
    });
  }
  recommendData.value = newData;
  if (Object.keys(newData).length) {
    const first = Object.keys(newData)[0];
    nextTick(() => {
      const el = document.querySelector('.seat[data-id="' + first + '"], .resource-card[data-id="' + first + '"]');
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  }
}

function applyRecommend() {}

function onRecommendClick(id) {
  const s = seats.value.find(x => x.id === id);
  if (s) onSeatClick(s);
  nextTick(() => {
    const el = document.querySelector('.seat[data-id="' + id + '"], .resource-card[data-id="' + id + '"]');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  });
}

async function confirmBooking() {
  if (!selectedId.value) return;
  if (!currentDate.value) return showResult({ type: 'fail', title: '请先选择日期', desc: '预约前请先选择预约日期与时段。' });
  if (!currentTimeStart.value || !currentTimeEnd.value || currentTimeStart.value >= currentTimeEnd.value)
    return showResult({ type: 'fail', title: '时段无效', desc: '请选择有效的开始与结束时间。' });
  const s = seats.value.find(x => x.id === selectedId.value);
  if (!s) return;
  const f = currentFloor.value;
  if (seatTaken(s)) {
    showResult({ type: 'fail', title: '预约失败', desc: '该资源在所选时段已被预约，请重新选择。' });
    resetSelection(); return;
  }
  const startIso = currentDate.value + 'T' + currentTimeStart.value + ':00';
  const endIso = currentDate.value + 'T' + currentTimeEnd.value + ':00';
  try {
    await apiFetch('/api/reservations', { method: 'POST', body: { scenario_id: currentScenario.value.id, resource_id: s.resourceId, start_time: startIso, end_time: endIso } });
    resetSelection();
    await loadAvailability();
    showResult({
      type: 'success', title: '预约成功！', desc: '请在预约时段内到达，逾期可能被系统取消。',
      detail: [
        { k: '预约人', v: auth.user ? (auth.user.name || auth.user.username) : '—' },
        { k: '预约场景', v: currentScenario.value.name },
        { k: '所在分组', v: f ? f.location : '' },
        { k: '资源编号', v: s.code || selectedId.value },
        { k: '预约日期', v: currentDate.value },
        { k: '预约时段', v: currentTimeStart.value + ' - ' + currentTimeEnd.value },
      ],
      closeText: '查看我的预约', onClose: () => router.push('/user/reservations'),
      actionText: '继续预约',
    });
  } catch (e) {
    showResult({ type: 'fail', title: '预约失败', desc: e.message || '请稍后重试' });
  }
}

onMounted(async () => {
  await loadBookingScenarios();
  if (bookingScenarios.value.length) {
    scenarioSelect.value = bookingScenarios.value[0].id;
  }
});
</script>

<template>
  <section class="page active">
    <div class="card filter-bar">
      <div class="filter-row">
        <div class="filter-field">
          <label>预约场景</label>
          <select class="form-input" v-model="scenarioSelect" @change="onScenarioChange">
            <option v-for="s in bookingScenarios" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </div>
        <div class="filter-field">
          <label>预约日期</label>
          <input type="date" class="form-input" :min="todayStr()" v-model="currentDate" @change="onDateOrTimeChange">
        </div>
        <div class="filter-field">
          <label>开始时间</label>
          <input type="time" class="form-input" v-model="currentTimeStart" :step="timeStep" :min="timeMin" :max="timeMax" value="08:00" @change="onDateOrTimeChange">
        </div>
        <div class="filter-field">
          <label>结束时间</label>
          <input type="time" class="form-input" v-model="currentTimeEnd" :step="timeStep" :min="timeMin" :max="timeMax" value="10:00" @change="onDateOrTimeChange">
        </div>
        <button class="btn btn-ghost" @click="prefOpen = true">🎯 智能推荐</button>
      </div>
      <div class="filter-hint" :class="{ ready: hintReady }">{{ bookingHint }}</div>
    </div>

    <div class="floor-tabs">
      <div class="floor-tab" :class="{ active: idx === currentFloorIdx }" v-for="(f, idx) in floors" :key="idx" @click="switchFloor(idx)">
        <span class="ft-icon">{{ roomIcon(f.name) }}</span><span class="ft-name">{{ f.location }}</span>
      </div>
    </div>

    <div class="booking-toolbar">
      <div class="legend">
        <span class="lg-item"><i class="lg-dot free"></i>空闲</span>
        <span class="lg-item"><i class="lg-dot occ"></i>已占用</span>
        <span class="lg-item"><i class="lg-dot sel"></i>已选中</span>
        <span class="lg-item"><i class="lg-dot rec"></i>智能推荐</span>
      </div>
      <div class="booking-stat">
        空闲 <b>{{ statFree }}</b> · 占用 <b>{{ statOcc }}</b> · 推荐 <b>{{ statRec }}</b>
      </div>
    </div>

    <div class="recommend-panel show" v-if="recommendIds.length">
      <div class="rp-head">🎯 为你推荐以下资源（按匹配度排序，点击可选中）</div>
      <div class="rp-cond" v-if="currentPrefLabels.length">预期条件：<b>{{ currentPrefLabels.join(' · ') }}</b></div>
      <div class="recommend-list">
        <div class="recommend-item" v-for="id in recommendIds" :key="id" @click="onRecommendClick(id)">
          <span class="ri-seat">{{ id }}</span>
          <div class="ri-bar-wrap"><div class="ri-bar" :style="{ width: recommendData[id].percent + '%' }"></div></div>
          <span class="ri-percent">{{ recommendData[id].percent }}%</span>
          <span class="ri-tags">{{ recommendData[id].matched.length ? recommendData[id].matched.join(' · ') : '无匹配' }}</span>
        </div>
      </div>
    </div>

    <div class="resource-area">
      <div class="room-map">
        <div class="empty-state" v-if="!seats.length"><span class="empty-icon">📦</span><p>该分组暂无资源</p></div>

        <template v-if="seats.length && floorHasGrid">
          <div class="row" v-for="r in seatRows" :key="r.row">
            <div class="row-label">{{ r.row }}排</div>
            <div class="seats">
              <template v-for="(s, idx) in r.items" :key="s.id">
                <div class="seat" :class="{ occupied: seatTaken(s), free: !seatTaken(s), selected: selectedId === s.id, recommend: recommendData[s.id] && selectedId !== s.id && !seatTaken(s), 'has-power': s.power }" :data-id="s.id" :data-match="recommendData[s.id] ? recommendData[s.id].percent + '%' : null" @click="onSeatClick(s)">
                  <div class="icons" v-if="s.window || s.power">{{ s.window ? '🪟' : '' }}{{ s.power ? '🔌' : '' }}</div>
                  <div class="num">{{ s.id }}</div>
                  <div class="tag">{{ s.group ? '讨论' : (s.quiet ? '安静' : '') }}</div>
                </div>
                <div class="aisle" v-if="idx === Math.floor(r.items.length / 2) - 1"></div>
              </template>
            </div>
          </div>
        </template>

        <div class="resource-card-grid" v-if="seats.length && !floorHasGrid">
          <div class="resource-card" :class="{ occupied: seatTaken(s), free: !seatTaken(s), selected: selectedId === s.id, recommend: recommendData[s.id] && selectedId !== s.id && !seatTaken(s) }" :data-id="s.id" :data-match="recommendData[s.id] ? recommendData[s.id].percent + '%' : null" v-for="s in sortedCardSeats" :key="s.id" @click="onSeatClick(s)">
            <div class="rc-head"><span class="rc-code">{{ s.code || s.id }}</span><span class="rc-name">{{ s.id }}</span><span class="badge" :class="seatTaken(s) ? 'badge-danger' : 'badge-success'">{{ seatTaken(s) ? '占用' : '空闲' }}</span></div>
            <div class="rc-meta">开放 {{ s.openStart }}-{{ s.openEnd }}</div>
            <div class="rc-chips">
              <span class="attr-chip bool-true" v-if="s.window">🪟靠窗</span>
              <span class="attr-chip bool-true" v-if="s.power">🔌电源</span>
              <span class="attr-chip bool-true" v-if="s.quiet">安静</span>
              <span class="attr-chip bool-true" v-if="s.group">讨论</span>
              <span class="attr-chip bool-true" v-if="s.corner">角落</span>
            </div>
            <div class="rc-slots">
              <template v-if="s.freeSlots && s.freeSlots.length">
                <span class="rc-slots-label">可约:</span>
                <span class="avail-slot" v-for="m in mergeSlots(s.freeSlots).slice(0, 12)" :key="m.start">{{ m.start }}-{{ m.end }}</span>
              </template>
              <span class="avail-slot none" v-else-if="currentDate">当天无空闲</span>
              <span class="rc-slots-label" v-else>选择日期后查看可约时段</span>
            </div>
          </div>
        </div>
      </div>
      <div class="room-lock" v-if="!hintReady">
        <div class="lock-icon">🔒</div>
        <p>请先选择预约日期与时段</p>
        <span>选择日期与起止时间后，即可点选资源</span>
      </div>
    </div>

    <div class="action-bar">
      <div class="selected-tip">{{ selTip }}</div>
      <button class="btn btn-primary" :disabled="!selectedId" @click="confirmBooking">确认预约</button>
    </div>

    <div class="modal-overlay" v-if="prefOpen">
      <div class="modal">
        <div class="modal-head">
          <h2>🎯 智能推荐</h2>
          <p>告诉我们你的偏好，为你推荐最合适的资源</p>
        </div>
        <div class="modal-body">
          <div class="form-field">
            <label>偏好（可多选）</label>
            <div class="chip-group">
              <div class="chip" :class="{ on: selectedPrefs.has(c.key) }" v-for="c in prefChips" :key="c.key" @click="togglePref(c.key)">{{ c.label }}</div>
            </div>
          </div>
          <div class="form-field">
            <label>专业方向</label>
            <select class="form-input" v-model="major">
              <option value="">不指定</option>
              <option value="cs">计算机 / 软件工程</option>
              <option value="math">数学 / 统计</option>
              <option value="literature">文学 / 语言</option>
              <option value="art">设计 / 艺术</option>
              <option value="science">理工科其他</option>
            </select>
          </div>
        </div>
        <div class="modal-foot">
          <button class="btn btn-ghost" @click="prefOpen = false">跳过</button>
          <button class="btn btn-primary" @click="runRecommend">为我推荐</button>
        </div>
      </div>
    </div>
  </section>
</template>
