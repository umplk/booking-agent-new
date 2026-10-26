/* 认证状态管理 —— 全局单例，保留原有接口与 token 逻辑 */
import { reactive } from 'vue';
import { apiFetch, setToken, clearToken, getToken } from '../api/request.js';

const state = reactive({
  user: null,
  loading: false,
});

export function useAuth() {
  return state;
}

export async function fetchMe() {
  state.user = await apiFetch('/api/users/me');
  return state.user;
}

export async function login(username, password) {
  const data = await apiFetch('/api/auth/login', { method: 'POST', body: { username, password } });
  setToken(data.access_token);
  await fetchMe();
  return state.user;
}

export async function register(payload) {
  await apiFetch('/api/auth/register', { method: 'POST', body: payload });
}

export function logout() {
  clearToken();
  state.user = null;
}

export function isLoggedIn() {
  return !!getToken();
}

export function isAdmin() {
  return state.user && state.user.role === 'admin';
}

export function isMerchant() {
  return state.user && (state.user.role === 'merchant' || state.user.role === 'admin');
}

export function userDisplayName() {
  return state.user ? (state.user.name || state.user.username) : '未登录';
}

export async function restoreSession() {
  const token = getToken();
  if (!token) return false;
  try {
    await fetchMe();
    return true;
  } catch (e) {
    clearToken();
    return false;
  }
}
