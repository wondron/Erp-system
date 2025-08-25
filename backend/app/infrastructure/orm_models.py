from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer
from .db import Base
import datetime as dt


class UserORM(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "erp_app"}  # 如果你用 erp_app 这个 schema
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_name:  Mapped[str] = mapped_column(String(64), nullable=False)