<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { apiFetch } from '../../api/request.js';
import { openAgent } from '../../composables/useAgent.js';
import { todayStr, isoDate, isoTime, statusText } from '../../composables/useUtils.js';

const router = useRouter();

const scenarioCount = ref(0);
const resourceCount = ref(0);
const activeCount = ref(0);
const todayCount = ref('—');
const recent = ref([]);
const scenarios = ref([]);

function quick(type) {
  if (type === 'agent') openAgent();
  else router.push('/user/' + type);
}

async function loadDashboard() {
  let list = [];
  try {
    const data = await apiFetch('/api/scenarios?page=1&page_size=200&include_inactive=false');
    list = data.items || [];
    scenarioCount.value = data.total || list.length;
  } catch (e) {}
  scenarios.value = list;

  const resCounts = await Promise.all(list.map(s =>
    apiFetch('/api/scenarios/' + s.id + '/resources?page=1&page_size=1').then(d => d.total || 0).catch(() => 0)
  ));
  resourceCount.value = resCounts.reduce((a, b) => a + b, 0);

  let myRes = [];
  try { myRes = await apiFetch('/api/reservations?status=all'); } catch (e) {}
  activeCount.value = myRes.filter(r => r.status === 'confirmed' || r.status === 'pending').length;

  todayCount.value = '—';
  if (list.length) {
    try {
      const av = await apiFetch('/api/scenarios/' + list[0].id + '/availability?date=' + todayStr());
      todayCount.value = av.free_slots_count || 0;
    } catch (e) {}
  }

  recent.value = myRes.slice().sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, 5);
}

onMounted(loadDashboard);
</script>

<template>
  <section class="page active">
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-icon indigo">🎯</div>
        <div class="stat-body"><b>{{ scenarioCount }}</b><span>预约场景</span></div>
      </div>
      <div class="stat-card">
        <div class="stat-icon emerald">📦</div>
        <div class="stat-body"><b>{{ resourceCount }}</b><span>可预约资源</span></div>
      </div>
      <div class="stat-card">
        <div class="stat-icon amber">📋</div>
        <div class="stat-body"><b>{{ activeCount }}</b><span>我的有效预约</span></div>
      </div>
      <div class="stat-card">
        <div class="stat-icon violet">🤖</div>
        <div class="stat-body"><b>{{ todayCount }}</b><span>今日可约时段</span></div>
      </div>
    </div>

    <div class="dash-grid">
      <div class="card dash-quick">
        <div class="card-header"><h3>快捷入口</h3></div>
        <div class="card-body">
          <div class="quick-grid">
            <button class="quick-item" @click="quick('booking')"><span class="qi-icon">📅</span><span>立即预约</span></button>
            <button class="quick-item" @click="quick('reservations')"><span class="qi-icon">📋</span><span>我的预约</span></button>
            <button class="quick-item" @click="quick('scenarios')"><span class="qi-icon">🎯</span><span>浏览场景</span></button>
            <button class="quick-item" @click="quick('agent')"><span class="qi-icon">🤖</span><span>AI 助手</span></button>
          </div>
        </div>
      </div>

      <div class="card dash-recent">
        <div class="card-header">
          <h3>最近预约</h3>
          <button class="link-btn" @click="quick('reservations')">查看全部 →</button>
        </div>
        <div class="card-body">
          <div class="recent-list">
            <div class="recent-item" v-for="r in recent" :key="r.id">
              <div class="ri-tag" :class="r.status === 'cancelled' ? 'cancel' : 'valid'">{{ r.status === 'cancelled' ? '❌' : '✅' }}</div>
              <div class="ri-main">
                <div class="ri-title">{{ (r.scenario_name || '') + ' · ' + (r.resource_code || r.resource_name || '') }}</div>
                <div class="ri-meta">{{ isoDate(r.start_time) }} {{ isoTime(r.start_time) }}-{{ isoTime(r.end_time) }} · {{ statusText(r.status) }}</div>
              </div>
            </div>
          </div>
          <div class="empty-state sm" v-if="!recent.length">
            <span class="empty-icon">🗓️</span>
            <p>暂无预约记录</p>
          </div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header"><h3>平台场景一览</h3></div>
      <div class="card-body">
        <div class="scenario-overview-grid">
          <div class="so-card" v-for="s in scenarios" :key="s.id" @click="quick('booking')">
            <div class="so-head"><span class="so-name">{{ s.name }}</span>
              <span class="badge" :class="s.is_active ? 'badge-success' : 'badge-danger'">{{ s.is_active ? '启用' : '停用' }}</span></div>
            <div class="so-desc">{{ s.description || '暂无描述' }}</div>
            <div class="so-meta"><span>步长 <b>{{ s.time_step_minutes }}</b>分</span><span>时长 <b>{{ s.min_duration_minutes }}-{{ s.max_duration_minutes }}</b>分</span><span>最多提前 <b>{{ s.max_advance_days }}</b>天</span></div>
          </div>
          <div class="empty-state sm" v-if="!scenarios.length">
            <span class="empty-icon">🎯</span><p>暂无场景</p>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
