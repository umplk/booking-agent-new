"""LLM 降级事件的可观测性：结构化日志 + 进程内计数 + 可选 Redis 持久累计 + 阈值告警。

降级吞掉异常是为了保证可用性，但如果不记录，就无法回答“最近降级了多少次、
集中在哪个环节、是不是 LLM 整体不可用”。

只记录三类信息：环节、原因（异常类名）、时间。detail 仅允许放非敏感的排障字段，
禁止写入用户原话或异常原文，避免隐私与密钥随 trace 扩散。
"""
import logging
import threading
import time
from collections import Counter, deque
from datetime import datetime, timezone
from typing import Dict, Optional

from app.utils import token_store

logger = logging.getLogger(__name__)

# 同一环节在窗口内降级达到阈值即告警一次，冷却期内不重复刷日志
ALERT_WINDOW_SECONDS = 300
ALERT_THRESHOLD = 5
ALERT_COOLDOWN_SECONDS = 300
RECENT_LIMIT = 50

STAGE_LABELS = {
    "intent": "意图识别",
    "slot": "槽位提取",
    "resource_spec": "资源参数解析",
    "resource_time": "开放时间解析",
    "sse": "Agent 会话",
}

_TOTAL_KEY = "agent:fallback:total"
_STAGE_KEY_PREFIX = "agent:fallback:stage:"

_lock = threading.Lock()
_total = 0
_by_stage: Counter = Counter()
_by_reason: Counter = Counter()
_recent: deque = deque(maxlen=RECENT_LIMIT)
_last_at: Optional[str] = None
_stage_events: Dict[str, deque] = {}
_last_alert: Dict[str, float] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def record_fallback(stage: str, reason: str, detail: Optional[dict] = None) -> None:
    """记录一次降级。detail 只放排障字段（如输入长度、异常类型），不要放用户原话。"""
    global _total, _last_at
    now = time.time()
    timestamp = _now_iso()
    safe_detail = dict(detail) if detail else None

    logger.warning(
        "fallback stage=%s reason=%s detail=%s",
        stage,
        reason,
        safe_detail if safe_detail else "-",
    )

    alert_count = 0
    with _lock:
        _total += 1
        _by_stage[stage] += 1
        _by_reason[reason] += 1
        _recent.append(
            {"at": timestamp, "stage": stage, "reason": reason, "detail": safe_detail}
        )
        _last_at = timestamp

        events = _stage_events.setdefault(stage, deque())
        events.append(now)
        while events and now - events[0] > ALERT_WINDOW_SECONDS:
            events.popleft()
        if (
            len(events) >= ALERT_THRESHOLD
            and now - _last_alert.get(stage, 0.0) >= ALERT_COOLDOWN_SECONDS
        ):
            _last_alert[stage] = now
            alert_count = len(events)

    if alert_count:
        logger.error(
            "fallback alert: stage=%s 在 %s 秒内降级 %s 次，LLM 可能整体不可用",
            stage,
            ALERT_WINDOW_SECONDS,
            alert_count,
        )

    # Redis 只做持久累计，失败不影响主流程；未配置 Redis 时返回 0
    token_store.incr_total(_TOTAL_KEY)
    token_store.incr_total(_STAGE_KEY_PREFIX + stage)


def snapshot() -> dict:
    """返回当前降级指标，供只读接口查询。"""
    with _lock:
        data = {
            "total": _total,
            "by_stage": dict(_by_stage),
            "by_reason": dict(_by_reason),
            "last_at": _last_at,
            "recent": list(_recent),
            "stage_labels": dict(STAGE_LABELS),
        }

    keys = set(_by_stage) | set(STAGE_LABELS)
    persistent_total = token_store.get_total(_TOTAL_KEY)
    data["persistent"] = None
    if persistent_total:
        data["persistent"] = {
            "total": persistent_total,
            "by_stage": {
                key: token_store.get_total(_STAGE_KEY_PREFIX + key) for key in sorted(keys)
            },
        }
    data["note"] = "total/by_stage 为进程内计数，重启清零；persistent 来自 Redis，未配置时为 null"
    return data


def reset() -> None:
    """清空进程内计数（测试用，不影响 Redis 历史累计）。"""
    global _total, _last_at
    with _lock:
        _total = 0
        _by_stage.clear()
        _by_reason.clear()
        _recent.clear()
        _stage_events.clear()
        _last_alert.clear()
        _last_at = None