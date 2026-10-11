from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.room import Room
from app.models.seat import Seat
from app.models.reservation import Reservation
from app.schemas.room import RoomCreate, RoomUpdate, RoomResponse, RoomDetailResponse
from app.utils.deps import get_current_user, get_current_admin
from app.models.user import User
from app.utils.response import success
from datetime import date

router = APIRouter(prefix="/api/rooms", tags=["自习室管理"])


@router.get("", summary="列出所有自习室")
def list_rooms(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str = Query("", description="按名称搜索"),
    db: Session = Depends(get_db),
):
    query = db.query(Room)
    if search:
        query = query.filter(Room.name.ilike(f"%{search}%"))
    total = query.count()
    rooms = query.offset((page - 1) * page_size).limit(page_size).all()
    data = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [RoomResponse.model_validate(r).model_dump() for r in rooms],
    }
    return success(data=data)


@router.get("/{room_id}", summary="获取自习室详情（含座位信息）")
def get_room(room_id: int, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="自习室不存在")
    return success(data=RoomDetailResponse.model_validate(room).model_dump())


@router.post("", summary="创建自习室（仅管理员）")
def create_room(
    payload: RoomCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    if payload.open_time >= payload.close_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开放时间必须早于关闭时间")
    room = Room(
        name=payload.name,
        location=payload.location,
        open_time=payload.open_time,
        close_time=payload.close_time,
        capacity=payload.capacity,
        is_active=payload.is_active,
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return success(data=RoomResponse.model_validate(room).model_dump(), message="创建成功")


@router.put("/{room_id}", summary="更新自习室（仅管理员）")
def update_room(
    room_id: int,
    payload: RoomUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="自习室不存在")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(room, key, value)

    if room.open_time >= room.close_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开放时间必须早于关闭时间")

    db.commit()
    db.refresh(room)
    return success(data=RoomResponse.model_validate(room).model_dump(), message="更新成功")


@router.delete("/{room_id}", summary="删除自习室（仅管理员）")
def delete_room(
    room_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="自习室不存在")
    db.delete(room)
    db.commit()
    return success(message="删除成功")


@router.get("/{room_id}/availability", summary="查询某自习室某天的可用时间段和座位")
def get_availability(
    room_id: int,
    date: date = Query(..., description="查询日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="自习室不存在")

    seats = db.query(Seat).filter(Seat.room_id == room_id, Seat.is_available == True).all()
    seat_ids = [s.id for s in seats]

    reservations = (
        db.query(Reservation)
        .filter(
            Reservation.seat_id.in_(seat_ids),
            Reservation.reservation_date == date,
            Reservation.status != "cancelled",
        )
        .all()
    )

    booked_map = {}
    for r in reservations:
        booked_map.setdefault(r.seat_id, []).append(
            {"start_time": r.start_time.isoformat(), "end_time": r.end_time.isoformat(), "status": r.status}
        )

    seats_info = []
    for s in seats:
        slots = booked_map.get(s.id, [])
        seats_info.append(
            {
                "seat_id": s.id,
                "seat_number": s.seat_number,
                "is_available": s.is_available,
                "window": s.window,
                "power": s.power,
                "quiet": s.quiet,
                "is_group": s.is_group,
                "corner": s.corner,
                "booked_slots": slots,
            }
        )

    data = {
        "room_id": room.id,
        "date": date.isoformat(),
        "open_time": room.open_time.isoformat(),
        "close_time": room.close_time.isoformat(),
        "seats": seats_info,
    }
    return success(data=data)
