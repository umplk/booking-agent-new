<script setup>
import { ref, onMounted } from 'vue';
import { apiFetch } from '../../api/request.js';
import { openScenarioModal } from '../../composables/useScenarioModal.js';

const scenarios = ref([]);

async function loadData() {
  try {
    const data = await apiFetch('/api/scenarios?page=1&page_size=200&mine=true&include_inactive=true');
    scenarios.value = data.items || [];
  } catch (e) { scenarios.value = []; }
}

function editRule(s) {
  openScenarioModal(s, loadData);
}

onMounted(loadData);
</script>

<template>
  <section class="page active">
    <div class="rules-intro card">
      <div class="card-body">
        <div class="rules-intro-head">
          <span class="ri-icon">⚙️</span>
          <div>
            <h3>可配置预约规则</h3>
            <p>每个预约场景拥有独立的规则配置，包括时间粒度、时长限制、提前预约、配额与取消规则。点击下方场景可编辑其规则。</p>
          </div>
        </div>
      </div>
    </div>
    <div class="rules-grid">
      <div class="rule-card" v-for="s in scenarios" :key="s.id">
        <div class="rule-card-head"><span class="rule-card-name">{{ s.name }}</span><span class="badge" :class="s.is_active ? 'badge-success' : 'badge-danger'">{{ s.is_active ? '启用' : '停用' }}</span></div>
        <div class="rule-card-body">
          <div class="rule-field"><span class="rf-label">时段步长</span><span class="rf-value">{{ s.time_step_minutes }} 分钟</span></div>
          <div class="rule-field"><span class="rf-label">最小时长</span><span class="rf-value">{{ s.min_duration_minutes }} 分钟</span></div>
          <div class="rule-field"><span class="rf-label">最大时长</span><span class="rf-value">{{ s.max_duration_minutes }} 分钟</span></div>
          <div class="rule-field"><span class="rf-label">最多提前天数</span><span class="rf-value">{{ s.max_advance_days }} 天</span></div>
          <div class="rule-field"><span class="rf-label">至少提前</span><span class="rf-value" :class="{ muted: !s.min_advance_minutes }">{{ s.min_advance_minutes ? s.min_advance_minutes + ' 分钟' : '即时预约' }}</span></div>
          <div class="rule-field"><span class="rf-label">每日上限</span><span class="rf-value" :class="{ muted: !s.max_minutes_per_day }">{{ s.max_minutes_per_day ? s.max_minutes_per_day + ' 分钟' : '不限制' }}</span></div>
          <div class="rule-field"><span class="rf-label">允许当日预约</span><span class="rf-value" :class="{ muted: !s.allow_same_day }">{{ s.allow_same_day ? '允许' : '不允许' }}</span></div>
          <div class="rule-field"><span class="rf-label">活跃预约上限</span><span class="rf-value">{{ s.max_active_per_user }} 个</span></div>
          <div class="rule-field"><span class="rf-label">取消需提前</span><span class="rf-value" :class="{ muted: s.cancel_before_minutes == null }">{{ s.cancel_before_minutes != null ? s.cancel_before_minutes + ' 分钟' : '不限制' }}</span></div>
        </div>
        <div class="rule-card-foot"><button class="btn-act primary" @click="editRule(s)">编辑规则</button></div>
      </div>
      <div class="empty-state" v-if="!scenarios.length"><span class="empty-icon">⚙️</span><p>暂无场景规则</p></div>
    </div>
  </section>
</template>
