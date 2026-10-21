from datetime import datetime, time, date, timedelta

from fastapi import HTTPException, status as http_status
from sqlalchemy.orm import Session

from app.models.reservation import Reservation
from app.models.resource import Resource
from app.models.scenario import Scenario
from app.models.user import User
from app.schemas.reservation import ResourceAvailability, TimeSlot


def _booking_error(detail: str):
    return HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=detail)


def _combine(d: date, t: time) -> datetime:
    return datetime.combine(d, t)


def _slots_overlap(start: datetime, end: datetime, slot_start: datetime, slot_end: datetime) -> bool:
    return start < slot_end and end > slot_start


def create_reservation(db: Session, current_user: User, scenario_id: int, resource_id: int, start_time: datetime, end_time: datetime) -> Reservation:
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise _booking_error("预约场景不存在")
    if not scenario.is_active:
        raise _booking_error("该预约场景未开放")

    resource = db.query(Resource).filter(Resource.id == resource_id, Resource.scenario_id == scenario_id).first()
    if not resource:
        raise _booking_error("资源不存在或不属于该场景")
    if not resource.is_active:
        raise _booking_error("该资源不可用")

    now = datetime.now()
    if start_time >= end_time:
        raise _booking_error("开始时间必须早于结束时间")

    if not scenario.allow_same_day and start_time.date() == now.date():
        raise _booking_error("该场景不支持当日预约")

    if start_time <= now:
        raise _booking_error("不能预约过去的时间")

    if scenario.min_advance_minutes and scenario.min_advance_minutes > 0:
        advance_minutes = int((start_time - now).total_seconds() // 60)
        if advance_minutes < scenario.min_advance_minutes:
            raise _booking_error(f"需至少提前 {scenario.min_advance_minutes} 分钟预约")

    max_date = now.date() + timedelta(days=scenario.max_advance_days)
    if start_time.date() > max_date:
        raise _booking_error(f"最多只能提前 {scenario.max_advance_days} 天预约")

    duration_minutes = int((end_time - start_time).total_seconds() // 60)
    if duration_minutes < scenario.min_duration_minutes:
        raise _booking_error(f"预约时长不能少于 {scenario.min_duration_minutes} 分钟")
    if duration_minutes > scenario.max_duration_minutes:
        raise _booking_error(f"预约时长不能超过 {scenario.max_duration_minutes} 分钟")

    step = scenario.time_step_minutes
    if start_time.minute % step != 0 or start_time.second != 0:
        raise _booking_error(f"开始时间需按 {step} 分钟粒度对齐")
    if duration_minutes % step != 0:
        raise _booking_error(f"预约时长需是 {step} 分钟的整数倍")

    rdate = start_time.date()
    open_start = _combine(rdate, resource.open_start)
    open_end = _combine(rdate, resource.open_end)
    if start_time < open_start or end_time > open_end:
        raise _booking_error(
            f"预约时间须在资源开放时间内（{resource.open_start.strftime('%H:%M')}-{resource.open_end.strftime('%H:%M')}）"
        )

    conflict = (
        db.query(Reservation)
        .filter(
            Reservation.resource_id == resource_id,
            Reservation.status != "cancelled",
            Reservation.start_time < end_time,
            Reservation.end_time > start_time,
        )
        .first()
    )
    if conflict:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="该资源在此时间段已被预约",
        )

    active_count = (
        db.query(Reservation)
        .filter(
            Reservation.user_id == current_user.id,
            Reservation.scenario_id == scenario_id,
            Reservation.status == "confirmed",
        )
        .count()
    )
    if active_count >= scenario.max_active_per_user:
        raise _booking_error(f"每个用户同时最多预约 {scenario.max_active_per_user} 次")

    if scenario.max_minutes_per_day is not None:
        day_start = _combine(start_time.date(), time.min)
        day_end = day_start + timedelta(days=1)
        day_rows = (
            db.query(Reservation)
            .filter(
                Reservation.user_id == current_user.id,
                Reservation.scenario_id == scenario_id,
                Reservation.status == "confirmed",
                Reservation.start_time >= day_start,
                Reservation.start_time < day_end,
            )
            .all()
        )
        used = sum(int((r.end_time - r.start_time).total_seconds() // 60) for r in day_rows)
        if used + duration_minutes > scenario.max_minutes_per_day:
            raise _booking_error(f"每日预约总时长不能超过 {scenario.max_minutes_per_day} 分钟")

    reservation = Reservation(
        scenario_id=scenario_id,
        user_id=current_user.id,
        resource_id=resource_id,
        start_time=start_time,
        end_time=end_time,
        status="confirmed",
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return reservation


def cancel_reservation(db: Session, current_user: User, reservation_id: int) -> Reservation:
    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not reservation:
        raise _booking_error("预约不存在")
    if reservation.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="无权取消该预约")
    if reservation.status == "cancelled":
        raise _booking_error("该预约已取消")
    if reservation.status == "completed":
        raise _booking_error("已完成的预约无法取消")

    scenario = db.query(Scenario).filter(Scenario.id == reservation.scenario_id).first()
    cancel_before_minutes = scenario.cancel_before_minutes if scenario else None
    if cancel_before_minutes is not None:
        remain_minutes = int((reservation.start_time - datetime.now()).total_seconds() // 60)
        if remain_minutes < cancel_before_minutes:
            raise _booking_error(f"预约开始前 {cancel_before_minutes} 分钟内不可取消")

    reservation.status = "cancelled"
    db.commit()
    db.refresh(reservation)
    return reservation


def query_availability(db: Session, scenario_id: int, target_date: date, range_start: time = None, range_end: time = None) -> dict:
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise _booking_error("预约场景不存在")

    booked_rows = (
        db.query(Reservation)
        .filter(
            Reservation.scenario_id == scenario_id,
            Reservation.status != "cancelled",
            Reservation.start_time < _combine(target_date + timedelta(days=1), time.min),
            Reservation.end_time > _combine(target_date, time.min),
        )
        .all()
    )
    booked_by_resource: dict[int, list[tuple[datetime, datetime]]] = {}
    for r in booked_rows:
        if r.start_time.date() == target_date:
            booked_by_resource.setdefault(r.resource_id, []).append((r.start_time, r.end_time))

    step = scenario.time_step_minutes
    results: list[ResourceAvailability] = []
    resources = (
        db.query(Resource)
        .filter(Resource.scenario_id == scenario_id, Resource.is_active == True)  # noqa: E712
        .all()
    )
    for resource in resources:
        slots: list[TimeSlot] = []
        cursor = _combine(target_date, resource.open_start)
        end_boundary = _combine(target_date, resource.open_end)
        if range_start and _combine(target_date, range_start) > cursor:
            cursor = _combine(target_date, range_start)
        if range_end and _combine(target_date, range_end) < end_boundary:
            end_boundary = _combine(target_date, range_end)
        booked = booked_by_resource.get(resource.id, [])
        while cursor < end_boundary:
            slot_end = cursor + timedelta(minutes=step)
            if slot_end > end_boundary:
                break
            if not any(_slots_overlap(b[0], b[1], cursor, slot_end) for b in booked):
                slots.append(TimeSlot(start=cursor.strftime("%H:%M"), end=slot_end.strftime("%H:%M")))
            cursor = slot_end
        results.append(
            ResourceAvailability(
                resource_id=resource.id,
                code=resource.code,
                name=resource.name,
                is_active=resource.is_active,
                free_slots=slots,
            )
        )

    return {"scenario_id": scenario_id, "date": target_date.isoformat(), "free_slots_count": sum(len(r.free_slots) for r in results), "resources": results}