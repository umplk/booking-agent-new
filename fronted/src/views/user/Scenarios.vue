<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { apiFetch } from '../../api/request.js';
import { showResult } from '../../composables/useResult.js';

const router = useRouter();
const scenarioList = ref([]);
const keyword = ref('');

const filteredList = computed(() => {
  const kw = keyword.value.trim().toLowerCase();
  return kw ? scenarioList.value.filter(s => s.name.toLowerCase().indexOf(kw) >= 0) : scenarioList.value;
});

async function loadData() {
  try {
    const data = await apiFetch('/api/scenarios?page=1&page_size=200&mine=false&include_inactive=false');
    scenarioList.value = data.items || [];
  } catch (e) { scenarioList.value = []; }
}

function goBooking() {
  router.push('/user/booking');
}

onMounted(loadData);
</script>

<template>
  <section class="page active">
    <div class="page-actions">
      <input type="text" class="form-input search-input" v-model="keyword" placeholder="搜索场景名称…">
    </div>
    <div class="scenario-card-grid">
      <div class="scen-card" v-for="s in filteredList" :key="s.id">
        <div class="scen-card-head">
          <div class="scen-card-name">{{ s.name }}</div>
          <div class="scen-card-desc">{{ s.description || '暂无描述' }}</div>
        </div>
        <div class="scen-card-body"><div class="scen-rules">
          <div class="scen-rule"><span>时段步长</span><span>{{ s.time_step_minutes }} 分钟</span></div>
          <div class="scen-rule"><span>时长范围</span><span>{{ s.min_duration_minutes }}-{{ s.max_duration_minutes }} 分钟</span></div>
          <div class="scen-rule"><span>最多提前</span><span>{{ s.max_advance_days }} 天</span></div>
          <div class="scen-rule"><span>活跃预约上限</span><span>{{ s.max_active_per_user }} 个</span></div>
          <div class="scen-rule"><span>当日预约</span><span>{{ s.allow_same_day ? '允许' : '不允许' }}</span></div>
          <div class="scen-rule"><span>状态</span><span>{{ s.is_active ? '启用' : '停用' }}</span></div>
        </div></div>
        <div class="scen-card-foot">
          <button class="btn-act primary" @click="goBooking">去预约</button>
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
