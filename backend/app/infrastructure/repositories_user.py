# 用 Session 操作 ORM，并在此负责 领域对象 ↔ ORM 的转换

from typing import List, Optional
from sqlalchemy.orm import Session
from .orm_models import UserORM

try:
    from ..domain.models import User
    USE_DOMAIN = True
except Exception:
    USE_DOMAIN = False


def to_domain(u: UserORM) -> User:
    return User(id=u.id, first_name=u.first_name, last_name=u.last_name, created_at=u.created_at)

def to_orm(u: User) -> UserORM:
    return UserORM(id=u.id, first_name=u.first_name, last_name=u.last_name)

    
class UserRepo:
    def __init__(self, db: Session):
        self.db = db
        
    def add(self, first_name: str, last_name: str) -> int:
        orm = UserORM(first_name=first_name, last_name=last_name)
        self.db.add(orm)
        # 让数据库生成自增主键
        self.db.flush()  # 有事务时 flush 即可拿到 orm.id；get_db 会在退出时统一 commit
        return orm.id

    def list_by_lastname(self, last_name: str)  -> List["User | dict"]:
        rows = (
            self.db.query(UserORM)
            .filter(UserORM.last_name == last_name)
            .order_by(UserORM.id.asc())
            .all()
        )
        if USE_DOMAIN:
            return [User(id=r.id, first_name=r.first_name, last_name=r.last_name) for r in rows]
        return [{"id": r.id, "first_name": r.first_name, "last_name": r.last_name} for r in rows]

    def get(self, user_id: int) -> Optional["User | dict"]:
        r = self.db.get(UserORM, user_id)
        if not r:
            return None
        if USE_DOMAIN:
            return User(id=r.id, first_name=r.first_name, last_name=r.last_name)
        return {"id": r.id, "first_name": r.first_name, "last_name": r.last_name}