<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { apiFetch } from '../../api/request.js';
import { SCENARIO_CATEGORIES, categoryLabel, categoryIcon, splitTags } from '../../composables/useScenarioMeta.js';

const router = useRouter();
const scenarioList = ref([]);
const keyword = ref('');
const activeCategory = ref('all');

const presentCategories = computed(() => {
  const used = new Set(scenarioList.value.map(s => s.category || 'other'));
  return SCENARIO_CATEGORIES.filter(c => used.has(c.value));
});

function categoryCount(value) {
  return scenarioList.value.filter(s => (s.category || 'other') === value).length;
}

const filteredList = computed(() => {
  const kw = keyword.value.trim().toLowerCase();
  return scenarioList.value.filter(s => {
    if (activeCategory.value !== 'all' && (s.category || 'other') !== activeCategory.value) return false;
    if (!kw) return true;
    const hay = (s.name + (s.location || '') + (s.tags || '') + (s.description || '')).toLowerCase();
    return hay.indexOf(kw) >= 0;
  });
});

async function loadData() {
  try {
    const data = await apiFetch('/api/scenarios?page=1&page_size=200&mine=false&include_inactive=false');
    scenarioList.value = data.items || [];
  } catch (e) { scenarioList.value = []; }
}

function goBooking(s) {
  router.push({ path: '/user/booking', query: { scenario: s.id } });
}

onMounted(loadData);
</script>

<template>
  <section class="page active">
    <div class="page-actions">
      <input type="text" class="form-input search-input" v-model="keyword" placeholder="搜索场景名称 / 位置 / 标签…">
    </div>
    <div class="scenario-tabs">
      <button class="scen-tab" :class="{ active: activeCategory === 'all' }" @click="activeCategory = 'all'">全部 ({{ scenarioList.length }})</button>
      <button class="scen-tab" v-for="c in presentCategories" :key="c.value" :class="{ active: activeCategory === c.value }" @click="activeCategory = c.value">{{ c.icon }} {{ c.label }} ({{ categoryCount(c.value) }})</button>
    </div>
    <div class="scenario-card-grid">
      <div class="scen-card" v-for="s in filteredList" :key="s.id">
        <div class="scen-card-head">
          <div class="scen-card-title">
            <span class="scen-card-icon">{{ s.icon || categoryIcon(s.category) }}</span>
            <span class="scen-card-name">{{ s.name }}</span>
            <span class="badge badge-warning" v-if="s.is_featured">推荐</span>
          </div>
          <div class="scen-card-desc">{{ s.description || '暂无描述' }}</div>
          <div class="scen-card-sub">
            <span class="badge ghost">{{ categoryLabel(s.category) }}</span>
            <span v-if="s.location">📍 {{ s.location }}</span>
            <span class="attr-chip" v-for="t in splitTags(s.tags)" :key="t">{{ t }}</span>
          </div>
        </div>
        <div class="scen-card-body">
          <div class="scen-rules">
            <div class="scen-rule"><span>时段步长</span><span>{{ s.time_step_minutes }} 分钟</span></div>
            <div class="scen-rule"><span>时长范围</span><span>{{ s.min_duration_minutes }}-{{ s.max_duration_minutes }} 分钟</span></div>
            <div class="scen-rule"><span>最多提前</span><span>{{ s.max_advance_days }} 天</span></div>
            <div class="scen-rule"><span>活跃预约上限</span><span>{{ s.max_active_per_user }} 个</span></div>
            <div class="scen-rule"><span>当日预约</span><span>{{ s.allow_same_day ? '允许' : '不允许' }}</span></div>
          </div>
          <div class="scen-notice" v-if="s.booking_notice">📌 {{ s.booking_notice }}</div>
        </div>
        <div class="scen-card-foot">
          <button class="btn-act primary" @click="goBooking(s)">去预约</button>
        </div>
      </div>
    </div>
    <div class="empty-state" v-if="!filteredList.length">
      <span class="empty-icon">🎯</span>
      <p>暂无预约场景</p>
      <span>平台暂未开放可预约场景</span>
    </div>
  </section>
</template>

<style scoped>
.scenario-tabs { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.scen-tab {
  padding: 6px 14px; border-radius: 999px; border: 1px solid var(--border);
  background: var(--card); color: var(--text-2); font-size: 13px; cursor: pointer;
  transition: all .15s ease;
}
.scen-tab:hover { border-color: var(--primary); color: var(--primary); }
.scen-tab.active { background: var(--primary); border-color: var(--primary); color: #fff; }
.scen-card-title { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 6px; }
.scen-card-icon { font-size: 20px; line-height: 1; }
.scen-card-title .scen-card-name { margin-bottom: 0; }
.scen-card-sub { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-top: 8px; font-size: 12px; color: var(--text-3); }
.scen-notice { margin-top: 12px; padding: 8px 10px; border-radius: var(--r-sm); background: var(--primary-50); color: var(--text-2); font-size: 12px; line-height: 1.5; }
</style>