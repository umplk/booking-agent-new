from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserUpdate, UserResponse
from app.utils import token_store
from app.utils.deps import get_current_user
from app.utils.security import get_password_hash
from app.utils.response import success

router = APIRouter(prefix="/api/users", tags=["用户管理"])


@router.get("/me", summary="获取当前登录用户信息")
def get_me(current_user: User = Depends(get_current_user)):
    return success(data=UserResponse.model_validate(current_user).model_dump())


@router.put("/me", summary="更新个人信息")
def update_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.email and payload.email != current_user.email:
        if db.query(User).filter(User.email == payload.email).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被注册")
        current_user.email = payload.email

    if payload.student_id and payload.student_id != current_user.student_id:
        if db.query(User).filter(User.student_id == payload.student_id).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="学号已存在")
        current_user.student_id = payload.student_id

    if payload.name is not None:
        current_user.name = payload.name

    password_changed = bool(payload.password)
    if payload.password:
        current_user.password_hash = get_password_hash(payload.password)

    db.commit()
    db.refresh(current_user)

    if password_changed:
        # 覆盖 refresh 最长有效期：此后 iat 早于此刻的令牌全部失效，实现全端下线
        ttl = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400 + 60
        token_store.mark_password_changed(current_user.id, ttl)

    return success(data=UserResponse.model_validate(current_user).model_dump(), message="更新成功")
