<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { apiFetch } from '../../api/request.js';
import { showResult } from '../../composables/useResult.js';
import { isoDate, isoTime, fmtDateTime, statusText } from '../../composables/useUtils.js';

const router = useRouter();
const myReservations = ref([]);
const tab = ref('active');

const activeList = computed(() => myReservations.value.filter(r => r.status === 'confirmed' || r.status === 'pending'));
const historyList = computed(() => myReservations.value.slice().sort((a, b) => new Date(b.created_at) - new Date(a.created_at)));

async function loadData() {
  try { myReservations.value = await apiFetch('/api/reservations?status=all'); } catch (e) { myReservations.value = []; }
}

async function cancelReservation(r) {
  try {
    await apiFetch('/api/reservations/' + r.id + '/cancel', { method: 'PUT' });
    await loadData();
    showResult({ type: 'success', title: '已取消预约', desc: '资源已释放。' });
  } catch (e) { showResult({ type: 'fail', title: '取消失败', desc: e.message }); }
}

function goBooking() {
  router.push('/user/booking');
}

onMounted(loadData);
</script>

<template>
  <section class="page active">
    <div class="res-tabs">
      <button class="res-tab" :class="{ active: tab === 'active' }" @click="tab = 'active'">有效预约</button>
      <button class="res-tab" :class="{ active: tab === 'history' }" @click="tab = 'history'">历史记录</button>
    </div>

    <div class="res-panel" v-show="tab === 'active'">
      <div class="res-list">
        <div class="res-card" v-for="r in activeList" :key="r.id">
          <div class="res-icon valid">✅</div>
          <div class="res-main">
            <div class="res-title">{{ (r.scenario_name || '') + ' · ' + (r.resource_code || r.resource_name || '') }}</div>
            <div class="res-meta">日期：{{ isoDate(r.start_time) }} · 时段：{{ isoTime(r.start_time) }}-{{ isoTime(r.end_time) }} · 状态：{{ statusText(r.status) }} · 创建：{{ fmtDateTime(r.created_at) }}</div>
          </div>
          <div class="res-actions">
            <button class="btn btn-ghost btn-sm" @click="cancelReservation(r)">取消预约</button>
          </div>
        </div>
      </div>
      <div class="empty-state" v-if="!activeList.length">
        <span class="empty-icon">🗓️</span>
        <p>暂无有效预约</p>
        <span>前往「我要预约」选择资源即可创建预约</span>
        <button class="btn btn-primary" @click="goBooking">去预约</button>
      </div>
    </div>

    <div class="res-panel" v-show="tab === 'history'">
      <div class="res-list">
        <div class="res-card" v-for="r in historyList" :key="r.id">
          <div class="res-icon" :class="r.status === 'cancelled' ? 'cancel' : 'valid'">{{ r.status === 'cancelled' ? '❌' : '✅' }}</div>
          <div class="res-main">
            <div class="res-title">{{ (r.scenario_name || '') + ' · ' + (r.resource_code || r.resource_name || '') }}</div>
            <div class="res-meta">日期：{{ isoDate(r.start_time) }} · 时段：{{ isoTime(r.start_time) }}-{{ isoTime(r.end_time) }} · 状态：{{ statusText(r.status) }} · 创建：{{ fmtDateTime(r.created_at) }}</div>
          </div>
        </div>
      </div>
      <div class="empty-state" v-if="!historyList.length">
        <span class="empty-icon">📭</span>
        <p>暂无历史记录</p>
      </div>
    </div>
  </section>
</template>
