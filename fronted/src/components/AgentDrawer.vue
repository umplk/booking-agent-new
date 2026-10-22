<script setup>
import { ref } from 'vue';
import { useAgent, openAgent, closeAgent, sendMessage, SUGGESTIONS } from '../composables/useAgent.js';

const state = useAgent();
const input = ref('');

function onSend() {
  if (!input.value.trim()) return;
  sendMessage(input.value);
  input.value = '';
}
function onSuggest(s) {
  input.value = s;
  onSend();
}
function onKeydown(e) {
  if (e.key === 'Enter') onSend();
}
</script>

<template>
  <div class="agent-drawer" :class="{ show: state.open }">
    <div class="agent-drawer-head">
      <div class="ad-title">
        <span class="ad-avatar">🤖</span>
        <div>
          <b>AI 智能预约助手</b>
          <small>{{ state.status }}</small>
        </div>
      </div>
      <button class="icon-btn" title="关闭" @click="closeAgent">✕</button>
    </div>
    <div class="agent-drawer-body">
      <div class="agent-msg" :class="m.role" v-for="(m, i) in state.messages" :key="i">{{ m.text }}</div>
    </div>
    <div class="agent-drawer-foot">
      <div class="agent-suggest">
        <button v-for="s in SUGGESTIONS" :key="s" @click="onSuggest(s)">{{ s }}</button>
      </div>
      <div class="agent-input-row">
        <input type="text" v-model="input" placeholder="如：帮我预约明天 10-12 点靠窗的座位" autocomplete="off" @keydown="onKeydown">
        <button class="btn btn-primary" :disabled="state.sending" @click="onSend">发送</button>
      </div>
    </div>
  </div>
  <div class="agent-drawer-mask" :class="{ show: state.open }" @click="closeAgent"></div>
</template>
