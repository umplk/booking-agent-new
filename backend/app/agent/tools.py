from datetime import date, datetime, time
from typing import Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.database import SessionLocal
from app.models.reservation import Reservation
from app.models.room import Room
from app.models.seat import Seat


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


def _fmt_time(value: time) -> str:
    return value.strftime("%H:%M")


def _seat_attrs(seat: Seat) -> str:
    tags = []
    if seat.window:
        tags.append("靠窗")
    if seat.power:
        tags.append("有电源")
    if seat.quiet:
        tags.append("安静区")
    if seat.corner:
        tags.append("角落")
    if seat.is_group:
        tags.append("讨论区")
    return ("（" + "、".join(tags) + "）") if tags else ""


def _occupied_seat_ids(db, room_id: int, target_date: date) -> set:
    rows = (
        db.query(Reservation.seat_id)
        .filter(
            Reservation.room_id == room_id,
            Reservation.reservation_date == target_date,
            Reservation.status != "cancelled",
        )
        .all()
    )
    return {r[0] for r in rows}


@tool
def list_rooms() -> str:
    """列出所有开放中的自习室，包含房间编号、名称、位置、开放时间和座位数。"""
    db = SessionLocal()
    try:
        rooms = db.query(Room).filter(Room.is_active == True).all()  # noqa: E712
        if not rooms:
            return "当前没有开放中的自习室。"
        lines = []
        for r in rooms:
            seat_count = db.query(Seat).filter(Seat.room_id == r.id).count()
            lines.append(
                f"room_id={r.id} | {r.name} | 位置:{r.location or '未标注'} | "
                f"开放时间 {_fmt_time(r.open_time)}-{_fmt_time(r.close_time)} | 座位数 {seat_count}"
            )
        return "\n".join(lines)
    finally:
        db.close()


@tool
def query_availability(room_id: int, date: str) -> str:
    """查询指定自习室在指定日期（YYYY-MM-DD）下未被预约、可选的座位。"""
    target_date = _parse_date(date)
    if target_date is None:
        return "日期格式不正确，请使用 YYYY-MM-DD 格式。"
    db = SessionLocal()
    try:
        room = db.query(Room).filter(Room.id == room_id, Room.is_active == True).first()  # noqa: E712
        if not room:
            return f"自习室 room_id={room_id} 不存在或未开放。"
        occupied = _occupied_seat_ids(db, room_id, target_date)
        seats = db.query(Seat).filter(Seat.room_id == room_id, Seat.is_available == True).all()  # noqa: E712
        free = [s for s in seats if s.id not in occupied]
        if not free:
            return f"{room.name} 在 {target_date} 当天没有可选座位。"
        lines = [f"{room.name} 在 {target_date} 可选座位："]
        for s in free:
            lines.append(f"seat_id={s.id} | 座位 {s.seat_number} {_seat_attrs(s)}")
        return "\n".join(lines)
    finally:
        db.close()


@tool
def recommend_seat(
    date: str,
    prefer_window: bool = False,
    prefer_power: bool = False,
    prefer_quiet: bool = False,
    prefer_corner: bool = False,
    prefer_group: bool = False,
    room_id: Optional[int] = None,
) -> str:
    """按用户偏好智能推荐可选座位，返回匹配度从高到低的推荐列表。"""
    target_date = _parse_date(date)
    if target_date is None:
        return "日期格式不正确，请使用 YYYY-MM-DD 格式。"
    prefs = {
        "window": prefer_window,
        "power": prefer_power,
        "quiet": prefer_quiet,
        "corner": prefer_corner,
        "group": prefer_group,
    }
    db = SessionLocal()
    try:
        room_query = db.query(Room).filter(Room.is_active == True)  # noqa: E712
        if room_id is not None:
            room_query = room_query.filter(Room.id == room_id)
        rooms = room_query.all()
        if not rooms:
            return "没有可推荐的开放自习室。"
        results = []
        for room in rooms:
            occupied = _occupied_seat_ids(db, room.id, target_date)
            seats = (
                db.query(Seat)
                .filter(Seat.room_id == room.id, Seat.is_available == True)  # noqa: E712
                .all()
            )
            for s in seats:
                if s.id in occupied:
                    continue
                score = 0
                if prefer_window and s.window:
                    score += 1
                if prefer_power and s.power:
                    score += 1
                if prefer_quiet and s.quiet:
                    score += 1
                if prefer_corner and s.corner:
                    score += 1
                if prefer_group and s.is_group:
                    score += 1
                results.append((score, room, s))
        if not results:
            return f"在 {target_date} 没有符合偏好的可选座位。"
        results.sort(key=lambda x: (-x[0], x[2].id))
        top = results[:5]
        lines = [f"为你推荐 {target_date} 的 {len(top)} 个座位（匹配度由高到低）："]
        for score, room, s in top:
            lines.append(
                f"匹配度 {score} | room_id={room.id} {room.name} | "
                f"seat_id={s.id} 座位 {s.seat_number} {_seat_attrs(s)}"
            )
        return "\n".join(lines)
    finally:
        db.close()


