# app/infrastructure/repositories_goods.py
from __future__ import annotations
from typing import Any, Sequence, List
import logging
import math
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import unicodedata
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Alignment  # 如需自动换行可用
from app.domain.models import GoodsIn
from app.infrastructure.orm_models import Goods, SupplyInfo, CustomsInfo, MaterialUsage, GoodsRaw

# === 新增：使用模板导出服务（pandas + openpyxl 由 goods_outporter 负责） ===
from io import BytesIO
from app.infrastructure.services.goods_outporter import (
    export_from_goods_list,   # (goods_list -> bytes)
)

logger = logging.getLogger('repo.goods')


# === 自动适配列宽工具 ===
def _east_asian_len(s: str) -> int:
    """按 East Asian Width 估算显示宽度：全角(W/F)=2，其他=1。"""
    total = 0
    for ch in s:
        ea = unicodedata.east_asian_width(ch)
        total += 2 if ea in ("W", "F") else 1
    return total

def _best_line_len(text: str) -> int:
    """支持多行：返回各行中最大显示宽度。"""
    if not text:
        return 0
    lines = text.splitlines() or [text]
    return max(_east_asian_len(line) for line in lines)

def _autofit_columns_on_ws(ws, *, padding: float = 2.0, min_width: float = 8.0, max_width: float = 100.0,
                           wrap_long_text: bool = False) -> None:
    """
    遍历工作表所有列，按内容计算合适列宽并设置。
    - padding: 额外留白
    - min/max_width: 列宽上下限，避免过窄/过宽
    - wrap_long_text: True 时给所有单元格开启换行（若你更偏向“显示完整但可能增高行高”，可打开）
    """
    # 先可选地打开自动换行（在列宽受限时更易完整显示）
    if wrap_long_text:
        for row in ws.iter_rows():
            for cell in row:
                cell.alignment = Alignment(wrap_text=True)

    # 计算每列最大宽度需求
    for col_idx in range(1, ws.max_column + 1):
        maxlen = 0
        for row in ws.iter_rows(min_col=col_idx, max_col=col_idx, values_only=True):
            val = row[0]
            if val is None:
                continue
            # 数字/日期等统一转字符串估算显示宽度
            text = str(val)
            maxlen = max(maxlen, _best_line_len(text))

        # openpyxl 的 width 是近似“字符数”概念
        width = max(min_width, min(maxlen + padding, max_width))
        ws.column_dimensions[get_column_letter(col_idx)].width = width

def _apply_autofit_on_xlsx_bytes(data: bytes, *, sheet_name: str | None = None,
                                 **kwargs) -> bytes:
    """
    把 bytes 载入为工作簿，执行自动列宽，返回新的 bytes。
    kwargs 透传给 _autofit_columns_on_ws（如 padding/min_width/max_width/wrap_long_text）
    """
    bio = BytesIO(data)
    wb = load_workbook(bio)
    ws = wb[sheet_name] if (sheet_name and sheet_name in wb.sheetnames) else wb.active

    _autofit_columns_on_ws(ws, **kwargs)

    out = BytesIO()
    wb.save(out)
    return out.getvalue()

# ------------------------------ 序列化给前端 ------------------------------
def serialize_goods(g: Goods) -> dict:
    return {
        "id": g.id,
        "sku": g.sku,
        "asin": g.asin,
        "barcode": g.barcode,
        "product_name": g.product_name,
        "category": g.category,
        "subcategory": g.subcategory,
        "season": g.season,
        "channel": g.channel,
        "owner": g.owner,
        "color": g.color,
        "size": g.size,
        "sale_price": float(g.sale_price) if g.sale_price is not None else None,
        "supply": {
            "vendor": g.supply.vendor if g.supply else None,
            "purchase_price": float(g.supply.purchase_price) if (g.supply and g.supply.purchase_price is not None) else None,
            "pkg_size": g.supply.pkg_size if g.supply else None,
            "pkg_weight": float(g.supply.pkg_weight) if (g.supply and g.supply.pkg_weight is not None) else None,
            "packing_ratio": g.supply.packing_ratio if g.supply else None,
            "carton_l": g.supply.carton_l if g.supply else None,
            "carton_w": g.supply.carton_w if g.supply else None,
            "carton_h": g.supply.carton_h if g.supply else None,
        },
        "customs": {
            "name_cn": g.customs.name_cn if g.customs else None,
            "name_en": g.customs.name_en if g.customs else None,
            "hscode": g.customs.hscode if g.customs else None,
            "declaration": g.customs.declaration if g.customs else None,
            "declared_price": float(g.customs.declared_price) if (g.customs and g.customs.declared_price is not None) else None,
            "image_note": g.customs.image_note if g.customs else None,
        },
        "materials": [{"name": m.material_name, "qty": float(m.quantity)} for m in (g.materials or [])],
    }


