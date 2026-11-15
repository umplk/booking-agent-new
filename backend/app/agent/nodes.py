from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from app.agent.classifier import (
    apply_prev_intent,
    chitchat_reply,
    detect_intent_safe,
    extract_request,
)
from app.agent.tools import (
    cancel_reservation,
    create_reservation,
    generate_resources,
    list_my_reservations,
    list_scenarios,
    query_availability,
)
from app.database import SessionLocal
from app.models.resource import Resource
from app.models.scenario import Scenario
from app.utils.fallback_metrics import record_fallback

REQUIRED_SLOTS = {
    "book": ["scenario_id", "resource_id", "date", "start_time", "end_time"],
    "cancel": ["reservation_id"],
    "query": ["scenario_id", "date"],
    "list_scenarios": [],
    "list_my": [],
    "configure": ["scenario_id"],
}


def _history_text(state: dict) -> str:
    lines = []
    for m in state.get("messages") or []:
        kind = getattr(m, "type", "")
        content = str(getattr(m, "content", ""))
        if not content:
            continue
        if kind in ("human", "ai"):
            prefix = "用户" if kind == "human" else "助手"
            lines.append(f"{prefix}说：{content}")
    return "\n".join(lines)


def _resolve_scenario_id(db, keyword) -> int | None:
    if not keyword:
        return None
    kw = str(keyword).strip()
    if not kw:
        return None
    if kw.isdigit():
        row = db.query(Scenario).filter(Scenario.id == int(kw), Scenario.is_active == True).first()  # noqa: E712
        return row.id if row else None
    row = (
        db.query(Scenario)
        .filter(Scenario.is_active == True, Scenario.name.ilike(f"%{kw}%"))  # noqa: E712
        .first()
    )
    return row.id if row else None


def _resolve_resource_id(db, scenario_id, keyword) -> int | None:
    if not keyword:
        return None
    kw = str(keyword).strip()
    if not kw:
        return None
    if kw.isdigit():
        row = db.query(Resource).filter(
            Resource.id == int(kw),
            Resource.scenario_id == scenario_id,
            Resource.is_active == True,  # noqa: E712
        ).first()
        return row.id if row else None
    row = (
        db.query(Resource)
        .filter(
            Resource.scenario_id == scenario_id,
            Resource.is_active == True,  # noqa: E712
            (Resource.name.ilike(f"%{kw}%")) | (Resource.code.ilike(f"%{kw}%")),
        )
        .first()
    )
    return row.id if row else None


_AFFIRMATIVE_WORDS = (
    "确认", "确定", "是的", "是", "对的", "对", "好的", "好", "可以", "没问题",
    "执行", "yes", "y", "ok", "yeah",
)
_NEGATIVE_WORDS = (
    "不", "否", "不要", "不行", "算了", "放弃", "作废", "no", "n", "cancel",
    "取消",
)
_STRONG_CONFIRM_WORDS = ("确认", "确定", "执行")


