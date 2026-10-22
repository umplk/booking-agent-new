/* 场景编辑弹窗状态 —— 全局单例 */
import { reactive } from 'vue';

const state = reactive({
  open: false,
  editing: null,
  onSaved: null,
});

export function openScenarioModal(s, onSaved) {
  state.editing = s || null;
  state.onSaved = onSaved || null;
  state.open = true;
}

export function closeScenarioModal() {
  state.open = false;
}

export function useScenarioModal() {
  return state;
}
