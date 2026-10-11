from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.room import Room
from app.models.seat import Seat
from app.models.user import User
from app.schemas.seat import SeatBatchCreate, SeatResponse, SeatUpdate
from app.utils.deps import get_current_admin
from app.utils.response import success

router = APIRouter(prefix="/api/rooms", tags=["座位管理"])


@router.get("/{room_id}/seats", summary="列出该自习室所有座位")
def list_seats(room_id: int, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="自习室不存在")
    seats = db.query(Seat).filter(Seat.room_id == room_id).all()
    return success(data=[SeatResponse.model_validate(s).model_dump() for s in seats])


@router.post("/{room_id}/seats", summary="批量创建座位（仅管理员）")
def create_seats(
    room_id: int,
    payload: SeatBatchCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="自习室不存在")

    existing_numbers = {
        s.seat_number for s in db.query(Seat).filter(Seat.room_id == room_id).all()
    }
    new_seats = []
    for item in payload.seats:
        if item.seat_number in existing_numbers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"座位编号 {item.seat_number} 已存在",
            )
        existing_numbers.add(item.seat_number)
        seat = Seat(
            room_id=room_id,
            seat_number=item.seat_number,
            is_available=item.is_available,
            window=item.window,
            power=item.power,
            quiet=item.quiet,
            is_group=item.is_group,
            corner=item.corner,
        )
        db.add(seat)
        new_seats.append(seat)

    db.commit()
    for s in new_seats:
        db.refresh(s)
    return success(
        data=[SeatResponse.model_validate(s).model_dump() for s in new_seats],
        message=f"成功创建 {len(new_seats)} 个座位",
    )


@router.put("/{room_id}/seats/{seat_id}", summary="更新座位状态（仅管理员）")
def update_seat(
    room_id: int,
    seat_id: int,
    payload: SeatUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    seat = db.query(Seat).filter(Seat.id == seat_id, Seat.room_id == room_id).first()
    if not seat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="座位不存在")
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(seat, key, value)
    db.commit()
    db.refresh(seat)
    return success(data=SeatResponse.model_validate(seat).model_dump(), message="更新成功")
