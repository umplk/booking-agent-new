<script setup>
import { ref, computed, onMounted } from 'vue';
import { apiFetch } from '../../api/request.js';
import { showResult } from '../../composables/useResult.js';
import { openResourceModal } from '../../composables/useResourceModal.js';
import { fmtTime, mergeSlots } from '../../composables/useUtils.js';

const scenarios = ref([]);
const currentScenario = ref(null);
const scenarioSelect = ref('');
const resources = ref([]);
const searchKw = ref('');
const genInput = ref('');
const genHint = ref('由 AI 解析描述并批量创建资源');
const availDate = ref('');
const availHint = ref('选择日期查看各资源当天空闲时段');
const availResult = ref(null);

const filteredList = computed(() => {
  const kw = searchKw.value.trim().toLowerCase();
  if (!kw) return resources.value;
  return resources.value.filter(r => (r.name + r.code).toLowerCase().indexOf(kw) >= 0);
});

async function loadScenarios() {
  try {
    const data = await apiFetch('/api/scenarios?page=1&page_size=200&mine=true&include_inactive=true');
    scenarios.value = data.items || [];
  } catch (e) { scenarios.value = []; }
  if (scenarios.value.length) {
    currentScenario.value = scenarios.value[0];
    scenarioSelect.value = scenarios.value[0].id;
    await loadResources();
  }
}

async function onScenarioChange() {
  const id = parseInt(scenarioSelect.value, 10);
  currentScenario.value = scenarios.value.find(s => s.id === id);
  await loadResources();
}

async function loadResources() {
  if (!currentScenario.value) return;
  try {
    const data = await apiFetch('/api/scenarios/' + currentScenario.value.id + '/resources?page=1&page_size=500');
    resources.value = data.items || [];
  } catch (e) { resources.value = []; }
}

function newResource() { openResourceModal(null, currentScenario.value, loadResources); }
function editResource(r) { openResourceModal(r, currentScenario.value, loadResources); }

async function deleteResource(r) {
  if (!confirm('确认删除资源「' + r.code + ' ' + r.name + '」？\n相关预约将一并删除，此操作不可恢复。')) return;
  try {
    await apiFetch('/api/scenarios/' + currentScenario.value.id + '/resources/' + r.id, { method: 'DELETE' });
    await loadResources();
    showResult({ type: 'success', title: '已删除', desc: '资源「' + r.code + '」已删除。' });
  } catch (e) { showResult({ type: 'fail', title: '删除失败', desc: e.message }); }
}

async function aiGenerate() {
  if (!currentScenario.value) return;
  const desc = genInput.value.trim();
  if (!desc) { genHint.value = '请先输入资源描述'; return; }
  genHint.value = 'AI 生成中…';
  try {
    const data = await apiFetch('/api/scenarios/' + currentScenario.value.id + '/resources/generate', { method: 'POST', body: { description: desc } });
    genInput.value = '';
    genHint.value = (data.count || 0) ? '已生成 ' + data.count + ' 个资源' : '未生成新资源（编号可能已存在）';
    await loadResources();
    showResult({ type: 'success', title: '生成成功', desc: 'AI 已根据「' + desc + '」生成 ' + (data.count || 0) + ' 个资源。' });
  } catch (e) { genHint.value = '生成失败'; showResult({ type: 'fail', title: '生成失败', desc: e.message || '请稍后重试' }); }
}

async function queryAvail() {
  if (!currentScenario.value) return;
  if (!availDate.value) { availHint.value = '请先选择查询日期'; return; }
  availHint.value = '查询中…';
  try {
    const data = await apiFetch('/api/scenarios/' + currentScenario.value.id + '/availability?date=' + availDate.value);
    availResult.value = data;
    availHint.value = '已加载 ' + (data.resources || []).length + ' 个资源在 ' + availDate.value + ' 的可预约状态';
  } catch (e) { availHint.value = '查询失败'; showResult({ type: 'fail', title: '查询失败', desc: e.message }); }
}

