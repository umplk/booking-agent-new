<script setup>
import { ref, watch } from 'vue';
import { useScenarioModal, closeScenarioModal } from '../composables/useScenarioModal.js';
import { apiFetch } from '../api/request.js';
import { showResult } from '../composables/useResult.js';
import { SCENARIO_CATEGORIES, SCENARIO_TEMPLATES } from '../composables/useScenarioMeta.js';

const state = useScenarioModal();

const templateKey = ref('');
const name = ref('');
const description = ref('');
const category = ref('study_room');
const icon = ref('🎯');
const location = ref('');
const tags = ref('');
const isFeatured = ref('false');
const sortOrder = ref(0);
const bookingNotice = ref('');
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
  templateKey.value = '';
  error.value = '';
  name.value = s ? s.name : '';
  description.value = s && s.description ? s.description : '';
  category.value = s && s.category ? s.category : 'study_room';
  icon.value = s && s.icon ? s.icon : '🎯';
  location.value = s && s.location ? s.location : '';
  tags.value = s && s.tags ? s.tags : '';
  isFeatured.value = s ? String(s.is_featured) : 'false';
  sortOrder.value = s ? s.sort_order : 0;
  bookingNotice.value = s && s.booking_notice ? s.booking_notice : '';
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

function applyTemplate() {
  const t = SCENARIO_TEMPLATES.find(x => x.key === templateKey.value);
  if (!t) return;
  name.value = t.name;
  description.value = t.description;
  category.value = t.category;
  icon.value = t.icon;
  tags.value = t.tags;
  bookingNotice.value = t.booking_notice;
  const r = t.rules;
  timeStep.value = r.time_step_minutes;
  minDuration.value = r.min_duration_minutes;
  maxDuration.value = r.max_duration_minutes;
  maxAdvanceDays.value = r.max_advance_days;
  minAdvanceMinutes.value = r.min_advance_minutes;
  allowSameDay.value = String(r.allow_same_day);
  maxActivePerUser.value = r.max_active_per_user;
  maxMinutesPerDay.value = r.max_minutes_per_day != null ? r.max_minutes_per_day : '';
  cancelBeforeMinutes.value = r.cancel_before_minutes != null ? r.cancel_before_minutes : '';
}

async function save() {
  if (!name.value.trim()) { error.value = '请输入场景名称'; return; }
  const minD = parseInt(minDuration.value, 10);
  const maxD = parseInt(maxDuration.value, 10);
  if (!(minD > 0) || !(maxD > 0)) { error.value = '请输入有效的时长范围'; return; }
  if (minD > maxD) { error.value = '最小时长不能大于最大时长'; return; }
  const body = {
    name: name.value.trim(),
    description: description.value.trim() || null,
    category: category.value,
    icon: icon.value.trim() || '🎯',
    location: location.value.trim() || null,
    tags: tags.value.trim() || null,
    is_featured: isFeatured.value === 'true',
    sort_order: parseInt(sortOrder.value, 10) || 0,
    booking_notice: bookingNotice.value.trim() || null,
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
        <div class="form-group" v-if="!state.editing">
          <div class="fg-title">快速模板</div>
          <div class="form-row">
            <div class="form-field">
              <select class="form-input" v-model="templateKey" @change="applyTemplate">
                <option value="">选择业态模板，自动填充规则（可选）</option>
                <option v-for="t in SCENARIO_TEMPLATES" :key="t.key" :value="t.key">{{ t.icon }} {{ t.name }}</option>
              </select>
            </div>
          </div>
          <p class="form-hint">选择模板后仍可自由修改下方所有配置</p>
        </div>
        <div class="form-group">
          <div class="fg-title">基本信息</div>
          <div class="form-row">
            <div class="form-field"><label>场景名称 <i class="req">*</i></label><input type="text" class="form-input" v-model="name" placeholder="如：自习室座位预约"></div>
            <div class="form-field"><label>描述</label><input type="text" class="form-input" v-model="description" placeholder="可选"></div>
          </div>
          <div class="form-row">
            <div class="form-field"><label>场景类型</label>
              <select class="form-input" v-model="category">
                <option v-for="c in SCENARIO_CATEGORIES" :key="c.value" :value="c.value">{{ c.icon }} {{ c.label }}</option>
              </select>
            </div>
            <div class="form-field"><label>图标</label><input type="text" class="form-input" v-model="icon" maxlength="4" placeholder="emoji"></div>
            <div class="form-field"><label>所属位置</label><input type="text" class="form-input" v-model="location" placeholder="如：A栋 1楼"></div>
          </div>
          <div class="form-row">
            <div class="form-field"><label>标签</label><input type="text" class="form-input" v-model="tags" placeholder="逗号分隔，如：安静,插座,靠窗"></div>
            <div class="form-field"><label>展示排序</label><input type="number" class="form-input" v-model="sortOrder" min="0" max="9999"></div>
            <div class="form-field"><label>推荐位</label>
              <select class="form-input" v-model="isFeatured"><option value="false">否</option><option value="true">是（排序靠前）</option></select>
            </div>
            <div class="form-field"><label>是否启用</label>
              <select class="form-input" v-model="isActive"><option value="true">启用</option><option value="false">停用</option></select>
            </div>
          </div>
          <div class="form-row">
            <div class="form-field full"><label>预约须知</label><textarea class="form-input" v-model="bookingNotice" rows="2" placeholder="展示给用户的入场/取消说明"></textarea></div>
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

<style scoped>
.form-field.full { flex: 1 1 100%; }
</style>