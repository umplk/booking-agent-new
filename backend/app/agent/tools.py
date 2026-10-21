from datetime import date, datetime, time
from typing import Optional

from fastapi import HTTPException
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.database import SessionLocal
from app.models.reservation import Reservation
from app.models.resource import Resource
from app.models.scenario import Scenario
from app.models.user import User
from app.services.booking_service import (
    cancel_reservation as booking_cancel,
    create_reservation as booking_create,
    query_availability as booking_availability,
)
from app.services.resource_generator import generate_resources as _generate_resources_impl

##庄子欣
def _parse_date(value: str) -> Optional[date]:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _parse_time(value: str) -> Optional[time]:
    try:
        return time.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")


def _http_message(exc: HTTPException) -> str:
    return f"操作未通过业务校验：{exc.detail}"


def _slots_to_ranges(free_slots: list) -> str:
    if not free_slots:
        return "无"
    ranges = []
    start = free_slots[0].start
    prev_end = free_slots[0].end
    for slot in free_slots[1:]:
        if slot.start == prev_end:
            prev_end = slot.end
        else:
            ranges.append(f"{start}-{prev_end}")
            start = slot.start
            prev_end = slot.end
    ranges.append(f"{start}-{prev_end}")
    return "、".join(ranges)


@tool
def get_current_datetime() -> str:
    """获取当前日期、星期和时间，用于把"今天/明天/后天/下周几"等相对时间换算成具体日期（YYYY-MM-DD）。"""
    now = datetime.now()
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return f"当前日期：{now.date()}（{weekdays[now.weekday()]}），当前时间：{now.strftime('%H:%M')}"


@tool
def list_scenarios() -> str:
    """列出所有开放中的预约场景（自习室、会议室等），包含场景 ID、名称和时间规则。"""
    db = SessionLocal()
    try:
        scenarios = db.query(Scenario).filter(Scenario.is_active == True).all()  # noqa: E712
        if not scenarios:
            return "当前没有开放的预约场景。"
        lines = ["开放的预约场景："]
        for s in scenarios:
            parts = [
                f"步长{s.time_step_minutes}分钟",
                f"时长{s.min_duration_minutes}-{s.max_duration_minutes}分钟",
                f"最多提前{s.max_advance_days}天",
                "可当日预约" if s.allow_same_day else "不可当日预约",
                f"每人最多{s.max_active_per_user}个活跃预约",
            ]
            if s.min_advance_minutes and s.min_advance_minutes > 0:
                parts.append(f"至少提前{s.min_advance_minutes}分钟")
            if s.max_minutes_per_day is not None:
                parts.append(f"每日每人最多{s.max_minutes_per_day}分钟")
            if s.cancel_before_minutes is not None:
                parts.append(f"需提前{s.cancel_before_minutes}分钟取消")
            rules = "，".join(parts)
            lines.append(f"scenario_id={s.id} | {s.name}" + (f" | {s.description}" if s.description else "") + f" | {rules}")
        return "\n".join(lines)
    finally:
        db.close()


@tool
def query_availability(
    scenario_id: int,
    date: str,
    start_time: str = "",
    end_time: str = "",
) -> str:
    """查询指定场景（scenario_id）在指定日期（YYYY-MM-DD）下各资源的可预约时段，可选起止时间（HH:MM）收窄范围。"""
    target_date = _parse_date(date)
    if target_date is None:
        return "日期格式不正确，请使用 YYYY-MM-DD 格式。"
    range_start = _parse_time(start_time) if start_time else None
    range_end = _parse_time(end_time) if end_time else None
    db = SessionLocal()
    try:
        try:
            result = booking_availability(db, scenario_id, target_date, range_start, range_end)
        except HTTPException as exc:
            return _http_message(exc)
        scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
        name = scenario.name if scenario else f"场景{scenario_id}"
        lines = [
            f"{name} 在 {target_date} 的可预约时段"
            + (f"（限定 {range_start.strftime('%H:%M')}-{range_end.strftime('%H:%M')}）" if range_start else "")
            + "："
        ]
        for r in result["resources"]:
            slots_text = _slots_to_ranges(r.free_slots)
            lines.append(f"resource_id={r.resource_id} | {r.code} | {r.name} | 可约: {slots_text}")
        if result["free_slots_count"] == 0:
            lines.append("当天没有任何可预约时段。")
        return "\n".join(lines)
    finally:
        db.close()