function attrEntries(attrs) {
  return Object.keys(attrs || {}).map(k => ({ k, v: attrs[k] }));
}
function attrText(v) { return v === true ? '' + true : (v === false ? '¬' : String(v)); }
function attrClass(v) { return v === true ? 'bool-true' : (v === false ? 'bool-false' : ''); }
function attrLabel(k, v) { return v === true ? k : (v === false ? '¬' + k : k + '=' + v); }

onMounted(loadScenarios);
</script>

<template>
  <section class="page active">
    <div class="card filter-bar">
      <div class="filter-row">
        <div class="filter-field">
          <label>选择场景</label>
          <select class="form-input" v-model="scenarioSelect" @change="onScenarioChange"><option v-for="s in scenarios" :key="s.id" :value="s.id">{{ s.name }}</option></select>
        </div>
        <input type="text" class="form-input search-input" v-model="searchKw" placeholder="搜索资源…">
        <button class="btn btn-primary" @click="newResource">+ 新建资源</button>
      </div>
    </div>

    <div class="card ai-gen-card">
      <div class="card-header"><h3>🤖 AI 批量生成资源</h3><span class="card-hint">用自然语言描述，AI 自动解析并批量创建</span></div>
      <div class="card-body">
        <div class="ai-gen-row">
          <input type="text" class="form-input" v-model="genInput" placeholder="如「5 个羽毛球场地，9-22 点开放」或「3 间会议室，带投影仪」">
          <button class="btn btn-primary" @click="aiGenerate">生成</button>
        </div>
        <div class="form-hint">{{ genHint }}</div>
      </div>
    </div>

    <div class="card">
      <div class="card-header"><h3>📅 可预约状态查询</h3></div>
      <div class="card-body">
        <div class="avail-query-row">
          <input type="date" class="form-input" v-model="availDate">
          <button class="btn btn-ghost" @click="queryAvail">查询</button>
          <span class="form-hint">{{ availHint }}</span>
        </div>
        <div class="avail-result" v-if="availResult">
          <div class="admin-avail-summary">📅 {{ availDate }} · 共 {{ (availResult.resources || []).length }} 个资源 · 合计 {{ availResult.free_slots_count || 0 }} 个空闲时段</div>
          <div class="admin-avail-resource" v-for="r in (availResult.resources || [])" :key="r.resource_id">
            <div class="ar-head"><span class="ar-code">{{ r.code }}</span><span class="ar-name">{{ r.name }}</span><span class="badge" :class="r.is_active ? 'badge-success' : 'badge-danger'">{{ r.is_active ? '启用' : '停用' }}</span></div>
            <div class="admin-avail-slots">
              <span class="avail-slot none" v-if="!(r.free_slots || []).length">当天无空闲</span>
              <span class="avail-slot" v-for="m in mergeSlots(r.free_slots || [])" :key="m.start">{{ m.start }}-{{ m.end }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header"><h3>资源列表</h3><span class="card-hint">{{ filteredList.length }} 个资源</span></div>
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>ID</th><th>编号</th><th>名称</th><th>开放时间</th><th>属性</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="r in filteredList" :key="r.id">
              <td class="col-id">{{ r.id }}</td>
              <td class="col-code">{{ r.code }}</td>
              <td>{{ r.name }}</td>
              <td>{{ fmtTime(r.open_start) }}-{{ fmtTime(r.open_end) }}</td>
              <td class="col-attrs"><div class="attr-chips">
                <span class="attr-chip" :class="attrClass(e.v)" v-for="e in attrEntries(r.attributes)" :key="e.k">{{ attrLabel(e.k, e.v) }}</span>
              </div></td>
              <td><span class="badge" :class="r.is_active ? 'badge-success' : 'badge-danger'">{{ r.is_active ? '启用' : '停用' }}</span></td>
              <td><div class="admin-actions">
                <button class="btn-act primary" @click="editResource(r)">编辑</button>
                <button class="btn-act danger" @click="deleteResource(r)">删除</button>
              </div></td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="empty-state sm" v-if="!filteredList.length"><span class="empty-icon">📦</span><p>该场景下暂无资源</p></div>
    </div>
  </section>
</template>

<style scoped>
.admin-actions { display: flex; gap: 6px; }
</style>
