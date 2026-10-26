from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
    OAuth2PasswordBearer,
)
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.utils.security import decode_token

# 支持两种认证方式（Swagger Authorize 弹窗会同时显示两个输入区域）：
# 1. OAuth2 密码流：直接填用户名/密码，走 /api/auth/token 换取 token
# 2. HTTPBearer：在 Value 输入框直接粘贴 "Bearer <token>"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="无法验证凭据",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> User:
    # 兼容两种来源：OAuth2 密码流自动携带的 token，或手动粘贴的 Bearer token
    token = token or (credentials.credentials if credentials else None)
    if not token:
        raise credentials_exception
    payload = decode_token(token)
    if payload is None or payload.get("sub") is None:
        raise credentials_exception
    username: str = payload.get("sub")
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，需要管理员权限",
        )
    return current_user


def get_current_merchant(current_user: User = Depends(get_current_user)) -> User:
    """要求当前用户为商家或管理员（普通用户不可访问商家管理接口）。"""
    if current_user.role not in ("admin", "merchant"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，需要商家权限",
        )
    return current_user


def get_optional_user(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[User]:
    """与 get_current_user 相同的解析逻辑，但未携带 token 时返回 None 而非抛 401。"""
    token = token or (credentials.credentials if credentials else None)
    if not token:
        return None
    payload = decode_token(token)
    if payload is None or payload.get("sub") is None:
        return None
    username: str = payload.get("sub")
    return db.query(User).filter(User.username == username).first()
