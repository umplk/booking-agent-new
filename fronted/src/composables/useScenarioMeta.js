export const SCENARIO_CATEGORIES = [
  { value: 'study_room', label: '自习室', icon: '📚' },
  { value: 'meeting_room', label: '会议室', icon: '💼' },
  { value: 'sports', label: '运动场馆', icon: '🏸' },
  { value: 'fitness', label: '健身房', icon: '💪' },
  { value: 'workspace', label: '共享空间', icon: '💻' },
  { value: 'other', label: '其他', icon: '🎯' },
];

export const SCENARIO_TEMPLATES = [
  {
    key: 'study_room',
    name: '自习室座位预约',
    category: 'study_room',
    icon: '📚',
    tags: '安静,插座,靠窗',
    description: '图书馆/自习室座位分时段预约',
    booking_notice: '请保持安静，离座超过 30 分钟请办理暂离。',
    rules: { time_step_minutes: 30, min_duration_minutes: 30, max_duration_minutes: 240, max_advance_days: 30, min_advance_minutes: 30, allow_same_day: true, max_active_per_user: 3, max_minutes_per_day: 480, cancel_before_minutes: 30 },
  },
  {
    key: 'meeting_room',
    name: '会议室预约',
    category: 'meeting_room',
    icon: '💼',
    tags: '投影仪,白板,视频会议',
    description: '不同容量会议室分时段预约',
    booking_notice: '请提前 10 分钟到场，会后请恢复桌椅并关闭设备。',
    rules: { time_step_minutes: 30, min_duration_minutes: 30, max_duration_minutes: 180, max_advance_days: 30, min_advance_minutes: 0, allow_same_day: true, max_active_per_user: 2, max_minutes_per_day: 240, cancel_before_minutes: 60 },
  },
  {
    key: 'sports',
    name: '羽毛球场地预约',
    category: 'sports',
    icon: '🏸',
    tags: '室内,灯光,木地板',
    description: '室内运动场地按小时预约',
    booking_notice: '请自备球拍并穿运动鞋入场，结束后请带走个人物品。',
    rules: { time_step_minutes: 60, min_duration_minutes: 60, max_duration_minutes: 120, max_advance_days: 7, min_advance_minutes: 0, allow_same_day: true, max_active_per_user: 2, max_minutes_per_day: 180, cancel_before_minutes: 120 },
  },
  {
    key: 'fitness',
    name: '健身房器械预约',
    category: 'fitness',
    icon: '💪',
    tags: '器械,空调,免费',
    description: '跑步机、椭圆机与力量器械分时段预约',
    booking_notice: '请先热身并使用毛巾，器械使用后请擦拭归位。',
    rules: { time_step_minutes: 30, min_duration_minutes: 30, max_duration_minutes: 90, max_advance_days: 3, min_advance_minutes: 0, allow_same_day: true, max_active_per_user: 1, max_minutes_per_day: 90, cancel_before_minutes: 30 },
  },
  {
    key: 'workspace',
    name: '共享工位预约',
    category: 'workspace',
    icon: '💻',
    tags: '工位,独立空间,高速网络',
    description: '开放式与安静区共享工位按小时预约',
    booking_notice: '离开超过 30 分钟请办理暂离，贵重物品请随身携带。',
    rules: { time_step_minutes: 60, min_duration_minutes: 60, max_duration_minutes: 480, max_advance_days: 14, min_advance_minutes: 0, allow_same_day: true, max_active_per_user: 1, max_minutes_per_day: 480, cancel_before_minutes: 60 },
  },
];

export function categoryLabel(value) {
  const item = SCENARIO_CATEGORIES.find(c => c.value === value);
  return item ? item.label : '其他';
}

export function categoryIcon(value) {
  const item = SCENARIO_CATEGORIES.find(c => c.value === value);
  return item ? item.icon : '🎯';
}

export function splitTags(tags) {
  return (tags || '').split(/[,，]/).map(t => t.trim()).filter(Boolean);
}