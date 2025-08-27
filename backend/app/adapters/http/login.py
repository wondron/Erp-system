from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
import logging

from app.domain.models import UserEntity, UserRole
from app.core.security import hash_password, verify_password
from app.infrastructure.db import get_db
from app.infrastructure.repositories_login import LoginRepo, DuplicateUserError


router = APIRouter(prefix="/login", tags=["Login"])
logger = logging.getLogger("erp.http.login")


class LoginData(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=64)


class AddUser(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    showname: str = Field(..., min_length=1, max_length=64)
    userrole: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=64)


class LoginResponse(BaseModel):
    username: str
    showname: str
    userrole: str


@router.post("/create", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def create_user(body: AddUser, db: AsyncSession = Depends(get_db)):
    repo = LoginRepo(db)
    try:
        role = UserRole(body.userrole) if body.userrole else UserRole.USER
    except ValueError:
        role = UserRole.USER

    entity = UserEntity(
        id=None,
        username=body.username,
        showname=body.showname,
        password_hash=hash_password(body.password),
        role=role,
    )

    try:
        user_info = await repo.add(entity)
    except (IntegrityError, DuplicateUserError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
    except Exception as e:
        logger.exception("Create user failed: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Create user failed") from e

    return LoginResponse(
        username=user_info.username,
        showname=user_info.showname,
        userrole=user_info.role.value,
    )


@router.post("/auth", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(body: LoginData, db: AsyncSession = Depends(get_db)):
    repo = LoginRepo(db)
    user = await repo.get_by_username(body.username)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号/密码错误！")

    logger.info("User %s logged in", user.username)

    return LoginResponse(
        username=user.username,
        showname=user.showname,
        userrole=user.role.value,
    )
