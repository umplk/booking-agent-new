from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.scenario import Scenario
from app.models.user import User
from app.schemas.scenario import ScenarioCreate, ScenarioUpdate, ScenarioResponse
from app.services.booking_service import query_availability
from app.utils.deps import get_current_admin
from app.utils.response import success

router = APIRouter(prefix="/api/scenarios", tags=["预约场景"])


@router.get("", summary="列出预约场景")
def list_scenarios(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str = Query("", description="按名称搜索"),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
):
    q = db.query(Scenario)
    if search:
        q = q.filter(Scenario.name.ilike(f"%{search}%"))
    if not include_inactive:
        q = q.filter(Scenario.is_active == True)  # noqa: E712
    total = q.count()
    scenarios = q.offset((page - 1) * page_size).limit(page_size).all()
    data = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [ScenarioResponse.model_validate(s).model_dump() for s in scenarios],
    }
    return success(data=data)


@router.get("/{scenario_id}", summary="获取场景详情")
def get_scenario(scenario_id: int, db: Session = Depends(get_db)):
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预约场景不存在")
    return success(data=ScenarioResponse.model_validate(scenario).model_dump())


@router.post("", summary="创建预约场景（仅管理员）")
def create_scenario(
    payload: ScenarioCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    if payload.min_duration_minutes > payload.max_duration_minutes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="最小时长不能大于最大时长")
    scenario = Scenario(**payload.model_dump())
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return success(data=ScenarioResponse.model_validate(scenario).model_dump(), message="创建成功")


@router.put("/{scenario_id}", summary="更新场景规则（仅管理员）")
def update_scenario(
    scenario_id: int,
    payload: ScenarioUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预约场景不存在")
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(scenario, key, value)
    if scenario.min_duration_minutes > scenario.max_duration_minutes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="最小时长不能大于最大时长")
    db.commit()
    db.refresh(scenario)
    return success(data=ScenarioResponse.model_validate(scenario).model_dump(), message="更新成功")


@router.delete("/{scenario_id}", summary="删除预约场景（仅管理员）")
def delete_scenario(
    scenario_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预约场景不存在")
    db.delete(scenario)
    db.commit()
    return success(message="删除成功")


@router.get("/{scenario_id}/availability", summary="查询场景某日各资源的空闲时段")
def get_availability(
    scenario_id: int,
    date: date = Query(..., description="查询日期 YYYY-MM-DD"),
    start: time = Query(None, description="过滤起始时间 HH:MM"),
    end: time = Query(None, description="过滤结束时间 HH:MM"),
    db: Session = Depends(get_db),
):
    if start and end and start >= end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="起始时间必须早于结束时间")
    data = query_availability(db, scenario_id, date, range_start=start, range_end=end)
    return success(data=data)