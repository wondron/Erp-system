# 不依赖 ORM
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


# @dataclass 是 Python 的一个装饰器，用于自动生成类的特殊方法（如 __init__, __repr__, __eq__ 等）。
# slots=True 参数会让类使用 __slots__ 来优化内存使用，避免创建实例字典，从而减少内存占用，提高属性访问速度。

class UserRole(str, Enum):
    USER = "user"         # 普通用户
    ADMIN = "admin"       # 管理员
    MANAGER = "manager"   # 经理/管理角色
    STAFF = "staff"       # 员工


@dataclass
class UserEntity:
    id: int | None
    username: str
    showname: str
    password_hash: str
    role: UserRole = UserRole.USER



@dataclass(slots=True)
class User:
    id: int | None
    first_name: str
    last_name: str
    created_at: datetime | None = None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"