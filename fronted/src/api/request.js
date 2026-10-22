/* API 配置与请求封装 —— 保留原有后端绝对地址与请求逻辑 */
export const API_BASE = 'http://127.0.0.1:8000';

export function getToken() { return localStorage.getItem('token') || ''; }
export function setToken(t) { localStorage.setItem('token', t); }
export function clearToken() { localStorage.removeItem('token'); }

export async function apiFetch(path, options) {
  options = options || {};
  options.headers = options.headers || {};
  const token = getToken();
  if (token) options.headers['Authorization'] = 'Bearer ' + token;
  if (options.body && typeof options.body !== 'string') {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }
  let resp;
  try { resp = await fetch(API_BASE + path, options); }
  catch (e) { throw { message: '无法连接服务器，请检查后端是否启动' }; }
  let json;
  try { json = await resp.json(); }
  catch (e) { throw { message: '服务器返回格式错误（HTTP ' + resp.status + '）' }; }
  if (json.code && json.code !== 200) throw { message: json.message || '请求失败', code: json.code };
  if (!resp.ok) throw { message: json.message || ('HTTP ' + resp.status), code: resp.status };
  return json.data;
}
