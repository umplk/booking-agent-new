from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.reservation import Reservation
from app.models.resource import Resource
from app.models.scenario import Scenario
from app.models.user import User
from app.schemas.reservation import ReservationCreate, ReservationResponse
from app.services.booking_service import create_reservation, cancel_reservation
from app.utils.deps import get_current_user
from app.utils.response import success

router = APIRouter(prefix="/api/reservations", tags=["预约"])

VALID_STATUSES = ("pending", "confirmed", "cancelled", "completed")


def _to_dict(r: Reservation) -> dict:
    item = ReservationResponse.model_validate(r).model_dump()
    item["resource_name"] = r.resource.name if r.resource else None
    item["resource_code"] = r.resource.code if r.resource else None
    item["scenario_name"] = r.scenario.name if r.scenario else None
    item["user_name"] = r.user.name if r.user else None
    item["user_username"] = r.user.username if r.user else None
    return item


@router.post("", summary="创建预约")
def create_reservation_api(
    payload: ReservationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reservation = create_reservation(db, current_user, payload.scenario_id, payload.resource_id, payload.start_time, payload.end_time)
    return success(data=_to_dict(reservation), message="预约成功")


@router.get("", summary="列出我的预约")
def list_my_reservations(
    status_filter: str = Query("all", alias="status"),
    scenario_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Reservation).filter(Reservation.user_id == current_user.id)
    if status_filter != "all":
        if status_filter not in VALID_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的状态，可选值: {', '.join(VALID_STATUSES)}",
            )
        q = q.filter(Reservation.status == status_filter)
    if scenario_id is not None:
        q = q.filter(Reservation.scenario_id == scenario_id)
    rows = q.order_by(Reservation.start_time.desc()).all()
    return success(data=[_to_dict(r) for r in rows])


@router.get("/admin", summary="列出所有用户预约（管理员）")
def list_all_reservations(
    status_filter: str = Query("all", alias="status"),
    scenario_id: int = Query(None),
    resource_id: int = Query(None),
    date: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可访问")
    q = db.query(Reservation)
    if status_filter != "all":
        if status_filter not in VALID_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的状态，可选值: {', '.join(VALID_STATUSES)}",
            )
        q = q.filter(Reservation.status == status_filter)
    if scenario_id is not None:
        q = q.filter(Reservation.scenario_id == scenario_id)
    if resource_id is not None:
        q = q.filter(Reservation.resource_id == resource_id)
    if date:
        try:
            day = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="日期格式应为 YYYY-MM-DD")
        q = q.filter(Reservation.start_time < day + timedelta(days=1), Reservation.end_time > day)
    rows = q.order_by(Reservation.start_time.desc()).all()
    return success(data=[_to_dict(r) for r in rows])


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


@router.put("/{reservation_id}/cancel", summary="取消预约")
def cancel_reservation_api(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reservation = cancel_reservation(db, current_user, reservation_id)
    return success(data=_to_dict(reservation), message="取消成功")