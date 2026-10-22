<script setup>
import { ref, computed, onMounted } from 'vue';
import { useAuth } from '../../composables/useAuth.js';
import { apiFetch } from '../../api/request.js';
import { showResult } from '../../composables/useResult.js';

const auth = useAuth();
const statTotal = ref('—');
const statValid = ref('—');
const statCancel = ref('—');
const editOpen = ref(false);
const editError = ref('');
const peName = ref('');
const peStudentId = ref('');
const peEmail = ref('');
const pePassword = ref('');

const user = computed(() => auth.user || {});
const displayName = computed(() => user.value.name || user.value.username || '未登录');
const avatarChar = computed(() => displayName.value.charAt(0));

async function loadData() {
  if (user.value.role === 'admin') {
    try {
      const list = await apiFetch('/api/reservations/admin?status=all');
      statTotal.value = list.length;
      statValid.value = list.filter(r => r.status === 'confirmed' || r.status === 'pending').length;
      statCancel.value = list.filter(r => r.status === 'cancelled').length;
    } catch (e) {}
  }
}

function openEdit() {
  peName.value = user.value.name || '';
  peStudentId.value = user.value.student_id || '';
  peEmail.value = user.value.email || '';
  pePassword.value = '';
  editError.value = '';
  editOpen.value = true;
}

async function saveEdit() {
  const body = { name: peName.value.trim() || null, student_id: peStudentId.value.trim() || null, email: peEmail.value.trim() };
  if (pePassword.value) body.password = pePassword.value;
  editError.value = '';
  try {
    const updated = await apiFetch('/api/users/me', { method: 'PUT', body });
    auth.user = updated;
    editOpen.value = false;
    showResult({ type: 'success', title: '保存成功', desc: '个人信息已更新。' });
  } catch (e) { editError.value = e.message || '保存失败'; }
}

onMounted(loadData);
</script>

<template>
  <section class="page active">
    <div class="card profile-card">
      <div class="card-body">
        <div class="profile-head">
          <div class="profile-avatar lg">{{ avatarChar }}</div>
          <div class="profile-info">
            <h2>{{ displayName }}</h2>
            <p class="profile-email">{{ user.email || '—' }}</p>
            <div class="profile-tags">
              <span class="badge">{{ user.role === 'admin' ? '管理员' : '普通用户' }}</span>
              <span class="badge ghost">学号：{{ user.student_id || '—' }}</span>
            </div>
          </div>
          <button class="btn btn-ghost" @click="openEdit">编辑资料</button>
        </div>
        <div class="profile-stats">
          <div class="ps-item"><b>{{ statTotal }}</b><span>累计预约</span></div>
          <div class="ps-item"><b>{{ statValid }}</b><span>有效预约</span></div>
          <div class="ps-item"><b>{{ statCancel }}</b><span>已取消</span></div>
        </div>
      </div>
    </div>

    <div class="modal-overlay" v-if="editOpen">
      <div class="modal">
        <div class="modal-head"><h2>编辑个人资料</h2><p>更新你的个人信息</p></div>
        <div class="modal-body">
          <div class="form-error">{{ editError }}</div>
          <div class="form-field"><label>姓名</label><input type="text" class="form-input" v-model="peName" placeholder="请输入姓名"></div>
          <div class="form-field"><label>学号</label><input type="text" class="form-input" v-model="peStudentId" placeholder="请输入学号"></div>
          <div class="form-field"><label>邮箱</label><input type="text" class="form-input" v-model="peEmail" placeholder="请输入邮箱"></div>
          <div class="form-field"><label>新密码</label><input type="password" class="form-input" v-model="pePassword" placeholder="留空则不修改"></div>
        </div>
        <div class="modal-foot">
          <button class="btn btn-ghost" @click="editOpen = false">取消</button>
          <button class="btn btn-primary" @click="saveEdit">保存</button>
        </div>
      </div>
    </div>
  </section>
</template>
