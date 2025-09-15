from __future__ import annotations
from datetime import datetime, timedelta, timezone
import logging
from typing import Optional

import jwt  # pip install PyJWT
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.domain.models import UserEntity, UserRole
from app.infrastructure.db import get_db
from app.infrastructure.repositories_login import LoginRepo, DuplicateUserError
from app.infrastructure.request_context import RequestCtx, RequestContext  # 用于可选的管理员校验


settings = get_settings()
router = APIRouter(prefix="/login", tags=["Login"])
logger = logging.getLogger("erp.http.login")


# ===================== 配置区 =====================
JWT_ALG = "HS256"
ACCESS_TOKEN_EXPIRE_MIN = 120           # 访问 token 有效期（分钟）
REFRESH_TOKEN_EXPIRE_DAYS = 14         # refresh token 有效期（天）
REQUIRE_ADMIN_FOR_CREATE = True        # 是否要求管理员才能创建用户
# =================================================


class LoginData(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=64)


class AddUser(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    showname: str = Field(..., min_length=1, max_length=64)
    userrole: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=64)
    comfirm: str = Field(..., min_length=1, max_length=64)

class TokenPair(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MIN * 60  # 秒


class LoginResponse(BaseModel):
    username: str
    showname: str
    userrole: str
    token: Optional[TokenPair] = None  # 登录成功时返回 token，创建用户时可不返回


# ---------- Token 工具 ----------
def _create_jwt(payload: dict, expires_delta: timedelta) -> str:
    to_encode = payload.copy()
    now = datetime.now(timezone.utc)
    to_encode["iat"] = int(now.timestamp())
    to_encode["exp"] = int((now + expires_delta).timestamp())
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=JWT_ALG)

def create_access_token(*, user_id: int | str, username: str, role: str) -> str:
    return _create_jwt(
        {"sub": str(user_id), "username": username, "role": role, "scope": "access"},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MIN)
    )

def create_refresh_token(*, user_id: int | str, username: str, role: str) -> str:
    return _create_jwt(
        {"sub": str(user_id), "username": username, "role": role, "scope": "refresh"},
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )


# ---------- 接口 ----------
@router.post("/create", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: AddUser,
    db: AsyncSession = Depends(get_db),
    # ctx: RequestContext = RequestCtx,   # 可选：要求管理员
):
    # 可选的管理员校验
    # if REQUIRE_ADMIN_FOR_CREATE:
    #     role_names = set((ctx.roles or [])) | ({ctx.username} if ctx.username else set())
    #     # 允许的管理员判断：token 里的 role=admin 或 authorities/scope 中包含 admin
    #     is_admin = ("admin" in role_names) or (getattr(ctx, "user_id", None) in {"1"})  # 例：ID=1 也算管理员
    #     if not is_admin:
    #         raise HTTPException(status_code=403, detail="只有管理员才能创建用户")
    logger.info("创建用户: %s", body)
    if body.password != body.comfirm:
        raise HTTPException(status_code=403, detail="两次输入的密码不一致")

    repo = LoginRepo(db)
    try:
        role = UserRole(body.userrole) if body.userrole else UserRole.USER
    except ValueError:
        role = UserRole.USER

    entity = UserEntity(
        id=None,
        username=body.username.strip(),
        showname=body.showname.strip(),
        password_hash=hash_password(body.password),
        role=role,
    )

    try:
        user_info = await repo.add(entity)
    except (IntegrityError, DuplicateUserError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户已注册！")
    except Exception as e:
        logger.exception("创建用户失败: %s", e)
        raise HTTPException(status_code=500, detail="创建用户失败") from e

    return LoginResponse(
        username=user_info.username,
        showname=user_info.showname,
        userrole=user_info.role.value,
        token=None,  # 创建用户不强制登录
    )


@router.post("/auth", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(body: LoginData, db: AsyncSession = Depends(get_db)):
    repo = LoginRepo(db)
    user = await repo.get_by_username(body.username.strip())
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="账号/密码错误！")

    access = create_access_token(user_id=user.id, username=user.username, role=user.role.value)
    refresh = create_refresh_token(user_id=user.id, username=user.username, role=user.role.value)

    logger.info("用户 %s 登录", user.username)

    return LoginResponse(
        username=user.username,
        showname=user.showname,
        userrole=user.role.value,
        token=TokenPair(access_token=access, refresh_token=refresh),
    )

# （可选）刷新 access_token
class RefreshIn(BaseModel):
    refresh_token: str

class RefreshOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MIN * 60

@router.post("/refresh", response_model=RefreshOut)
async def refresh_token(body: RefreshIn):
    try:
        payload = jwt.decode(body.refresh_token, settings.SECRET_KEY, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if payload.get("scope") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token scope")

    new_access = create_access_token(
        user_id=payload.get("sub"),
        username=payload.get("username", ""),
        role=payload.get("role", "user"),
    )
    return RefreshOut(access_token=new_access)