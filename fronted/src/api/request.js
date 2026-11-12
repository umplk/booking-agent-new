/* API 配置与请求封装 —— 双 Token（access + refresh）与 401 单飞刷新 */
export const API_BASE = 'http://127.0.0.1:8000';

const ACCESS_KEY = 'token';
const REFRESH_KEY = 'refresh_token';
const REFRESH_AHEAD_MS = 60 * 1000;

export function getToken() { return localStorage.getItem(ACCESS_KEY) || ''; }
export function getRefreshToken() { return localStorage.getItem(REFRESH_KEY) || ''; }
export function setToken(t) { localStorage.setItem(ACCESS_KEY, t); }
export function setTokens(access, refresh) {
  if (access) localStorage.setItem(ACCESS_KEY, access);
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
}
export function clearToken() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

function parseExpiry(token) {
  try {
    const segment = token.split('.')[1];
    if (!segment) return 0;
    let base64 = segment.replace(/-/g, '+').replace(/_/g, '/');
    base64 += '='.repeat((4 - (base64.length % 4)) % 4);
    const binary = atob(base64);
    const bytes = Uint8Array.from(binary, c => c.charCodeAt(0));
    const payload = JSON.parse(new TextDecoder().decode(bytes));
    return (payload.exp || 0) * 1000;
  } catch (e) { return 0; }
}

let refreshPromise = null;

export function refreshSession() {
  if (refreshPromise) return refreshPromise;
  const refreshToken = getRefreshToken();
  if (!refreshToken) return Promise.reject(new Error('缺少刷新令牌'));
  refreshPromise = fetch(API_BASE + '/api/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
    .then(async resp => {
      const json = await resp.json().catch(() => null);
      if (!resp.ok || !json) throw new Error((json && json.message) || '刷新令牌失败');
      const data = json.data || json;
      if (!data.access_token) throw new Error('刷新令牌失败');
      setTokens(data.access_token, data.refresh_token);
      return data.access_token;
    })
    .finally(() => { refreshPromise = null; });
  return refreshPromise;
}

export async function ensureFreshToken() {
  const token = getToken();
  if (!token) return '';
  const expiresAt = parseExpiry(token);
  if (expiresAt && expiresAt - Date.now() > REFRESH_AHEAD_MS) return token;
  if (!getRefreshToken()) return token;
  try { return await refreshSession(); }
  catch (e) { return token; }
}

function isAuthEndpoint(path) {
  return /^\/api\/auth\/(login|token|register|refresh)$/.test(path);
}

function redirectToLogin() {
  if (location.pathname !== '/login') location.href = '/login';
}

async function send(path, options, token, allowRefresh) {
  const opts = { ...options, headers: { ...(options.headers || {}) } };
  if (token) opts.headers['Authorization'] = 'Bearer ' + token;
  if (opts.body && typeof opts.body !== 'string') {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(opts.body);
  }
  let resp;
  try { resp = await fetch(API_BASE + path, opts); }
  catch (e) { throw { message: '无法连接服务器，请检查后端是否启动' }; }
  let json;
  try { json = await resp.json(); }
  catch (e) { throw { message: '服务器返回格式错误（HTTP ' + resp.status + '）' }; }

  if (resp.status === 401) {
    if (allowRefresh && !isAuthEndpoint(path) && getRefreshToken()) {
      try {
        const fresh = await refreshSession();
        return await send(path, options, fresh, false);
      } catch (e) { /* 刷新失败走下方统一登出 */ }
    }
    clearToken();
    redirectToLogin();
    throw { message: (json && json.message) || '登录状态已失效', code: 401 };
  }
  if (json && json.code && json.code !== 200) throw { message: json.message || '请求失败', code: json.code };
  if (!resp.ok) throw { message: (json && json.message) || ('HTTP ' + resp.status), code: resp.status };
  return json.data;
}

export async function apiFetch(path, options) {
  const token = await ensureFreshToken();
  return send(path, options || {}, token, true);
}