<script setup>
import { ref, watch } from 'vue';
import { useScenarioModal, closeScenarioModal } from '../composables/useScenarioModal.js';
import { apiFetch } from '../api/request.js';
import { showResult } from '../composables/useResult.js';

const state = useScenarioModal();

const name = ref('');
const description = ref('');
const isActive = ref('true');
const timeStep = ref(30);
const minDuration = ref(30);
const maxDuration = ref(240);
const maxAdvanceDays = ref(30);
const minAdvanceMinutes = ref(0);
const allowSameDay = ref('true');
const maxActivePerUser = ref(5);
const maxMinutesPerDay = ref('');
const cancelBeforeMinutes = ref('');
const error = ref('');

watch(() => state.open, (open) => {
  if (!open) return;
  const s = state.editing;
  error.value = '';
  name.value = s ? s.name : '';
  description.value = s && s.description ? s.description : '';
  isActive.value = s ? String(s.is_active) : 'true';
  timeStep.value = s ? s.time_step_minutes : 30;
  minDuration.value = s ? s.min_duration_minutes : 30;
  maxDuration.value = s ? s.max_duration_minutes : 240;
  maxAdvanceDays.value = s ? s.max_advance_days : 30;
  minAdvanceMinutes.value = s ? s.min_advance_minutes : 0;
  allowSameDay.value = s ? String(s.allow_same_day) : 'true';
  maxActivePerUser.value = s ? s.max_active_per_user : 5;
  maxMinutesPerDay.value = s && s.max_minutes_per_day != null ? s.max_minutes_per_day : '';
  cancelBeforeMinutes.value = s && s.cancel_before_minutes != null ? s.cancel_before_minutes : '';
});

async function save() {
  if (!name.value.trim()) { error.value = '请输入场景名称'; return; }
  const minD = parseInt(minDuration.value, 10);
  const maxD = parseInt(maxDuration.value, 10);
  if (!(minD > 0) || !(maxD > 0)) { error.value = '请输入有效的时长范围'; return; }
  if (minD > maxD) { error.value = '最小时长不能大于最大时长'; return; }
  const body = {
    name: name.value.trim(),
    description: description.value.trim() || null,
    is_active: isActive.value === 'true',
    time_step_minutes: parseInt(timeStep.value, 10) || 30,
    min_duration_minutes: minD, max_duration_minutes: maxD,
    max_advance_days: parseInt(maxAdvanceDays.value, 10) || 0,
    min_advance_minutes: parseInt(minAdvanceMinutes.value, 10) || 0,
    allow_same_day: allowSameDay.value === 'true',
    max_active_per_user: parseInt(maxActivePerUser.value, 10) || 5,
  };
  const mmpd = maxMinutesPerDay.value.trim();
  body.max_minutes_per_day = mmpd ? parseInt(mmpd, 10) : null;
  const cbm = cancelBeforeMinutes.value.trim();
  body.cancel_before_minutes = cbm ? parseInt(cbm, 10) : null;
  error.value = '';
  try {
    if (state.editing) await apiFetch('/api/scenarios/' + state.editing.id, { method: 'PUT', body });
    else await apiFetch('/api/scenarios', { method: 'POST', body });
    closeScenarioModal();
    showResult({ type: 'success', title: '保存成功', desc: '场景「' + body.name + '」已保存。' });
    if (state.onSaved) state.onSaved();
  } catch (e) { error.value = e.message || '保存失败'; }
}
</script>

<template>
  <div class="modal-overlay" v-if="state.open">
    <div class="modal modal-wide">
      <div class="modal-head">
        <h2>{{ state.editing ? '编辑预约场景' : '新建预约场景' }}</h2>
        <p>配置场景基本信息与预约规则，突出可配置特色</p>
      </div>
      <div class="modal-body">
        <div class="form-error">{{ error }}</div>
        <div class="form-group">
          <div class="fg-title">基本信息</div>
          <div class="form-row">
            <div class="form-field"><label>场景名称 <i class="req">*</i></label><input type="text" class="form-input" v-model="name" placeholder="如：自习室座位预约"></div>
            <div class="form-field"><label>描述</label><input type="text" class="form-input" v-model="description" placeholder="可选"></div>
          </div>
          <div class="form-row">
            <div class="form-field"><label>是否启用</label>
              <select class="form-input" v-model="isActive"><option value="true">启用</option><option value="false">停用</option></select>
            </div>
          </div>
        </div>
        <div class="form-group">
          <div class="fg-title">时间粒度</div>
          <div class="form-row">
            <div class="form-field"><label>时段步长(分钟) <i class="req">*</i></label><input type="number" class="form-input" v-model="timeStep" min="5" max="240"></div>
          </div>
          <p class="form-hint">预约起止时间需按此步长对齐，可选 5-240</p>
        </div>
        <div class="form-group">
          <div class="fg-title">时长限制</div>
          <div class="form-row">
            <div class="form-field"><label>最小时长(分钟) <i class="req">*</i></label><input type="number" class="form-input" v-model="minDuration" min="5"></div>
            <div class="form-field"><label>最大时长(分钟) <i class="req">*</i></label><input type="number" class="form-input" v-model="maxDuration" max="1440"></div>
          </div>
        </div>
        <div class="form-group">
          <div class="fg-title">提前预约</div>
          <div class="form-row">
            <div class="form-field"><label>最多提前天数 <i class="req">*</i></label><input type="number" class="form-input" v-model="maxAdvanceDays" min="0" max="365"></div>
            <div class="form-field"><label>至少提前(分钟)</label><input type="number" class="form-input" v-model="minAdvanceMinutes" min="0" max="10080"></div>
            <div class="form-field"><label>允许当日预约</label><select class="form-input" v-model="allowSameDay"><option value="true">允许</option><option value="false">不允许</option></select></div>
          </div>
        </div>
        <div class="form-group">
          <div class="fg-title">配额</div>
          <div class="form-row">
            <div class="form-field"><label>每人最大活跃预约数 <i class="req">*</i></label><input type="number" class="form-input" v-model="maxActivePerUser" min="1" max="100"></div>
            <div class="form-field"><label>每人每日上限(分钟)</label><input type="number" class="form-input" v-model="maxMinutesPerDay" min="1" max="1440" placeholder="留空不限制"></div>
          </div>
        </div>
        <div class="form-group">
          <div class="fg-title">取消规则</div>
          <div class="form-row">
            <div class="form-field"><label>取消需提前(分钟)</label><input type="number" class="form-input" v-model="cancelBeforeMinutes" min="0" placeholder="留空不限制"></div>
          </div>
        </div>
      </div>
      <div class="modal-foot">
        <button class="btn btn-ghost" @click="closeScenarioModal">取消</button>
        <button class="btn btn-primary" @click="save">保存场景</button>
      </div>
    </div>
  </div>
</template>
