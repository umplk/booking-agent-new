<script setup>
import { ref, computed, onMounted } from 'vue';
import { apiFetch } from '../../api/request.js';
import { showResult } from '../../composables/useResult.js';
import { isoDate, isoTime, fmtDateTime, statusText, statusBadgeClass } from '../../composables/useUtils.js';

const scenarios = ref([]);
const bmScenario = ref('');
const bmStatus = ref('all');
const bmDate = ref('');
const bmSearch = ref('');
const allRes = ref([]);

const filteredList = computed(() => {
  const kw = bmSearch.value.trim().toLowerCase();
  if (!kw) return allRes.value;
  return allRes.value.filter(r => ((r.user_name || '') + (r.user_username || '') + (r.resource_code || '') + (r.resource_name || '')).toLowerCase().indexOf(kw) >= 0);
});

async function loadScenarios() {
  try {
    const data = await apiFetch('/api/scenarios?page=1&page_size=200&include_inactive=true');
    scenarios.value = data.items || [];
  } catch (e) { scenarios.value = []; }
}

async function queryBookings() {
  let path = '/api/reservations/admin?status=' + encodeURIComponent(bmStatus.value);
  if (bmScenario.value) path += '&scenario_id=' + bmScenario.value;
  if (bmDate.value) path += '&date=' + encodeURIComponent(bmDate.value);
  try { allRes.value = await apiFetch(path); }
  catch (e) { allRes.value = []; showResult({ type: 'fail', title: '查询失败', desc: e.message || '请检查权限' }); }
}

async function cancelBooking(r) {
  if (!confirm('确认取消该预约？\n用户：' + (r.user_name || r.user_username || '—') + '\n资源：' + (r.resource_code || r.resource_name) + '\n时段：' + isoDate(r.start_time) + ' ' + isoTime(r.start_time) + '-' + isoTime(r.end_time))) return;
  try {
    await apiFetch('/api/reservations/' + r.id + '/cancel', { method: 'PUT' });
    await queryBookings();
    showResult({ type: 'success', title: '已取消预约', desc: '资源已释放。' });
  } catch (e) { showResult({ type: 'fail', title: '取消失败', desc: e.message }); }
}

onMounted(async () => {
  await loadScenarios();
  await queryBookings();
});
</script>

<template>
  <section class="page active">
    <div class="card filter-bar">
      <div class="filter-row">
        <div class="filter-field">
          <label>预约场景</label>
          <select class="form-input" v-model="bmScenario" @change="queryBookings"><option value="">全部场景</option><option v-for="s in scenarios" :key="s.id" :value="s.id">{{ s.name }}</option></select>
        </div>
        <div class="filter-field">
          <label>状态</label>
          <select class="form-input" v-model="bmStatus" @change="queryBookings">
            <option value="all">全部</option><option value="confirmed">已确认</option><option value="pending">待确认</option><option value="cancelled">已取消</option><option value="completed">已完成</option>
          </select>
        </div>
        <div class="filter-field">
          <label>日期</label>
          <input type="date" class="form-input" v-model="bmDate" @change="queryBookings">
        </div>
        <input type="text" class="form-input search-input" v-model="bmSearch" placeholder="搜索用户 / 资源…">
        <button class="btn btn-primary" @click="queryBookings">查询</button>
      </div>
    </div>

    <div class="card">
      <div class="card-header"><h3>预约列表</h3><span class="card-hint">{{ filteredList.length }} 条记录</span></div>
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>ID</th><th>用户</th><th>场景</th><th>资源</th><th>日期</th><th>时段</th><th>状态</th><th>创建时间</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="r in filteredList" :key="r.id">
              <td class="col-id">{{ r.id }}</td>
              <td>{{ r.user_name || r.user_username || '—' }}</td>
              <td>{{ r.scenario_name || '—' }}</td>
              <td class="col-code">{{ r.resource_code || r.resource_name || '—' }}</td>
              <td>{{ isoDate(r.start_time) }}</td>
              <td>{{ isoTime(r.start_time) }}-{{ isoTime(r.end_time) }}</td>
              <td><span class="badge" :class="statusBadgeClass(r.status)">{{ statusText(r.status) }}</span></td>
              <td>{{ fmtDateTime(r.created_at) }}</td>
              <td>
                <div class="admin-actions">
                  <button class="btn-act danger" v-if="r.status !== 'cancelled' && r.status !== 'completed'" @click="cancelBooking(r)">取消</button>
                  <span class="attr-chip" v-else>—</span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="empty-state sm" v-if="!filteredList.length"><span class="empty-icon">🗂️</span><p>暂无预约记录</p></div>
    </div>
  </section>
</template>

<style scoped>
.admin-actions { display: flex; gap: 6px; }
</style>