@tool
def create_reservation(
    scenario_id: int,
    resource_id: int,
    date: str,
    start_time: str,
    end_time: str,
    *,
    config: RunnableConfig,
) -> str:
    """为用户创建一条预约：指定场景、资源、日期（YYYY-MM-DD）、起止时间（HH:MM）。所有规则校验由后端统一完成。"""
    target_date = _parse_date(date)
    start = _parse_time(start_time)
    end = _parse_time(end_time)
    if target_date is None:
        return "预约日期格式不正确，请使用 YYYY-MM-DD 格式。"
    if start is None or end is None:
        return "时间格式不正确，请使用 HH:MM 格式。"
    user_id = config["configurable"].get("user_id")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return "无法确认登录用户身份，请重新登录后再试。"
        try:
            reservation = booking_create(
                db,
                user,
                scenario_id,
                resource_id,
                datetime.combine(target_date, start),
                datetime.combine(target_date, end),
            )
        except HTTPException as exc:
            return _http_message(exc)
        scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
        resource = db.query(Resource).filter(Resource.id == resource_id).first()
        return (
            f"预约成功！预约号 {reservation.id}："
            f"{scenario.name if scenario else scenario_id} {resource.name if resource else resource_id}，"
            f"{_fmt(reservation.start_time)}-{_fmt(reservation.end_time)}。"
        )
    finally:
        db.close()


@tool
def list_my_reservations(*, config: RunnableConfig) -> str:
    """查询当前登录用户的全部有效预约记录。"""
    user_id = config["configurable"].get("user_id")
    db = SessionLocal()
    try:
        rows = (
            db.query(Reservation)
            .filter(Reservation.user_id == user_id, Reservation.status.in_(["confirmed"]))
            .order_by(Reservation.start_time.asc())
            .all()
        )
        if not rows:
            return "你当前没有有效预约。"
        lines = ["你的有效预约："]
        status_text = {"confirmed": "已确认", "pending": "待确认", "cancelled": "已取消", "completed": "已完成"}
        for r in rows:
            scenario = db.query(Scenario).filter(Scenario.id == r.scenario_id).first()
            resource = db.query(Resource).filter(Resource.id == r.resource_id).first()
            lines.append(
                f"预约号 {r.id} | {scenario.name if scenario else r.scenario_id} "
                f"{resource.name if resource else r.resource_id} | {_fmt(r.start_time)}-{_fmt(r.end_time)} "
                f"| {status_text.get(r.status, r.status)}"
            )
        return "\n".join(lines)
    finally:
        db.close()


@tool
def cancel_reservation(reservation_id: int, *, config: RunnableConfig) -> str:
    """取消指定预约号的预约，只能取消自己的预约，后端统一校验取消规则。"""
    user_id = config["configurable"].get("user_id")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return "无法确认登录用户身份，请重新登录后再试。"
        try:
            reservation = booking_cancel(db, user, reservation_id)
        except HTTPException as exc:
            return _http_message(exc)
        scenario = db.query(Scenario).filter(Scenario.id == reservation.scenario_id).first()
        resource = db.query(Resource).filter(Resource.id == reservation.resource_id).first()
        return (
            f"预约号 {reservation_id} 已成功取消："
            f"{scenario.name if scenario else reservation.scenario_id} "
            f"{resource.name if resource else reservation.resource_id}，"
            f"{_fmt(reservation.start_time)}-{_fmt(reservation.end_time)}。"
        )
    finally:
        db.close()


@tool
def generate_resources(scenario_id: int, description: str, *, config: RunnableConfig) -> str:
    """根据自然语言描述在指定场景下批量生成资源。description 例如「5个羽毛球场地，9-22点开放」或「3间会议室」。仅场景拥有者或管理员可操作。"""
    user_id = config["configurable"].get("user_id")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return "无法确认登录用户身份，请重新登录后再试。"
        scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
        if not scenario:
            return f"场景 {scenario_id} 不存在。"
        if user.role != "admin" and (scenario.owner_id is None or scenario.owner_id != user.id):
            return "你无权在该场景下生成资源。"
        created = _generate_resources_impl(db, scenario, description)
        if not created:
            return "未生成新资源，可能编号已全部存在。"
        lines = [f"已在场景「{scenario.name}」下生成 {len(created)} 个资源："]
        for r in created:
            lines.append(
                f"resource_id={r.id} | {r.code} | {r.name} | "
                f"{r.open_start.strftime('%H:%M')}-{r.open_end.strftime('%H:%M')}"
            )
        return "\n".join(lines)
    finally:
        db.close()


TOOLS = [
    get_current_datetime,
    list_scenarios,
    query_availability,
    create_reservation,
    list_my_reservations,
    cancel_reservation,
    generate_resources,
]