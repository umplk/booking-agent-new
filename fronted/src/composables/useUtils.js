/* 工具函数 —— 从原 script.js 提取，保留原有格式化逻辑 */
export function fmtTime(t) { return t ? String(t).slice(0, 5) : ''; }
export function fmtDateTime(dt) { return dt ? String(dt).replace('T', ' ').slice(0, 16) : ''; }
export function isoDate(dt) { return dt ? String(dt).slice(0, 10) : ''; }
export function isoTime(dt) { return dt ? String(dt).slice(11, 16) : ''; }
export function todayStr() {
  const d = new Date();
  const p = n => n < 10 ? '0' + n : '' + n;
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate());
}
export function esc(str) {
  return String(str == null ? '' : str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
export function mergeSlots(freeSlots) {
  if (!freeSlots || !freeSlots.length) return [];
  const sorted = freeSlots.slice().sort((a, b) => a.start < b.start ? -1 : (a.start > b.start ? 1 : 0));
  const out = [];
  let start = sorted[0].start, prevEnd = sorted[0].end;
  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i].start === prevEnd) prevEnd = sorted[i].end;
    else { out.push({ start, end: prevEnd }); start = sorted[i].start; prevEnd = sorted[i].end; }
  }
  out.push({ start, end: prevEnd });
  return out;
}
export function statusText(s) {
  return ({ confirmed: '已确认', pending: '待确认', cancelled: '已取消', completed: '已完成' })[s] || s;
}
