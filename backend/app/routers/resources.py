from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.resource import Resource
from app.models.scenario import Scenario
from app.models.user import User
from app.schemas.resource import ResourceCreate, ResourceUpdate, ResourceResponse
from app.utils.deps import get_current_admin
from app.utils.response import success

router = APIRouter(prefix="/api/scenarios", tags=["资源管理"])


def _get_scenario(db: Session, scenario_id: int) -> Scenario:
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预约场景不存在")
    return scenario


@router.get("/{scenario_id}/resources", summary="列出场景下的资源")
def list_resources(
    scenario_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    search: str = Query(""),
    db: Session = Depends(get_db),
):
    _get_scenario(db, scenario_id)
    q = db.query(Resource).filter(Resource.scenario_id == scenario_id)
    if search:
        q = q.filter(Resource.name.ilike(f"%{search}%"))
    total = q.count()
    resources = q.offset((page - 1) * page_size).limit(page_size).all()
    data = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [ResourceResponse.model_validate(r).model_dump() for r in resources],
    }
    return success(data=data)


@router.post("/{scenario_id}/resources", summary="创建资源（仅管理员）")
def create_resource(
    scenario_id: int,
    payload: ResourceCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    _get_scenario(db, scenario_id)
    if payload.open_start >= payload.open_end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开放时间必须早于关闭时间")
    exists = (
        db.query(Resource)
        .filter(Resource.scenario_id == scenario_id, Resource.code == payload.code)
        .first()
    )
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"资源编号 {payload.code} 已存在")
    resource = Resource(scenario_id=scenario_id, **payload.model_dump())
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return success(data=ResourceResponse.model_validate(resource).model_dump(), message="创建成功")


@router.put("/{scenario_id}/resources/{resource_id}", summary="更新资源（仅管理员）")
def update_resource(
    scenario_id: int,
    resource_id: int,
    payload: ResourceUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    resource = (
        db.query(Resource)
        .filter(Resource.id == resource_id, Resource.scenario_id == scenario_id)
        .first()
    )
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资源不存在")
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(resource, key, value)
    if resource.open_start >= resource.open_end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开放时间必须早于关闭时间")
    db.commit()
    db.refresh(resource)
    return success(data=ResourceResponse.model_validate(resource).model_dump(), message="更新成功")


@router.delete("/{scenario_id}/resources/{resource_id}", summary="删除资源（仅管理员）")
def delete_resource(
    scenario_id: int,
    resource_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    resource = (
        db.query(Resource)
        .filter(Resource.id == resource_id, Resource.scenario_id == scenario_id)
        .first()
    )
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资源不存在")
    db.delete(resource)
    db.commit()
    return success(message="删除成功")