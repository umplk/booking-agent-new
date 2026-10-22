<script setup>
import { useRouter } from 'vue-router';
import { useAuth, logout, userDisplayName, isAdmin } from '../composables/useAuth.js';

defineProps({ title: { type: String, default: '页面' } });
const router = useRouter();
const auth = useAuth();

function doLogout() {
  logout();
  router.push('/login');
}
</script>

<template>
  <div class="pending-page">
    <div class="modal">
      <div class="modal-head">
        <h2>{{ title }}</h2>
        <p>该页面正在从原生前端迁移至 Vue 3，敬请期待</p>
      </div>
      <div class="modal-body">
        <div class="form-field"><label>当前用户</label><div class="form-input readonly">{{ userDisplayName() }}</div></div>
        <div class="form-field"><label>角色</label><div class="form-input readonly">{{ isAdmin() ? '管理员' : '普通用户' }}</div></div>
        <div class="form-field"><label>当前路径</label><div class="form-input readonly">{{ router.currentRoute.value.fullPath }}</div></div>
      </div>
      <div class="modal-foot">
        <button class="btn btn-ghost" @click="doLogout">🚪 退出登录</button>
        <button class="btn btn-primary" @click="router.push(isAdmin() ? '/merchant/dashboard' : '/user/dashboard')">返回首页</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pending-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg);
  padding: 20px;
}
.form-input.readonly {
  background: var(--border-soft);
  cursor: default;
}
</style>
