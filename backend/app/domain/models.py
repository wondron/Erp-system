# 不依赖 ORM
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
# app/domain/models.py
from pydantic import BaseModel, Field, RootModel
from typing import Optional, Dict, Any, List



# @dataclass 是 Python 的一个装饰器，用于自动生成类的特殊方法（如 __init__, __repr__, __eq__ 等）。
# slots=True 参数会让类使用 __slots__ 来优化内存使用，避免创建实例字典，从而减少内存占用，提高属性访问速度。

class UserRole(str, Enum):
    USER = "user"         # 普通用户
    ADMIN = "admin"       # 管理员
    SUPPLIER = "supplier" # 供应商
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


class BarcodesIn(BaseModel):
    barcodes: List[str]

    
class SalesInfoIn(BaseModel):
    大类目: str
    小品类: str
    季节性: Optional[str] = None
    产品: str
    销售渠道: Optional[str] = None
    责任人: Optional[str] = None
    SKU: str
    ASIN: Optional[str] = None
    产品条码: Optional[str] = None
    自定义箱唛: Optional[str] = None
    货号: Optional[str] = None
    颜色: Optional[str] = None
    尺寸: Optional[str] = None
    销售价: Optional[float] = None

class SupplyInfoIn(BaseModel):
    供应商: Optional[str] = None
    采购价: Optional[float] = None
    单品包装尺寸: Optional[str] = None
    单品包装重量: Optional[float] = None
    装箱系数: Optional[int] = None
    外箱长: Optional[int] = None
    外箱宽: Optional[int] = None
    外箱高: Optional[int] = None
    
class CustomsInfoIn(BaseModel):
    中文品名: Optional[str] = None
    英文品名: Optional[str] = None
    海关编码: Optional[str] = None
    申报要素: Optional[str] = None
    申报价: Optional[float] = None
    图片: Optional[str] = None

class ProductionIn(RootModel[Dict[str, Any]]):
    """按“材料X / 材料X用量”成对解析，v2 用 RootModel，值在 .root 里"""
    pass

class GoodsIn(BaseModel):
    销售信息: SalesInfoIn = Field(...)
    供应信息: SupplyInfoIn = Field(...)
    报关信息: CustomsInfoIn = Field(...)
    生产配套: ProductionIn = Field(...)