# ------------------------------ JSON 清洗 ------------------------------
def _json_sanitize(obj: Any):
    """
    递归清洗：
    - Decimal -> float（失败则转 str）
    - float 的 NaN/Inf -> None
    - dict/list/tuple 递归处理
    其余类型原样返回
    """
    if obj is None or isinstance(obj, (bool, int, str)):
        return obj

    if isinstance(obj, Decimal):
        try:
            return float(obj)
        except Exception:
            return str(obj)

    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj

    if isinstance(obj, dict):
        return {k: _json_sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_sanitize(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_json_sanitize(v) for v in obj)

    return obj


# 统一的查询 options（带出一对一/一对多）
def _with_rels():
    return (
        selectinload(Goods.supply),
        selectinload(Goods.customs),
        selectinload(Goods.materials),
    )


# ------------------------------ 仓储 API ------------------------------
async def list_goods(session: AsyncSession, *, offset: int = 0, limit: int = 100) -> list[Goods]:
    stmt = select(Goods).options(*_with_rels()).offset(offset).limit(limit)
    res = await session.execute(stmt)
    return res.scalars().unique().all()


async def get_goods_by_barcodes(session: AsyncSession, barcodes: Sequence[str]) -> list[Goods]:
    if not barcodes:
        return []
    # 去重 & 清理
    uniq: list[str] = []
    seen = set()
    for b in barcodes:
        if not b:
            continue
        s = str(b).strip()
        if s and s not in seen:
            uniq.append(s)
            seen.add(s)
    if not uniq:
        return []
    stmt = select(Goods).where(Goods.barcode.in_(uniq)).options(*_with_rels())
    res = await session.execute(stmt)
    return res.scalars().unique().all()


async def delete_goods_by_barcodes(session: AsyncSession, barcodes: Sequence[str]) -> dict:
    """
    批量按产品条码删除；为保证关系级联，逐条 ORM 删除（不要用 bulk delete）。
    返回: {"deleted": [...], "not_found": [...], "count": N}
    """
    if not barcodes:
        return {"deleted": [], "not_found": [], "count": 0}

    # 去重并清理空值，同时保留顺序
    seen = set()
    uniq = []
    for b in barcodes:
        if b and b not in seen:
            uniq.append(b)
            seen.add(b)

    res = await session.execute(select(Goods).where(Goods.barcode.in_(uniq)))
    goods = res.scalars().all()
    found_set = {g.barcode for g in goods if g.barcode is not None}

    # 逐条删除以触发关系 cascade
    for g in goods:
        await session.delete(g)
    await session.flush()  # 交给 get_db()/get_session 统一 commit

    deleted = [b for b in uniq if b in found_set]
    not_found = [b for b in uniq if b not in found_set]
    return {"deleted": deleted, "not_found": not_found, "count": len(deleted)}


async def delete_goods_by_barcode(session: AsyncSession, barcode: str) -> bool:
    res = await session.execute(select(Goods).where(Goods.barcode == barcode))
    g = res.scalar_one_or_none()
    if not g:
        return False
    await session.delete(g)  # 依赖 ORM 关系的 cascade 或 FK ondelete
    await session.flush()
    return True


async def update_goods_by_barcode(session: AsyncSession, barcode: str, update_payload) -> Goods | None:
    q = await session.execute(
        select(Goods).where(Goods.barcode == barcode).options(*_with_rels())
    )
    g: Goods | None = q.scalar_one_or_none()
    if not g:
        return None

    # ---------- 销售信息 ----------
    s = getattr(update_payload, "销售信息", None)
    if s:
        if s.SKU is not None: g.sku = s.SKU
        if s.ASIN is not None: g.asin = s.ASIN
        if s.产品 is not None: g.product_name = s.产品
        if s.大类目 is not None: g.category = s.大类目
        if s.小品类 is not None: g.subcategory = s.小品类
        if s.季节性 is not None: g.season = s.季节性
        if s.销售渠道 is not None: g.channel = s.销售渠道
        if s.责任人 is not None: g.owner = s.责任人
        if s.颜色 is not None: g.color = s.颜色
        if s.尺寸 is not None: g.size = s.尺寸
        if s.销售价 is not None: g.sale_price = s.销售价
        if s.产品条码 is not None: g.barcode = s.产品条码  # 如允许改条码
        if s.自定义箱唛 is not None: g.carton_mark = s.自定义箱唛
        if s.货号 is not None: g.item_no = s.货号

    # ---------- 供应信息 ----------
    sup = getattr(update_payload, "供应信息", None)
    if sup:
        if not g.supply:
            g.supply = SupplyInfo()
        if sup.供应商 is not None: g.supply.vendor = sup.供应商
        if sup.采购价 is not None: g.supply.purchase_price = sup.采购价
        if sup.单品包装尺寸 is not None: g.supply.pkg_size = sup.单品包装尺寸
        if sup.单品包装重量 is not None: g.supply.pkg_weight = sup.单品包装重量
        if sup.装箱系数 is not None: g.supply.packing_ratio = sup.装箱系数
        if sup.外箱长 is not None: g.supply.carton_l = sup.外箱长
        if sup.外箱宽 is not None: g.supply.carton_w = sup.外箱宽
        if sup.外箱高 is not None: g.supply.carton_h = sup.外箱高

    # ---------- 报关信息 ----------
    cs = getattr(update_payload, "报关信息", None)
    if cs:
        if not g.customs:
            g.customs = CustomsInfo()
        if cs.中文品名 is not None: g.customs.name_cn = cs.中文品名
        if cs.英文品名 is not None: g.customs.name_en = cs.英文品名
        if cs.海关编码 is not None: g.customs.hscode = cs.海关编码
        if cs.申报要素 is not None: g.customs.declaration = cs.申报要素
        if cs.申报价 is not None: g.customs.declared_price = cs.申报价
        if cs.图片 is not None: g.customs.image_note = cs.图片

    # ---------- 生产配套（材料） ----------
    prod = getattr(update_payload, "生产配套", None)
    replace_materials = getattr(update_payload, "replace_materials", True)
    if prod:
        # 兼容 RootModel 与 dict
        root = getattr(prod, "root", None)
        if root is None and isinstance(prod, dict):
            root = prod
        root = root or {}

        # 解析“材料X / 材料X用量”
        pairs: dict[str, float] = {}
        for k, v in root.items():
            ks = str(k)
            if ks.startswith("材料") and not ks.endswith("用量"):
                idx = ks.replace("材料", "")
                qty = root.get(f"材料{idx}用量")
                if v is not None and qty is not None:
                    pairs[str(v)] = float(qty)

        if replace_materials:
            # 先清空再重建
            for m in list(g.materials or []):
                await session.delete(m)
            g.materials = []
        # 追加/重建
        for name, qty in pairs.items():
            g.materials.append(MaterialUsage(material_name=name, quantity=qty))

    await session.flush()
    return g


async def create_goods(session: AsyncSession, data: GoodsIn) -> Goods:
    """
    新增商品：
    - 先将 Pydantic 数据 model_dump(mode="python") 后做 _json_sanitize，再写入 goods_raw(JSONB)
    - 再写入结构化表
    - 不在此处 commit，交给 get_db()/get_session 统一提交
    """
    # --- 原始 JSON（消毒后） ---
    logger.info(f"create_goods: {data}")
    raw_payload = _json_sanitize(data.model_dump(mode="python"))
    raw = GoodsRaw(payload=raw_payload)
    session.add(raw)
    await session.flush()

    # --- 结构化主表/子表 ---
    s = data.销售信息
    g = Goods(
        sku=s.SKU,
        asin=s.ASIN,
        product_name=s.产品,
        category=s.大类目,
        subcategory=s.小品类,
        season=s.季节性,
        channel=s.销售渠道,
        owner=s.责任人,
        color=s.颜色,
        size=s.尺寸,
        sale_price=s.销售价,
        barcode=s.产品条码,
        carton_mark=s.自定义箱唛,
        item_no=s.货号,
    )
    session.add(g)
    await session.flush()     # 得到 goods.id

    # 回填 raw.goods_id
    raw.goods_id = g.id

    sup = data.供应信息
    session.add(SupplyInfo(
        goods_id=g.id,
        vendor=sup.供应商,
        purchase_price=sup.采购价,
        pkg_size=sup.单品包装尺寸,
        pkg_weight=sup.单品包装重量,
        packing_ratio=sup.装箱系数,
        carton_l=sup.外箱长,
        carton_w=sup.外箱宽,
        carton_h=sup.外箱高
    ))

    cs = data.报关信息
    session.add(CustomsInfo(
        goods_id=g.id,
        name_cn=cs.中文品名,
        name_en=cs.英文品名,
        hscode=cs.海关编码,
        declaration=cs.申报要素,
        declared_price=cs.申报价,
        image_note=cs.图片
    ))

    # 生产配套
    prod = getattr(data.生产配套, "root", {}) or {}
    pairs: dict[str, Any] = {}
    for k, v in prod.items():
        ks = str(k)
        if ks.startswith("材料") and not ks.endswith("用量"):
            idx = ks.replace("材料", "")
            qty = prod.get(f"材料{idx}用量")
            if v is not None and qty is not None:
                pairs[str(v)] = qty

    for name, qty in pairs.items():
        session.add(MaterialUsage(goods_id=g.id, material_name=name, quantity=qty))

    await session.flush()
    await session.refresh(g)
    return g


async def get_goods_by_sku(session: AsyncSession, sku: str) -> Goods | None:
    res = await session.execute(select(Goods).where(Goods.sku == sku))
    return res.scalar_one_or_none()


# ------------------------------ 导出 Excel ------------------------------
def export_goods_xlsx(goods_list: List[Goods]) -> BytesIO:
    """
    兼容旧签名：将 Goods 列表导出为 Excel。
    实现上使用 goods_outporter.export_from_goods_list（遵循 1111.xlsx 模板列顺序）。
    追加：自动适配列宽，保证列宽能显示完整文字（中/日文全角按2个字符宽估算）。
    """
    base_data: bytes = export_from_goods_list(goods_list, sheet_name="Sheet1")

    # 这里可以按需调整 padding/min/max/wrap_long_text
    tuned: bytes = _apply_autofit_on_xlsx_bytes(
        base_data,
        sheet_name="Sheet1",
        padding=2.0,
        min_width=8.0,
        max_width=100.0,
        wrap_long_text=False,   # 如果你更希望强制整段可见（增高行高），可改为 True
    )
    return BytesIO(tuned)


async def export_goods_xlsx_by_barcodes(
    session: AsyncSession,
    barcodes: Sequence[str],
    *,
    sheet_name: str = "Sheet1",
) -> BytesIO:
    goods_list = await get_goods_by_barcodes(session, barcodes)  # 先查
    base_data: bytes = export_from_goods_list(goods_list, sheet_name=sheet_name)
    tuned: bytes = _apply_autofit_on_xlsx_bytes(
        base_data,
        sheet_name=sheet_name,
        padding=2.0,
        min_width=8.0,
        max_width=100.0,
        wrap_long_text=False,
    )
    return BytesIO(tuned)