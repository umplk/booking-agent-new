<script setup>
import { ref, watch } from 'vue';
import { useResourceModal, closeResourceModal } from '../composables/useResourceModal.js';
import { apiFetch } from '../api/request.js';
import { showResult } from '../composables/useResult.js';
import { fmtTime } from '../composables/useUtils.js';

const state = useResourceModal();

const name = ref('');
const code = ref('');
const openStart = ref('08:00');
const openEnd = ref('22:00');
const isActive = ref('true');
const attrs = ref([]);
const error = ref('');

watch(() => state.open, (open) => {
  if (!open) return;
  const r = state.editing;
  error.value = '';
  name.value = r ? r.name : '';
  code.value = r ? r.code : '';
  openStart.value = r ? fmtTime(r.open_start) : '08:00';
  openEnd.value = r ? fmtTime(r.open_end) : '22:00';
  isActive.value = r ? String(r.is_active) : 'true';
  const a = r && r.attributes ? r.attributes : {};
  attrs.value = Object.keys(a).map(k => ({ key: k, val: a[k] === true ? 'true' : (a[k] === false ? 'false' : String(a[k])) }));
});

function addAttr() {
  attrs.value.push({ key: '', val: '' });
}
function removeAttr(idx) {
  attrs.value.splice(idx, 1);
}

function collectAttrs() {
  const obj = {};
  attrs.value.forEach(row => {
    const k = row.key.trim();
    const v = row.val.trim();
    if (!k) return;
    if (v === 'true') obj[k] = true;
    else if (v === 'false') obj[k] = false;
    else if (v !== '' && !isNaN(Number(v)) && /^-?\d+(\.\d+)?$/.test(v)) obj[k] = Number(v);
    else obj[k] = v;
  });
  return obj;
}

async function save() {
  if (!state.scenario) { error.value = '未选择场景'; return; }
  if (!name.value.trim()) { error.value = '请输入资源名称'; return; }
  if (!code.value.trim()) { error.value = '请输入资源编号'; return; }
  if (!openStart.value || !openEnd.value) { error.value = '请输入开放时间'; return; }
  if (openStart.value >= openEnd.value) { error.value = '开放起始必须早于结束'; return; }
  const body = { name: name.value.trim(), code: code.value.trim(), open_start: openStart.value + ':00', open_end: openEnd.value + ':00', attributes: collectAttrs(), is_active: isActive.value === 'true' };
  error.value = '';
  try {
    if (state.editing) await apiFetch('/api/scenarios/' + state.scenario.id + '/resources/' + state.editing.id, { method: 'PUT', body });
    else await apiFetch('/api/scenarios/' + state.scenario.id + '/resources', { method: 'POST', body });
    closeResourceModal();
    showResult({ type: 'success', title: '保存成功', desc: '资源「' + body.code + '」已保存。' });
    if (state.onSaved) state.onSaved();
  } catch (e) { error.value = e.message || '保存失败'; }
}
</script>

<template>
  <div class="modal-overlay" v-if="state.open">
    <div class="modal modal-wide">
      <div class="modal-head">
        <h2>{{ state.editing ? '编辑资源' : '新建资源' }}</h2>
        <p>配置资源基本信息与扩展属性</p>
      </div>
      <div class="modal-body">
        <div class="form-error">{{ error }}</div>
        <div class="form-group">
          <div class="fg-title">基本信息</div>
          <div class="form-row">
            <div class="form-field"><label>资源名称 <i class="req">*</i></label><input type="text" class="form-input" v-model="name" placeholder="如：1F 文学区 A1 座位"></div>
            <div class="form-field"><label>资源编号 <i class="req">*</i></label><input type="text" class="form-input" v-model="code" placeholder="场景内唯一，如 1F-A1"></div>
          </div>
          <div class="form-row">
            <div class="form-field"><label>开放起始 <i class="req">*</i></label><input type="time" class="form-input" v-model="openStart"></div>
            <div class="form-field"><label>开放结束 <i class="req">*</i></label><input type="time" class="form-input" v-model="openEnd"></div>
            <div class="form-field"><label>是否启用</label><select class="form-input" v-model="isActive"><option value="true">启用</option><option value="false">停用</option></select></div>
          </div>
        </div>
        <div class="form-group">
          <div class="fg-title">扩展属性 (attributes) <button class="btn btn-ghost btn-sm" @click="addAttr">+ 添加</button></div>
          <p class="form-hint">描述资源特征，如 location / row / col / window / power / quiet / group / corner 等</p>
          <div class="attr-empty" v-if="!attrs.length">暂无扩展属性，点击「添加」新增（如 location、row、col、window 等）</div>
          <div class="attr-row" v-for="(a, idx) in attrs" :key="idx">
            <input class="attr-key" type="text" v-model="a.key" placeholder="属性名">
            <input class="attr-val" type="text" v-model="a.val" placeholder="属性值">
            <button class="attr-remove" type="button" @click="removeAttr(idx)">✕</button>
          </div>
        </div>
      </div>
      <div class="modal-foot">
        <button class="btn btn-ghost" @click="closeResourceModal">取消</button>
        <button class="btn btn-primary" @click="save">保存资源</button>
      </div>
    </div>
  </div>
</template>
