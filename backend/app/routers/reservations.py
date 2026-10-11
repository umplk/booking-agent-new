from datetime import datetime, date, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.reservation import Reservation
from app.models.room import Room
from app.models.seat import Seat
from app.models.user import User
from app.schemas.reservation import ReservationCreate, ReservationResponse
from app.utils.deps import get_current_user
from app.utils.response import success

router = APIRouter(prefix="/api/reservations", tags=["预约管理"])

VALID_STATUSES = ("pending", "confirmed", "cancelled", "completed")


def _to_dict(r: Reservation) -> dict:
    item = ReservationResponse.model_validate(r).model_dump()
    item["seat_number"] = r.seat.seat_number if r.seat else None
    item["room_name"] = r.room.name if r.room else None
    return item


@router.post("", summary="创建预约")
def create_reservation(
    payload: ReservationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = db.query(Room).filter(Room.id == payload.room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="自习室不存在")
    if not room.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该自习室未开放")

    seat = db.query(Seat).filter(Seat.id == payload.seat_id, Seat.room_id == payload.room_id).first()
    if not seat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="座位不存在或不属于该自习室")
    if not seat.is_available:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该座位不可用")

    if payload.start_time >= payload.end_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开始时间必须早于结束时间")

    now = datetime.now()
    if payload.reservation_date < now.date():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能预约过去的日期")
    if payload.reservation_date == now.date() and payload.start_time <= now.time():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能预约过去的时间")

    if payload.start_time < room.open_time or payload.end_time > room.close_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"预约时间须在开放时间内（{room.open_time} - {room.close_time}）",
        )

    conflict = (
        db.query(Reservation)
        .filter(
            Reservation.seat_id == payload.seat_id,
            Reservation.reservation_date == payload.reservation_date,
            Reservation.status != "cancelled",
            Reservation.start_time < payload.end_time,
            Reservation.end_time > payload.start_time,
        )
        .first()
    )
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该座位在此时间段已被预约",
        )

    reservation = Reservation(
        user_id=current_user.id,
        seat_id=payload.seat_id,
        room_id=payload.room_id,
        reservation_date=payload.reservation_date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        status=payload.status,
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return success(data=_to_dict(reservation), message="预约成功")


@router.get("", summary="列出我的预约")
def list_my_reservations(
    status_filter: str = Query("all", alias="status", description="按状态筛选"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Reservation).filter(Reservation.user_id == current_user.id)
    if status_filter != "all":
        if status_filter not in VALID_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的状态，可选值: {', '.join(VALID_STATUSES)}",
            )
        query = query.filter(Reservation.status == status_filter)
    reservations = query.order_by(Reservation.reservation_date.desc()).all()
    return success(data=[_to_dict(r) for r in reservations])


@router.get("/{reservation_id}", summary="获取预约详情")
def get_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not reservation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预约不存在")
    if reservation.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该预约")
    return success(data=_to_dict(reservation))


@router.put("/{reservation_id}/cancel", summary="取消预约（仅本人）")
def cancel_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not reservation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预约不存在")
    if reservation.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只能取消自己的预约")
    if reservation.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该预约已取消")
    if reservation.status == "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已完成的预约无法取消")

    reservation.status = "cancelled"
    db.commit()
    db.refresh(reservation)
    return success(data=_to_dict(reservation), message="取消成功")
