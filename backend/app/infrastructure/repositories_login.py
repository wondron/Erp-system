# 用 Session 操作 ORM，并在此负责 领域对象 ↔ ORM 的转换
from __future__ import annotations
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from .orm_models import LoginORM
from app.domain.models import UserEntity, UserRole


class DuplicateUserError(Exception):
    """username 已存在"""
    pass

    
class LoginRepo:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get_by_username(self, username: str) -> Optional[UserEntity]:
        stmt = select(LoginORM).where(LoginORM.username == username)
        result = await self.db.execute(stmt)
        orm_user = result.scalar_one_or_none()
        if orm_user:
            return UserEntity(
                id=orm_user.id,
                username=orm_user.username,
                showname=orm_user.showname,
                password_hash=orm_user.password_hash,
                role=UserRole(orm_user.role),
            )
        return None
    
    
    async def add(self, user: UserEntity) -> UserEntity:
        existing = await self.get_by_username(user.username)
        if existing:
            raise DuplicateUserError(f"username '{user.username}' already exists")
        
        orm_user = LoginORM(
            username=user.username,
            password_hash=user.password_hash,
            showname=user.showname,
            role=user.role.value,
        )
        self.db.add(orm_user)
        try:
            await self.db.flush()
            await self.db.refresh(orm_user)
        except IntegrityError as e:
            await self.db.rollback()
            raise DuplicateUserError(f"username '{user.username}' already exists") from e
        
        return UserEntity(
            id = orm_user.id,
            username=orm_user.username,
            showname=orm_user.showname,
            password_hash=orm_user.password_hash,
            role=UserRole(orm_user.role)
        )