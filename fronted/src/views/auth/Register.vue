<script setup>
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { register, login } from '../../composables/useAuth.js';

const router = useRouter();

const role = ref('student');
const username = ref('');
const name = ref('');
const studentId = ref('');
const email = ref('');
const password = ref('');
const error = ref('');
const submitting = ref(false);

const isMerchant = computed(() => role.value === 'merchant');

async function doRegister() {
  const u = username.value.trim();
  const nm = name.value.trim();
  const sid = studentId.value.trim();
  const em = email.value.trim();
  const p = password.value;
  if (!u || u.length < 3) { error.value = '用户名至少 3 位'; return; }
  if (!em) { error.value = '请输入邮箱'; return; }
  if (!p || p.length < 6) { error.value = '密码至少 6 位'; return; }
  if (isMerchant.value && !nm) { error.value = '请输入商家名称'; return; }
  error.value = '';
  submitting.value = true;
  try {
    await register({
      username: u,
      email: em,
      password: p,
      name: nm || null,
      student_id: isMerchant.value ? null : (sid || null),
      role: role.value,
    });
    await login(u, p);
    if (isMerchant.value) router.push('/merchant/dashboard');
    else router.push('/user/dashboard');
  } catch (e) {
    error.value = e.message || '注册失败';
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="modal">
      <div class="modal-head">
        <h2>注册账号</h2>
        <p>填写信息，即刻开始预约</p>
      </div>
      <div class="modal-body">
        <div class="role-tabs">
          <button class="role-tab" :class="{ active: !isMerchant }" @click="role = 'student'">用户注册</button>
          <button class="role-tab" :class="{ active: isMerchant }" @click="role = 'merchant'">商家注册</button>
        </div>
        <div class="form-field"><label>用户名</label><input type="text" class="form-input" v-model="username" placeholder="至少 3 位" autocomplete="off"></div>
        <div class="form-field"><label>{{ isMerchant ? '商家名称' : '姓名' }}</label><input type="text" class="form-input" v-model="name" :placeholder="isMerchant ? '请输入商家名称' : '请输入姓名'" autocomplete="off"></div>
        <div v-if="!isMerchant" class="form-field"><label>学号</label><input type="text" class="form-input" v-model="studentId" placeholder="请输入学号" autocomplete="off"></div>
        <div class="form-field"><label>邮箱</label><input type="text" class="form-input" v-model="email" placeholder="请输入邮箱" autocomplete="off"></div>
        <div class="form-field"><label>密码</label><input type="password" class="form-input" v-model="password" placeholder="至少 6 位" autocomplete="off"></div>
        <div class="form-error">{{ error }}</div>
      </div>
      <div class="modal-foot">
        <button class="btn btn-ghost" @click="router.push('/login')">返回登录</button>
        <button class="btn btn-primary" :disabled="submitting" @click="doRegister">注 册</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg);
  padding: 20px;
}
.role-tabs {
  display: flex;
  background: var(--border-soft);
  border-radius: var(--r);
  padding: 4px;
  margin-bottom: 16px;
}
.role-tab {
  flex: 1;
  padding: 8px 12px;
  border-radius: var(--r-sm);
  font-size: 14px;
  font-weight: 500;
  color: var(--text-2);
  transition: all .15s ease;
}
.role-tab.active {
  background: var(--card);
  color: var(--primary);
  box-shadow: var(--shadow-xs);
}
</style>
