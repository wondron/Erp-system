# app/infrastructure/orm_models.py
from __future__ import annotations
from unicodedata import category
from sqlalchemy import (
    BigInteger, Integer, String, Text, Numeric, Date, DateTime, JSON, Enum,
    ForeignKey, UniqueConstraint, CheckConstraint, func    # ← 加上 CheckConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
import enum
from sqlalchemy.dialects.postgresql import JSONB
from app.infrastructure.db import Base 


#--------------------------------------用户信息-----------------------------------
class UserORM(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "erp_app"}  # 如果你用 erp_app 这个 schema
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_name:  Mapped[str] = mapped_column(String(64), nullable=False)
    
    
class LoginORM(Base):
    __tablename__ = "logins"
    __table_args__ = {"schema": "erp_app"}  # 如果你用 erp_app 这个 schema
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    showname: Mapped[str] = mapped_column(String(50), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    

#--------------------------------------产品信息---------------------------------------





class Goods(Base):
    __tablename__ = "goods"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # 核心标识
    category: Mapped[str] = mapped_column(String(64), nullable=False)        # 大类目
    subcategory: Mapped[str] = mapped_column(String(64), nullable=False)     # 小品类
    season: Mapped[str] = mapped_column(String(32), nullable=True)           # 季节性
    product_name: Mapped[str] = mapped_column(Text, nullable=False)          # 产品名称
    channel: Mapped[str] = mapped_column(String(32), nullable=True)          # 销售渠道
    owner: Mapped[str] = mapped_column(String(64), nullable=True)            # 责任人
    sku: Mapped[str] = mapped_column(String(64), index=True, nullable=False) # SKU（唯一约束见下）
    asin: Mapped[str] = mapped_column(String(20), index=True, nullable=True) # ASIN
    barcode: Mapped[str] = mapped_column(String(64), nullable=True)          # 产品条码（唯一约束见下）
    carton_mark: Mapped[str] = mapped_column(String(64), nullable=True)      # 自定义箱唛
    item_no: Mapped[str] = mapped_column(String(64), nullable=True)          # 货号
    color: Mapped[str] = mapped_column(String(64), nullable=True)            # 颜色
    size: Mapped[str] = mapped_column(String(64), nullable=True)             # 尺寸
    sale_price: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=True)  # 销售价（非负约束见下）

    # 关系
    supply: Mapped["SupplyInfo"] = relationship(back_populates="goods", uselist=False, cascade="all, delete-orphan")
    customs: Mapped["CustomsInfo"] = relationship(back_populates="goods", uselist=False, cascade="all, delete-orphan")
    materials: Mapped[list["MaterialUsage"]] = relationship(back_populates="goods", cascade="all, delete-orphan")

    # 改为 DB 侧时间（带时区）
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (
        UniqueConstraint("sku", name="uq_goods_sku"),
        UniqueConstraint("barcode", name="uq_goods_barcode"),                     # ← 新增：条码唯一（Postgres 允许多 NULL）
        UniqueConstraint("asin", name="uq_goods_asin"),   # ✅ 新增：ASIN 唯一（PG 允许多 NULL）
        CheckConstraint("sale_price IS NULL OR sale_price >= 0", name="ck_goods_sale_price_nonneg"),  # ← 新增：非负
        {"schema": "erp_product"}
    )


class SupplyInfo(Base):
    __tablename__ = "supply_info"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    goods_id: Mapped[int] = mapped_column(ForeignKey("erp_product.goods.id", ondelete="CASCADE"), nullable=False)

    vendor: Mapped[str] = mapped_column(String(128), nullable=True)
    purchase_price: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=True)       # 非负约束见下
    pkg_size: Mapped[str] = mapped_column(String(64), nullable=True)
    pkg_weight: Mapped[Numeric] = mapped_column(Numeric(10, 3), nullable=True)
    packing_ratio: Mapped[int] = mapped_column(Integer, nullable=True)
    carton_l: Mapped[int] = mapped_column(Integer, nullable=True)
    carton_w: Mapped[int] = mapped_column(Integer, nullable=True)
    carton_h: Mapped[int] = mapped_column(Integer, nullable=True)

    goods: Mapped["Goods"] = relationship(back_populates="supply")

    __table_args__ = (
        CheckConstraint("purchase_price IS NULL OR purchase_price >= 0", name="ck_supply_purchase_price_nonneg"),
        CheckConstraint("pkg_weight IS NULL OR pkg_weight >= 0",       name="ck_supply_pkg_weight_nonneg"),
        CheckConstraint("packing_ratio IS NULL OR packing_ratio >= 0", name="ck_supply_packing_ratio_nonneg"),
        CheckConstraint("carton_l IS NULL OR carton_l >= 0",           name="ck_supply_carton_l_nonneg"),
        CheckConstraint("carton_w IS NULL OR carton_w >= 0",           name="ck_supply_carton_w_nonneg"),
        CheckConstraint("carton_h IS NULL OR carton_h >= 0",           name="ck_supply_carton_h_nonneg"),
        {"schema": "erp_product"}
    )


class CustomsInfo(Base):
    __tablename__ = "customs_info"
    __table_args__ = {"schema": "erp_product"} 
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    goods_id: Mapped[int] = mapped_column(ForeignKey("erp_product.goods.id", ondelete="CASCADE"), nullable=False)
    
    name_cn: Mapped[str] = mapped_column(String(128), nullable=True)                    # 中文品名
    name_en: Mapped[str] = mapped_column(String(128), nullable=True)                    # 英文品名
    hscode: Mapped[str] = mapped_column(String(32), nullable=True)                      # 海关编码
    declaration: Mapped[str] = mapped_column(Text, nullable=True)                       # 申报要素
    declared_price: Mapped[Numeric] = mapped_column(Numeric(12,2), nullable=True)       # 申报价
    image_note: Mapped[str] = mapped_column(String(128), nullable=True)                 # 图片字段说明
    goods: Mapped["Goods"] = relationship(back_populates="customs")


class MaterialUsage(Base):
    __tablename__ = "material_usage"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    goods_id: Mapped[int] = mapped_column(ForeignKey("erp_product.goods.id", ondelete="CASCADE"), nullable=False)
    material_name: Mapped[str] = mapped_column(String(128), nullable=False)             # 材料名称
    quantity: Mapped[Numeric] = mapped_column(Numeric(12,3), nullable=False)            # 材料用量
    unit: Mapped[str] = mapped_column(String(32), nullable=False, server_default="件")
    goods: Mapped["Goods"] = relationship(back_populates="materials")
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_material_quantity_nonneg"),
        {"schema": "erp_product"}
    )


# 原始 JSON 备份（审计用）
class GoodsRaw(Base):
    __tablename__ = "goods_raw"
    __table_args__ = {"schema": "erp_product"} 

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    goods_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)