@tool
def create_reservation(
    room_id: int,
    seat_id: int,
    date: str,
    start_time: str,
    end_time: str,
    *,
    config: RunnableConfig,
) -> str:
    """为用户创建座位预约，成功后返回预约信息；失败时返回具体原因。"""
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
        room = db.query(Room).filter(Room.id == room_id).first()
        if not room or not room.is_active:
            return "该自习室不存在或未开放。"
        seat = db.query(Seat).filter(Seat.id == seat_id, Seat.room_id == room_id).first()
        if not seat or not seat.is_available:
            return "座位不存在、不属于该自习室或不可用。"
        if start >= end:
            return "开始时间必须早于结束时间。"
        now = datetime.now()
        if target_date < now.date():
            return "不能预约过去的日期。"
        if target_date == now.date() and start <= now.time():
            return "不能预约过去的时间。"
        if start < room.open_time or end > room.close_time:
            return f"预约时间须在开放时间内（{_fmt_time(room.open_time)}-{_fmt_time(room.close_time)}）。"
        conflict = (
            db.query(Reservation)
            .filter(
                Reservation.seat_id == seat_id,
                Reservation.reservation_date == target_date,
                Reservation.status != "cancelled",
                Reservation.start_time < end,
                Reservation.end_time > start,
            )
            .first()
        )
        if conflict:
            return "该座位在此时间段已被预约。"
        reservation = Reservation(
            user_id=user_id,
            seat_id=seat_id,
            room_id=room_id,
            reservation_date=target_date,
            start_time=start,
            end_time=end,
            status="confirmed",
        )
        db.add(reservation)
        db.commit()
        db.refresh(reservation)
        return (
            f"预约成功！预约号 {reservation.id}：{room.name} 座位 {seat.seat_number}，"
            f"{target_date} {_fmt_time(start)}-{_fmt_time(end)}。"
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
            .filter(Reservation.user_id == user_id, Reservation.status.in_(["pending", "confirmed"]))
            .order_by(Reservation.reservation_date.asc(), Reservation.start_time.asc())
            .all()
        )
        if not rows:
            return "你当前没有有效预约。"
        lines = ["你的有效预约："]
        for r in rows:
            room = db.query(Room).filter(Room.id == r.room_id).first()
            seat = db.query(Seat).filter(Seat.id == r.seat_id).first()
            lines.append(
                f"预约号 {r.id} | {room.name if room else r.room_id} 座位 "
                f"{seat.seat_number if seat else r.seat_id} | {r.reservation_date} "
                f"{_fmt_time(r.start_time)}-{_fmt_time(r.end_time)}"
            )
        return "\n".join(lines)
    finally:
        db.close()


@tool
def cancel_reservation(reservation_id: int, *, config: RunnableConfig) -> str:
    """取消指定预约号的预约，只能取消自己的预约。"""
    user_id = config["configurable"].get("user_id")
    db = SessionLocal()
    try:
        reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
        if not reservation:
            return "预约不存在。"
        if reservation.user_id != user_id:
            return "只能取消自己的预约。"
        if reservation.status == "cancelled":
            return "该预约已取消。"
        if reservation.status == "completed":
            return "已完成的预约无法取消。"
        reservation.status = "cancelled"
        db.commit()
        return f"预约号 {reservation_id} 已成功取消。"
    finally:
        db.close()


@tool
def get_current_datetime() -> str:
    """获取当前日期、星期和时间，用于把"今天/明天/后天/下周几"等相对时间换算成具体日期（YYYY-MM-DD）。"""
    now = datetime.now()
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return f"当前日期：{now.date()}（{weekdays[now.weekday()]}），当前时间：{now.strftime('%H:%M')}"


TOOLS = [
    get_current_datetime,
    list_rooms,
    query_availability,
    recommend_seat,
    create_reservation,
    list_my_reservations,
    cancel_reservation,
]