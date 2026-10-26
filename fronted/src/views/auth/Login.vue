<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { login, useAuth } from '../../composables/useAuth.js';

const router = useRouter();
const auth = useAuth();

const username = ref('');
const password = ref('');
const error = ref('');
const submitting = ref(false);

async function doLogin() {
  const u = username.value.trim();
  const p = password.value;
  if (!u) { error.value = '请输入用户名'; return; }
  if (!p) { error.value = '请输入密码'; return; }
  error.value = '';
  submitting.value = true;
  try {
    const user = await login(u, p);
    if (user && (user.role === 'admin' || user.role === 'merchant')) router.push('/merchant/dashboard');
    else router.push('/user/dashboard');
  } catch (e) {
    error.value = e.message || '登录失败';
  } finally {
    submitting.value = false;
  }
}

function onKeydown(e) {
  if (e.key === 'Enter') doLogin();
}
</script>

<template>
  <div class="auth-page">
    <div class="modal">
      <div class="modal-head">
        <h2>登录智约平台</h2>
        <p>输入账号密码，开启智能预约</p>
      </div>
      <div class="modal-body">
        <div class="form-field">
          <label>用户名</label>
          <input type="text" class="form-input" v-model="username" placeholder="请输入用户名" autocomplete="off" @keydown="onKeydown">
        </div>
        <div class="form-field">
          <label>密码</label>
          <input type="password" class="form-input" v-model="password" placeholder="请输入密码" autocomplete="off" @keydown="onKeydown">
        </div>
        <div class="form-error">{{ error }}</div>
      </div>
      <div class="modal-foot">
        <button class="btn btn-ghost" @click="router.push('/register')">没有账号？去注册</button>
        <button class="btn btn-primary" :disabled="submitting" @click="doLogin">登 录</button>
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