def _is_affirmative(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    has_confirm = any(w in t for w in _STRONG_CONFIRM_WORDS)
    if not has_confirm and any(w in t for w in _NEGATIVE_WORDS):
        return False
    return any(w in t for w in _AFFIRMATIVE_WORDS)


def _is_negative(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    if any(w in t for w in _STRONG_CONFIRM_WORDS):
        return False
    return any(w in t for w in _NEGATIVE_WORDS)


def _last_human_text(state: dict) -> str:
    for m in reversed(state.get("messages") or []):
        if getattr(m, "type", "") == "human":
            return str(m.content) or ""
    return ""


_CLARIFY_INTENTS = {"book", "cancel", "configure"}

_CLARIFY_PROMPT = (
    "我不太确定你的意思，先确认再执行。你是想：\n"
    "1. 预约\n"
    "2. 查询空闲\n"
    "3. 取消预约\n"
    "4. 查看我的预约\n"
    "5. 查看场景\n"
    "6. 批量生成资源（商家）\n"
    '直接回复序号或关键词即可，例如"1"或"预约"。'
)

_CLARIFY_KEYWORDS = (
    ("cancel", ("取消", "退订", "作废")),
    ("list_my", ("我的预约", "预约记录", "我的记录")),
    ("list_scenarios", ("场景", "有哪些", "能约什么")),
    ("configure", ("生成资源", "批量生成", "配置资源", "新建资源")),
    ("query", ("查询", "查一下", "空闲", "有没有", "空位", "能约吗")),
    ("book", ("预约", "订", "约个", "book")),
)

_CLARIFY_NUMBERS = {
    "1": "book",
    "2": "query",
    "3": "cancel",
    "4": "list_my",
    "5": "list_scenarios",
    "6": "configure",
}


def _match_clarified_intent(text: str) -> str | None:
    t = (text or "").strip().lower()
    if not t:
        return None
    if t in _CLARIFY_NUMBERS:
        return _CLARIFY_NUMBERS[t]
    for intent, keywords in _CLARIFY_KEYWORDS:
        if any(k in t for k in keywords):
            return intent
    return None


def route_intent(state: dict) -> dict:
    if state.get("pending_confirmation"):
        text = _last_human_text(state)
        if _is_affirmative(text):
            return {"pending_confirmation": False, "confirmed": True, "reply": ""}
        if _is_negative(text):
            reply = "好的，已取消本次操作。"
            return {
                "pending_confirmation": False,
                "confirmed": False,
                "intent": "chitchat",
                "reply": reply,
                "messages": [AIMessage(content=reply)],
            }
        reply = '请明确回复"确认"执行或"取消"放弃。'
        return {"reply": reply, "messages": [AIMessage(content=reply)]}

    if state.get("pending_clarification"):
        text = _last_human_text(state)
        matched = _match_clarified_intent(text)
        if matched:
            return {
                "pending_clarification": False,
                "intent_degraded": False,
                "intent": matched,
                "reply": "",
            }
        reply = (
            "请直接回复：1 预约 / 2 查询空闲 / 3 取消预约 / "
            "4 查看我的预约 / 5 查看场景。"
        )
        return {
            "pending_clarification": False,
            "intent_degraded": False,
            "intent": "chitchat",
            "reply": reply,
            "messages": [AIMessage(content=reply)],
        }

    text = _last_human_text(state)
    prev_intent = state.get("intent")
    raw_intent, degraded = detect_intent_safe(text)
    intent = apply_prev_intent(raw_intent, prev_intent, state.get("missing"))
    if degraded and raw_intent == intent and intent in _CLARIFY_INTENTS:
        record_fallback("clarify", "intent_degraded", {"guessed_intent": intent})
        return {
            "intent": intent,
            "intent_degraded": True,
            "pending_clarification": True,
            "reply": _CLARIFY_PROMPT,
            "messages": [AIMessage(content=_CLARIFY_PROMPT)],
        }
    if intent == "chitchat":
        reply = chitchat_reply(text)
        return {
            "intent": intent,
            "intent_degraded": degraded,
            "reply": reply,
            "messages": [AIMessage(content=reply)],
        }
    return {"intent": intent, "intent_degraded": degraded, "reply": ""}


def _all_human_text(state: dict) -> str:
    parts = []
    for m in state.get("messages") or []:
        if getattr(m, "type", "") == "human":
            parts.append(str(m.content) or "")
    return "\n".join(parts)


def extract_slots(state: dict) -> dict:
    intent = state.get("intent")
    merged = dict(state.get("slots") or {})
    history = _history_text(state)
    if intent in ("book", "cancel", "query"):
        parsed = extract_request(intent, history)
        for key in ("date", "start_time", "end_time", "scenario_query", "resource_query", "reservation_id"):
            value = parsed.get(key)
            if value is not None and str(value).strip() not in ("", "None"):
                merged[key] = str(value).strip() if not isinstance(value, int) else value

    db = SessionLocal()
    try:
        all_text = _all_human_text(state)
        scenarios = (
            db.query(Scenario)
            .filter(Scenario.is_active == True)  # noqa: E712
            .all()
        )
        if merged.get("scenario_id") is None:
            keyword = merged.get("scenario_query")
            resolved = _resolve_scenario_id(db, keyword)
            if not resolved:
                for s in sorted(scenarios, key=lambda x: len(x.name), reverse=True):
                    if s.name and s.name in all_text:
                        resolved = s.id
                        merged["scenario_query"] = s.name
                        break
            if resolved:
                merged["scenario_id"] = resolved
        scenario_id = merged.get("scenario_id")
        if merged.get("resource_id") is None:
            keyword = merged.get("resource_query")
            resolved = _resolve_resource_id(db, scenario_id, keyword) if scenario_id else None
            if not resolved:
                resources = (
                    db.query(Resource)
                    .filter(Resource.is_active == True)  # noqa: E712
                    .all()
                )
                for r in sorted(resources, key=lambda x: len(x.name or ""), reverse=True):
                    if scenario_id is not None and r.scenario_id != scenario_id:
                        continue
                    if (r.code and r.code in all_text) or (r.name and r.name in all_text):
                        resolved = r.id
                        merged["resource_query"] = r.code or r.name
                        if scenario_id is None:
                            merged["scenario_id"] = r.scenario_id
                        break
            if resolved:
                merged["resource_id"] = resolved
    finally:
        db.close()

    missing = []
    for field in REQUIRED_SLOTS.get(intent, []):
        value = merged.get(field)
        if value is None or str(value).strip() == "":
            missing.append(field)

    return {"slots": merged, "missing": missing}


_ASK_PROMPTS = {
    "scenario_id": "请选择要预约的场景",
    "resource_id": "请选择具体资源",
    "date": "请问预约哪一天",
    "start_time": "请问开始时间",
    "end_time": "请问结束时间",
    "reservation_id": "请提供要取消的预约号",
}


def ask_missing(state: dict, config: RunnableConfig) -> dict:
    missing = state.get("missing") or []
    questions = [_ASK_PROMPTS[f] for f in missing if f in _ASK_PROMPTS]
    parts = []
    if "scenario_id" in missing:
        parts.append(f"目前开放的场景如下：\n{list_scenarios.invoke({})}")
    if "reservation_id" in missing:
        c = {"configurable": config["configurable"]}
        parts.append(f"你当前的预约如下：\n{list_my_reservations.invoke({}, config=c)}")
    question = "，".join(questions) + "。"
    content = "\n\n".join(["为了完成这个操作，" + question] + parts)
    return {"messages": [AIMessage(content=content)]}


def call_tool(state: dict, config: RunnableConfig) -> dict:
    intent = state["intent"]
    slots = state.get("slots") or {}
    c = {"configurable": config["configurable"]}
    if intent == "book":
        result = create_reservation.invoke(
            {
                "scenario_id": slots["scenario_id"],
                "resource_id": slots["resource_id"],
                "date": slots["date"],
                "start_time": slots["start_time"],
                "end_time": slots["end_time"],
            },
            config=c,
        )
    elif intent == "cancel":
        result = cancel_reservation.invoke({"reservation_id": slots["reservation_id"]}, config=c)
    elif intent == "query":
        result = query_availability.invoke(
            {
                "scenario_id": slots["scenario_id"],
                "date": slots["date"],
                "start_time": slots.get("start_time", ""),
                "end_time": slots.get("end_time", ""),
            }
        )
    elif intent == "list_scenarios":
        result = list_scenarios.invoke({})
    elif intent == "list_my":
        result = list_my_reservations.invoke({}, config=c)
    elif intent == "configure":
        description = ""
        for m in reversed(state.get("messages") or []):
            if getattr(m, "type", "") == "human":
                description = str(m.content) or ""
                break
        result = generate_resources.invoke(
            {"scenario_id": slots["scenario_id"], "description": description},
            config=c,
        )
    else:
        result = "抱歉，我暂时无法处理这个操作。"
    return {"tool_result": result, "confirmed": False, "pending_confirmation": False}


def respond(state: dict) -> dict:
    content = state.get("tool_result") or "处理完成。"
    return {"messages": [AIMessage(content=content)]}


def confirm(state: dict) -> dict:
    intent = state.get("intent")
    slots = state.get("slots") or {}
    db = SessionLocal()
    try:
        if intent == "book":
            scenario = db.query(Scenario).filter(Scenario.id == slots.get("scenario_id")).first()
            resource = db.query(Resource).filter(Resource.id == slots.get("resource_id")).first()
            scenario_name = scenario.name if scenario else slots.get("scenario_id")
            resource_name = resource.name if resource else slots.get("resource_id")
            content = (
                "请确认以下预约信息：\n"
                f"  场景：{scenario_name}\n"
                f"  资源：{resource_name}\n"
                f"  日期：{slots.get('date')}\n"
                f"  时间：{slots.get('start_time')} - {slots.get('end_time')}\n\n"
                '回复"确认"执行预约，"取消"放弃。'
            )
        elif intent == "cancel":
            content = (
                f"请确认是否取消预约号 {slots.get('reservation_id')}？\n"
                '回复"确认"执行取消，"取消"放弃。'
            )
        else:
            content = '请确认是否执行该操作？回复"确认"或"取消"。'
    finally:
        db.close()
    return {"pending_confirmation": True, "messages": [AIMessage(content=content)]}


def route_after_intent(state: dict) -> str:
    if state.get("reply"):
        return "done"
    return "proceed"


def slot_status(state: dict) -> str:
    if state.get("missing"):
        return "missing"
    if state.get("confirmed"):
        return "complete"
    if state.get("intent") in ("book", "cancel"):
        return "confirm"
    return "complete"