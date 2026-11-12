from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    UserRegister,
    UserLogin,
    UserResponse,
    RefreshRequest,
    LogoutRequest,
)
from app.utils import token_store
from app.utils.deps import bearer_scheme, oauth2_scheme
from app.utils.security import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    issued_before_password_change,
    verify_password,
)
from app.utils.response import success

router = APIRouter(prefix="/api/auth", tags=["认证"])


def _issue_tokens(user: User) -> dict:
    claims = {"sub": user.username}
    return {
        "access_token": create_access_token(claims),
        "refresh_token": create_refresh_token(claims),
        "token_type": "bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


def _invalid_refresh() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="刷新令牌无效或已过期",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _remaining_ttl(payload: dict) -> int:
    try:
        return int(payload["exp"] - datetime.now(timezone.utc).timestamp())
    except (KeyError, TypeError, ValueError):
        return 0


def _revoke_token(raw_token: Optional[str], expected_type: Optional[str] = None) -> None:
    """尽力撤销单个令牌：已过期或无法解析的直接跳过（此时它本就不可用）。"""
    if not raw_token:
        return
    payload = decode_token(raw_token, expected_type=expected_type)
    if not payload or not payload.get("jti"):
        return
    ttl = _remaining_ttl(payload)
    if ttl > 0:
        token_store.revoke(payload["jti"], ttl)


@router.post("/register", summary="用户注册")
def register(payload: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被注册")
    if payload.student_id and db.query(User).filter(User.student_id == payload.student_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="学号已存在")

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        student_id=payload.student_id,
        name=payload.name,
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return success(data=UserResponse.model_validate(user).model_dump(), message="注册成功")


@router.post("/login", summary="用户登录")
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    return success(data=_issue_tokens(user), message="登录成功")


@router.post("/token", summary="OAuth2 表单登录（供 Swagger Authorize 弹窗使用）")
def login_form(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """标准 OAuth2 密码流端点，返回 token 格式可直接被 Swagger 识别并自动保存。"""
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _issue_tokens(user)


@router.post("/logout", summary="登出当前设备")
def logout(
    payload: Optional[LogoutRequest] = None,
    token: Optional[str] = Depends(oauth2_scheme),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
):
    """撤销当前设备的 access 与 refresh；access 已过期时仍会撤销 refresh，保证登出有效。"""
    raw_access = token or (credentials.credentials if credentials else None)
    _revoke_token(raw_access, ACCESS_TOKEN_TYPE)
    if payload and payload.refresh_token:
        _revoke_token(payload.refresh_token, REFRESH_TOKEN_TYPE)
    return success(message="已退出登录")


@router.post("/refresh", summary="刷新访问令牌（refresh 单次使用，用后轮换）")
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    data = decode_token(payload.refresh_token, expected_type=REFRESH_TOKEN_TYPE)
    if not data or not data.get("sub") or not data.get("jti"):
        raise _invalid_refresh()

    jti = data["jti"]
    if token_store.is_revoked(jti):
        raise _invalid_refresh()

    user = db.query(User).filter(User.username == data["sub"]).first()
    if user is None:
        raise _invalid_refresh()

    if issued_before_password_change(data, user.id):
        raise _invalid_refresh()

    remaining = int(data["exp"] - datetime.now(timezone.utc).timestamp())
    token_store.revoke(jti, remaining)
    return success(data=_issue_tokens(user), message="刷新成功")