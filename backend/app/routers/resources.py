from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.resource import Resource
from app.models.scenario import Scenario
from app.models.user import User
from app.schemas.resource import ResourceCreate, ResourceUpdate, ResourceResponse
from app.services.resource_generator import generate_resources
from app.utils.deps import get_current_user, get_current_merchant
from app.utils.response import success

router = APIRouter(prefix="/api/scenarios", tags=["资源管理"])


class GenerateRequest(BaseModel):
    description: str = Field(..., min_length=1, description="自然语言描述，如「5个羽毛球场地，9-22点开放」")


def _get_scenario(db: Session, scenario_id: int) -> Scenario:
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预约场景不存在")
    return scenario


def _get_scenario_owned(db: Session, scenario_id: int, user: User) -> Scenario:
    """获取场景并校验当前用户是否为其拥有者（管理员放行）。"""
    scenario = _get_scenario(db, scenario_id)
    if user.role == "admin":
        return scenario
    if scenario.owner_id is None or scenario.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作该场景下的资源")
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


@router.post("/{scenario_id}/resources", summary="创建资源")
def create_resource(
    scenario_id: int,
    payload: ResourceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_merchant),
):
    _get_scenario_owned(db, scenario_id, current_user)
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


@router.post("/{scenario_id}/resources/generate", summary="AI 根据描述批量生成资源")
def generate_resources_api(
    scenario_id: int,
    payload: GenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_merchant),
):
    scenario = _get_scenario_owned(db, scenario_id, current_user)
    created = generate_resources(db, scenario, payload.description)
    if not created:
        return success(data={"created": [], "count": 0}, message="未生成新资源（编号可能已存在）")
    data = {
        "created": [ResourceResponse.model_validate(r).model_dump() for r in created],
        "count": len(created),
    }
    return success(data=data, message=f"已生成 {len(created)} 个资源")


@router.put("/{scenario_id}/resources/{resource_id}", summary="更新资源")
def update_resource(
    scenario_id: int,
    resource_id: int,
    payload: ResourceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_merchant),
):
    _get_scenario_owned(db, scenario_id, current_user)
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


@router.delete("/{scenario_id}/resources/{resource_id}", summary="删除资源")
def delete_resource(
    scenario_id: int,
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_merchant),
):
    _get_scenario_owned(db, scenario_id, current_user)
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
