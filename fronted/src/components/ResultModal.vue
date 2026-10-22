<script setup>
import { useResult, hideResult } from '../composables/useResult.js';
import { esc } from '../composables/useUtils.js';

const state = useResult();

function doAction() {
  hideResult();
  if (state.onAction) state.onAction();
}
function doClose() {
  hideResult();
  if (state.onClose) state.onClose();
}
</script>

<template>
  <div class="modal-overlay" v-if="state.visible">
    <div class="modal result-modal">
      <div class="result-icon" :class="state.type">{{ state.type === 'success' ? '✅' : '⚠️' }}</div>
      <h2>{{ state.title }}</h2>
      <p class="result-desc">{{ state.desc }}</p>
      <div class="result-detail" v-if="state.detail">
        <div class="row-item" v-for="d in state.detail" :key="d.k">
          <span>{{ d.k }}</span><span>{{ d.v }}</span>
        </div>
      </div>
      <div class="modal-foot">
        <button class="btn btn-ghost" @click="doClose">{{ state.closeText }}</button>
        <button class="btn btn-primary" @click="doAction">{{ state.actionText }}</button>
      </div>
    </div>
  </div>
</template>
