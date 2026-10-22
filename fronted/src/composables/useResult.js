/* 通用结果弹窗状态 —— 全局单例，替代原 showResult */
import { reactive } from 'vue';

const state = reactive({
  visible: false,
  type: '',
  title: '',
  desc: '',
  detail: null,
  actionText: '好的',
  closeText: '关闭',
  onAction: null,
  onClose: null,
});

export function showResult(opt) {
  state.type = opt.type || 'success';
  state.title = opt.title || '';
  state.desc = opt.desc || '';
  state.detail = opt.detail && opt.detail.length ? opt.detail : null;
  state.actionText = opt.actionText || '好的';
  state.closeText = opt.closeText || '关闭';
  state.onAction = opt.onAction || null;
  state.onClose = opt.onClose || null;
  state.visible = true;
}

export function hideResult() {
  state.visible = false;
}

export function useResult() {
  return state;
}
