<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuth, logout, userDisplayName, isAdmin } from '../composables/useAuth.js';
import { openAgent } from '../composables/useAgent.js';
import AgentDrawer from '../components/AgentDrawer.vue';
import ResultModal from '../components/ResultModal.vue';

const router = useRouter();
const route = useRoute();
const auth = useAuth();

const navGroups = [
  {
    label: '工作台',
    items: [
      { page: 'dashboard', icon: '🏠', label: '首页' },
      { page: 'booking', icon: '📅', label: '我要预约' },
      { page: 'reservations', icon: '📋', label: '我的预约' },
    ],
  },
  {
    label: '浏览',
    items: [{ page: 'scenarios', icon: '🎯', label: '预约场景' }],
  },
  {
    label: '账户',
    items: [{ page: 'profile', icon: '👤', label: '个人中心' }],
  },
];

const PAGE_META = {
  dashboard: ['首页', '查看你的预约数据与可预约场景'],
  booking: ['我要预约', '选择场景与资源，完成自助预约'],
  reservations: ['我的预约', '查看与管理你的预约记录'],
  scenarios: ['预约场景', '浏览可预约场景'],
  profile: ['个人中心', '查看与编辑个人信息'],
};

const currentPage = computed(() => route.path.split('/').pop());
const pageTitle = computed(() => (PAGE_META[currentPage.value] || ['', ''])[0]);
const pageSubtitle = computed(() => (PAGE_META[currentPage.value] || ['', ''])[1]);
const displayName = computed(() => userDisplayName());
const avatarChar = computed(() => displayName.value.charAt(0));
const roleText = computed(() => (isAdmin() ? '管理员' : '普通用户'));

const sidebar = ref(null);
const sidebarOpen = ref(false);
const dropdownOpen = ref(false);

function goPage(page) {
  router.push('/user/' + page);
  dropdownOpen.value = false;
  sidebarOpen.value = false;
}

function toggleSidebar() {
  sidebarOpen.value = !sidebarOpen.value;
}

function toggleDropdown(e) {
  e.stopPropagation();
  dropdownOpen.value = !dropdownOpen.value;
}

function closeDropdown() {
  dropdownOpen.value = false;
}

function doLogout() {
  logout();
  router.push('/login');
}

onMounted(() => document.addEventListener('click', closeDropdown));
onBeforeUnmount(() => document.removeEventListener('click', closeDropdown));
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar" :class="{ show: sidebarOpen }" ref="sidebar">
      <div class="sidebar-brand">
        <div class="brand-logo">约</div>
        <div class="brand-text">
          <span class="brand-name">智约</span>
          <span class="brand-sub">智能预约平台</span>
        </div>
      </div>
      <nav class="sidebar-nav">
        <div class="nav-group" v-for="g in navGroups" :key="g.label">
          <div class="nav-group-label">{{ g.label }}</div>
          <a class="nav-item" :class="{ active: currentPage === item.page }" v-for="item in g.items" :key="item.page" @click="goPage(item.page)">
            <span class="nav-icon">{{ item.icon }}</span><span class="nav-label">{{ item.label }}</span>
          </a>
        </div>
      </nav>
      <div class="sidebar-footer">
        <button class="agent-launch-btn" @click="openAgent">
          <span class="al-icon">🤖</span>
          <span class="al-text">
            <b>AI 智能助手</b>
            <small>自然语言预约 · 查询 · 取消</small>
          </span>
        </button>
      </div>
    </aside>

    <div class="main-area">
      <header class="topbar">
        <div class="topbar-left">
          <button class="icon-btn sidebar-toggle" title="收起菜单" @click="toggleSidebar">☰</button>
          <div class="page-title-wrap">
            <h1 class="page-title">{{ pageTitle }}</h1>
            <p class="page-subtitle">{{ pageSubtitle }}</p>
          </div>
        </div>
        <div class="topbar-right">
          <button class="icon-btn" title="AI 助手" @click="openAgent">🤖</button>
          <div class="user-chip" @click="toggleDropdown">
            <div class="user-avatar">{{ avatarChar }}</div>
            <div class="user-meta">
              <span class="user-name">{{ displayName }}</span>
              <span class="user-role">{{ roleText }}</span>
            </div>
            <span class="caret">▾</span>
          </div>
        </div>
      </header>

      <div class="user-dropdown" :class="{ show: dropdownOpen }">
        <div class="ud-head">
          <div class="user-avatar lg">{{ avatarChar }}</div>
          <div>
            <div class="ud-name">{{ displayName }}</div>
            <div class="ud-email">{{ auth.user ? (auth.user.email || '—') : '—' }}</div>
          </div>
        </div>
        <div class="ud-body">
          <button class="ud-item" @click="goPage('profile')">👤 个人中心</button>
          <button class="ud-item" @click="doLogout">🚪 退出登录</button>
        </div>
      </div>

      <main class="content">
        <router-view />
      </main>
    </div>
  </div>

  <AgentDrawer />
  <ResultModal />
</template>
