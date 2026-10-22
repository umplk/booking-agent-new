<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { register, login } from '../../composables/useAuth.js';

const router = useRouter();

const username = ref('');
const name = ref('');
const studentId = ref('');
const email = ref('');
const password = ref('');
const error = ref('');
const submitting = ref(false);

async function doRegister() {
  const u = username.value.trim();
  const nm = name.value.trim();
  const sid = studentId.value.trim();
  const em = email.value.trim();
  const p = password.value;
  if (!u || u.length < 3) { error.value = '用户名至少 3 位'; return; }
  if (!em) { error.value = '请输入邮箱'; return; }
  if (!p || p.length < 6) { error.value = '密码至少 6 位'; return; }
  error.value = '';
  submitting.value = true;
  try {
    await register({ username: u, email: em, password: p, name: nm || null, student_id: sid || null });
    await login(u, p);
    router.push('/user/dashboard');
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
        <div class="form-field"><label>用户名</label><input type="text" class="form-input" v-model="username" placeholder="至少 3 位" autocomplete="off"></div>
        <div class="form-field"><label>姓名</label><input type="text" class="form-input" v-model="name" placeholder="请输入姓名" autocomplete="off"></div>
        <div class="form-field"><label>学号</label><input type="text" class="form-input" v-model="studentId" placeholder="请输入学号" autocomplete="off"></div>
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
</style>
