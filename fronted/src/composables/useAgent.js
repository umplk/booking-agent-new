/* AI 智能助手抽屉状态 —— 保留原 SSE 流式对话逻辑 */
import { reactive, nextTick } from 'vue';
import { API_BASE, getToken } from '../api/request.js';

const AGENT_API = '/api/agent/chat';

const state = reactive({
  open: false,
  messages: [],
  status: '在线 · 自然语言查询 / 预约 / 取消',
  sending: false,
});

export const SUGGESTIONS = ['帮我推荐一个安静靠窗的座位', '今天有哪些空闲资源', '怎么预约', '我的预约记录'];

export function useAgent() {
  return state;
}

export function openAgent() {
  state.open = true;
  if (!state.messages.length) {
    state.messages.push({ role: 'bot', text: '你好！我是 AI 智能预约助手 🤖\n你可以用自然语言让我帮你：查询可预约资源、推荐座位、创建或取消预约。\n试试下方建议问题吧～' });
  }
}

export function closeAgent() {
  state.open = false;
}

function getAgentSessionId() {
  let id = localStorage.getItem('agent_session_id');
  if (!id) {
    id = 'session_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8);
    localStorage.setItem('agent_session_id', id);
  }
  return id;
}

async function streamChat(text, onPartial) {
  const resp = await fetch(API_BASE + AGENT_API, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + getToken() },
    body: JSON.stringify({ message: text, session_id: getAgentSessionId() }),
  });
  if (!resp.ok) {
    let msg = 'HTTP ' + resp.status;
    try { const j = await resp.json(); if (j && j.message) msg = j.message; } catch (e) {}
    throw { message: msg };
  }
  if (!resp.body) throw { message: '浏览器不支持流式响应' };
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '', full = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n\n');
    buffer = parts.pop();
    for (const part of parts) {
      const line = part.trim();
      if (line.indexOf('data:') !== 0) continue;
      let payload;
      try { payload = JSON.parse(line.slice(5).trim()); } catch (e) { continue; }
      if (payload.error) throw { message: payload.error };
      if (payload.content) { full += payload.content; if (onPartial) onPartial(full); }
      if (payload.done) return full || '（无回复内容）';
    }
  }
  return full || '（无回复内容）';
}

export async function sendMessage(text) {
  text = (text || '').trim();
  if (!text || state.sending) return;
  state.messages.push({ role: 'user', text });
  state.sending = true;
  state.status = '思考中…';
  const thinking = reactive({ role: 'bot', text: '…' });
  state.messages.push(thinking);
  try {
    const reply = await streamChat(text, partial => { thinking.text = partial; });
    thinking.text = reply;
  } catch (e) {
    thinking.text = '⚠️ 智能体服务异常：' + (e.message || '未知错误') + '\n（请确认后端已启动并配置 DeepSeek API Key）';
  }
  state.status = '在线 · 自然语言查询 / 预约 / 取消';
  state.sending = false;
}
