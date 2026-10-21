from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from app.agent.classifier import chitchat_reply, detect_intent, extract_request
from app.agent.tools import (
    cancel_reservation,
    create_reservation,
    list_my_reservations,
    list_scenarios,
    query_availability,
)
from app.database import SessionLocal
from app.models.resource import Resource
from app.models.scenario import Scenario

REQUIRED_SLOTS = {
    "book": ["scenario_id", "resource_id", "date", "start_time", "end_time"],
    "cancel": ["reservation_id"],
    "query": ["scenario_id", "date"],
    "list_scenarios": [],
    "list_my": [],
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


def route_intent(state: dict) -> dict:
    text = ""
    for m in reversed(state.get("messages") or []):
        if getattr(m, "type", "") == "human":
            text = str(m.content) or ""
            break
    intent = detect_intent(text)
    prev_intent = state.get("intent")
    if intent == "chitchat" and prev_intent not in (None, "", "chitchat") and state.get("missing"):
        intent = prev_intent
    if intent == "chitchat":
        reply = chitchat_reply(text)
        return {"intent": intent, "reply": reply, "messages": [AIMessage(content=reply)]}
    return {"intent": intent, "reply": ""}


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
    else:
        result = "抱歉，我暂时无法处理这个操作。"
    return {"tool_result": result}


def respond(state: dict) -> dict:
    content = state.get("tool_result") or "处理完成。"
    return {"messages": [AIMessage(content=content)]}


def route_after_intent(state: dict) -> str:
    if state.get("reply"):
        return "done"
    return "proceed"


def slot_status(state: dict) -> str:
    return "missing" if state.get("missing") else "complete"