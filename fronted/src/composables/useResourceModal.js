/* 资源编辑弹窗状态 —— 全局单例 */
import { reactive } from 'vue';

const state = reactive({
  open: false,
  editing: null,
  scenario: null,
  onSaved: null,
});

export function openResourceModal(r, scenario, onSaved) {
  state.editing = r || null;
  state.scenario = scenario || null;
  state.onSaved = onSaved || null;
  state.open = true;
}

export function closeResourceModal() {
  state.open = false;
}

export function useResourceModal() {
  return state;
}
