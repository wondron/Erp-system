# app/infrastructure/services/goods_importer.py
from __future__ import annotations
import io
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Tuple, Iterable
from sqlalchemy.orm import selectinload
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.infrastructure.orm_models import Goods 
from app.domain.models import GoodsIn, SalesInfoIn, SupplyInfoIn, CustomsInfoIn, ProductionIn, MaterialItemIn
from app.infrastructure.repositories_goods import create_goods, get_goods_by_sku, update_goods_by_barcode
import logging


logger = logging.getLogger('infra.goods_importer')

def sniff_sheets(file_bytes: bytes) -> list[str]:
    xf = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")
    return xf.sheet_names


# 列名映射（Excel表头 → 你的 JSON/字段）
SALES_COLS = {
    "大类目": "大类目",
    "小品类": "小品类",
    "季节性": "季节性",
    "产品":   "产品",
    "销售渠道": "销售渠道",
    "责任人": "责任人",
    "SKU":   "SKU",
    "ASIN":  "ASIN",
    "产品条码": "产品条码",
    "自定义箱唛": "自定义箱唛",
    "货号": "货号",
    "颜色": "颜色",
    "尺寸": "尺寸",
    "销售价": "销售价",
}
SUPPLY_COLS = {
    "供应商": "供应商",
    "采购价": "采购价",
    "单品包装尺寸": "单品包装尺寸",
    "单品包装重量": "单品包装重量",
    "装箱系数": "装箱系数",
    "外箱长": "外箱长",
    "外箱宽": "外箱宽",
    "外箱高": "外箱高",
}
CUSTOMS_COLS = {
    "中文品名": "中文品名",
    "英文品名": "英文品名",
    "海关编码": "海关编码",
    "申报要素": "申报要素",
    "申报价":   "申报价",
    "图片":     "图片",
}

# 编号类：强制按字符串处理与清洗（保留前导零）
ID_STR_COLS = ["SKU", "ASIN", "产品条码", "自定义箱唛", "货号"]
# 供应里更适合整数入库的列
INT_SUPPLY_COLS = {"装箱系数", "外箱长", "外箱宽", "外箱高"}


def _clean_header(name: Any) -> str:
    return str(name).strip()


def _detect_material_mode(columns: list[str]) -> str:
    """
    返回:
      - "with_unit": 存在任意 '材料1用量单位' 这类列 -> 三列模式
      - "no_unit":   完全不存在 -> 两列模式
    """
    for i in range(1, 11):
        if f"材料{i}用量单位" in columns:
            return "with_unit"
    return "no_unit"



def _to_str(val) -> str | None:
    """文本统一清洗：空/NaN/'nan'/'none'/'null' -> None，其余去首尾空白。"""
    if pd.isna(val) or val == "":
        return None
    s = str(val).strip()
    if s == "" or s.lower() in ("nan", "none", "null"):
        return None
    return s


def _to_decimal(val, *, field_name: str | None = None) -> Decimal | None:
    if val is None or (hasattr(pd, "isna") and pd.isna(val)):
        return None
    s = str(val).strip()
    if s == "":
        return None
    # 去掉千分位
    s = s.replace(",", "")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        if field_name:
            raise ValueError(f"{field_name} 数值不合法: {val}")
        return None


def _to_int(val) -> int | None:
    """将字符串/数字（含 '20.0' / 科学计数法）稳妥转成 int；为空返回 None。"""
    if pd.isna(val) or val == "":
        return None
    s = str(val).strip()
    if s == "" or s.lower() in ("nan", "none", "null"):
        return None
    if s.endswith(".0"):
        s = s[:-2]
    # 科学计数法 -> 普通整数字符串
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?[eE][+-]?\d+", s):
        try:
            s = format(Decimal(s), "f").rstrip("0").rstrip(".")
        except Exception:
            pass
    try:
        if "." in s:
            s = s.split(".", 1)[0]
        return int(s)
    except Exception:
        return None


def _clean_id_string(val):
    """把 SKU/ASIN/条码等字段统一转成干净字符串，保留前导零，去掉 .0/科学计数。"""
    if pd.isna(val) or val == "":
        return None
    s = str(val).strip()
    if s == "" or s.lower() in ("nan", "none", "null"):
        return None
    if s.endswith(".0"):
        s = s[:-2]
    # 科学计数法 -> 普通字符串（不丢精度）
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?[eE][+-]?\d+", s):
        try:
            s = format(Decimal(s), "f").rstrip("0").rstrip(".")
        except Exception:
            pass
    return s


def _normalize_unit(u: str) -> str:
    u = u.strip()
    mapping = {
        "个": "件",
        "pcs": "件",
        "piece": "件",
        "kg": "kg",
        "g": "g",
        "米": "m",
        "m": "m",
    }
    return mapping.get(u.lower(), u)


def _parse_materials_from_row(row, *, material_mode: str) -> list[MaterialItemIn]:
    materials: list[MaterialItemIn] = []

    for i in range(1, 11):
        name = _to_str(row.get(f"材料{i}"))
        qty  = _to_decimal(
            row.get(f"材料{i}用量"),
            field_name=f"材料{i}用量"
        )
        # ✅ 单位处理规则
        if material_mode == "with_unit":
            unit = _to_str(row.get(f"材料{i}用量单位")) or "件"
            unit = _normalize_unit(unit)
        else:
            unit = "件"
        # 整组为空 -> 跳过
        if name is None and qty is None:
            continue
        # 不完整 -> 报错
        if not name or qty is None:
            raise ValueError(
                f"材料{i} 信息不完整：需同时填写「材料{i}」与「材料{i}用量」"
            )
        materials.append(
            MaterialItemIn(
                name=name,
                qty=qty,
                unit=unit
            )
        )
    return materials



def _row_to_goods_in(row: pd.Series, material_mode: str) -> GoodsIn:
    # 销售信息
    sales_data: Dict[str, Any] = {}
    for xls, field in SALES_COLS.items():
        v = row.get(xls)
        if field in ("销售价", "销售价"):  # 这里按你的最终字段名二选一
            sales_data[field] = _to_decimal(v, field_name=field)
        elif field in ("SKU", "ASIN", "产品条码", "自定义箱唛", "货号"):
            sales_data[field] = _clean_id_string(v)
        else:
            sales_data[field] = _to_str(v)

    # 供应信息
    supply_data: Dict[str, Any] = {}
    for xls, field in SUPPLY_COLS.items():
        v = row.get(xls)
        if field in INT_SUPPLY_COLS:
            supply_data[field] = _to_int(v)
        elif field in ("采购价", "单品包装重量"):
            supply_data[field] = _to_decimal(v, field_name=field)
        else:
            supply_data[field] = _to_str(v)

    # 报关信息
    customs_data: Dict[str, Any] = {}
    for xls, field in CUSTOMS_COLS.items():
        v = row.get(xls)
        customs_data[field] = _to_decimal(v, field_name=field) if field in ("申报价",) else _to_str(v)

    # ✅ 生产配套：两列/三列自动兼容
    materials = _parse_materials_from_row(row, material_mode=material_mode)

    return GoodsIn(
        销售信息=SalesInfoIn(**sales_data),
        供应信息=SupplyInfoIn(**supply_data),
        报关信息=CustomsInfoIn(**customs_data),
        生产配套=ProductionIn(materials),   # ✅ RootModel[List[...]]
    )

async def import_excel_to_db(
    session: AsyncSession,
    file_bytes: bytes,
    *,
    sheet_name: str | int | None = 0,
    upsert_by_sku: bool = True,
) -> Dict[str, Any]:
    """
    方案B（不兼容旧 errors）：
    - inserted: 成功插入数
    - skipped:  跳过数（DB 已存在导致不插入）
    - failed:   失败数（数据问题/异常导致不插入）
    - total:    本次处理的总行数（清理空行后的 df 行数）
    - skipped_items: 跳过明细
    - failed_items:  失败明细
    """
    ok: int = 0
    skipped_items: List[Dict[str, Any]] = []
    failed_items: List[Dict[str, Any]] = []

    logger.info(
        "开始导入 Excel：sheet=%s, upsert_by_sku=%s, file_size=%d bytes",
        sheet_name, upsert_by_sku, len(file_bytes),
    )

    # -------------------------
    # 1) 校验 sheet 参数
    # -------------------------
    sheet_names = sniff_sheets(file_bytes)
    if sheet_name is None:
        sheet_arg: str | int = 0
    elif isinstance(sheet_name, int):
        if sheet_name < 0 or sheet_name >= len(sheet_names):
            raise ValueError(f"工作表索引越界: {sheet_name}；可用工作表：{sheet_names}")
        sheet_arg = sheet_name
    else:
        s = str(sheet_name).strip()
        if s.isdigit():
            idx = int(s)
            if idx < 0 or idx >= len(sheet_names):
                raise ValueError(f"工作表索引越界: {idx}；可用工作表：{sheet_names}")
            sheet_arg = idx
        else:
            if s not in sheet_names:
                raise ValueError(f"未找到名为 '{s}' 的工作表；可用工作表：{sheet_names}")
            sheet_arg = s

    # -------------------------
    # 2) 读取 DataFrame
    # -------------------------
    df = pd.read_excel(
        io.BytesIO(file_bytes),
        sheet_name=sheet_arg,
        engine="openpyxl",
        dtype=str,
        keep_default_na=True,
    )

    df.rename(columns={c: _clean_header(c) for c in df.columns}, inplace=True)

    # 材料列模式（两列/三列）
    material_mode = _detect_material_mode(list(df.columns))

    # 清洗 ID 字段
    for col in ID_STR_COLS:
        if col in df.columns:
            df[col] = df[col].map(_clean_id_string)

    # 去掉空行（SKU 和 产品都空则去掉）
    if "SKU" in df.columns and "产品" in df.columns:
        before = len(df)
        df = df[~(df.get("SKU").isna() & df.get("产品").isna())]
        after = len(df)
        if after != before:
            logger.info("清理空行：before=%d, after=%d, removed=%d", before, after, before - after)

    # ✅ total（清理后的）
    total = int(len(df))

    # -------------------------
    # 3) 预取数据库已存在 key
    # -------------------------
    sku_list: list[str] = []
    barcode_list: list[str] = []
    asin_list: list[str] = []

    if "SKU" in df.columns:
        sku_list = [s for s in df["SKU"].dropna().astype(str).map(str.strip).tolist() if s]
        sku_list = list(dict.fromkeys(sku_list))

    if "产品条码" in df.columns:
        barcode_list = [b for b in df["产品条码"].dropna().astype(str).map(str.strip).tolist() if b]
        barcode_list = list(dict.fromkeys(barcode_list))

    if "ASIN" in df.columns:
        asin_list = [a for a in df["ASIN"].dropna().astype(str).map(str.strip).tolist() if a]
        asin_list = list(dict.fromkeys(asin_list))

    exist_skus: set[str] = set()
    exist_barcodes: set[str] = set()
    exist_asins: set[str] = set()

    if upsert_by_sku and sku_list:
        res = await session.execute(select(Goods.sku).where(Goods.sku.in_(sku_list)))
        exist_skus = {r[0] for r in res.all() if r[0]}
        logger.info("预取数据库已存在 SKU：%d / excel_sku=%d", len(exist_skus), len(sku_list))

    if barcode_list:
        res = await session.execute(select(Goods.barcode).where(Goods.barcode.in_(barcode_list)))
        exist_barcodes = {r[0] for r in res.all() if r[0]}
        logger.info("预取数据库已存在 条码：%d / excel_barcode=%d", len(exist_barcodes), len(barcode_list))

    if asin_list:
        res = await session.execute(select(Goods.asin).where(Goods.asin.in_(asin_list)))
        exist_asins = {r[0] for r in res.all() if r[0]}
        logger.info("预取数据库已存在 ASIN：%d / excel_asin=%d", len(exist_asins), len(asin_list))

    # -------------------------
    # 4) Excel 内部重复检测
    # -------------------------
    seen_skus: set[str] = set()
    seen_barcodes: set[str] = set()
    seen_asins: set[str] = set()

    logger.info("开始逐行导入：rows=%d, material_mode=%s", total, material_mode)

    # -------------------------
    # 5) 主循环
    # -------------------------
    for idx, row in df.iterrows():
        row_no = int(idx) + 2  # Excel 行号（含表头）
        try:
            payload = _row_to_goods_in(row, material_mode=material_mode)

            sku = (payload.销售信息.SKU or "").strip()
            barcode = (payload.销售信息.产品条码 or "").strip()
            asin = (payload.销售信息.ASIN or "").strip()

            # Excel 内重复：归失败
            if sku and sku in seen_skus:
                failed_items.append({"row": row_no, "reason": "excel_duplicate_sku", "message": f"Excel 内重复 SKU: {sku}", "sku": sku})
                continue
            if sku:
                seen_skus.add(sku)

            if barcode and barcode in seen_barcodes:
                failed_items.append({"row": row_no, "reason": "excel_duplicate_barcode", "message": f"Excel 内重复 条码: {barcode}", "barcode": barcode})
                continue
            if barcode:
                seen_barcodes.add(barcode)

            if asin and asin in seen_asins:
                failed_items.append({"row": row_no, "reason": "excel_duplicate_asin", "message": f"Excel 内重复 ASIN: {asin}", "asin": asin})
                continue
            if asin:
                seen_asins.add(asin)

            # DB 已存在：归跳过
            if upsert_by_sku and sku and sku in exist_skus:
                skipped_items.append({"row": row_no, "reason": "db_exists_sku", "message": f"已存在 SKU: {sku}", "sku": sku})
                continue

            if barcode and barcode in exist_barcodes:
                skipped_items.append({"row": row_no, "reason": "db_exists_barcode", "message": f"已存在 条码: {barcode}", "barcode": barcode})
                continue

            if asin and asin in exist_asins:
                skipped_items.append({"row": row_no, "reason": "db_exists_asin", "message": f"已存在 ASIN: {asin}", "asin": asin})
                continue

            # 插入
            await create_goods(session, payload)
            ok += 1

            # 放入 exist_*，防止同批后续重复插入
            if sku:
                exist_skus.add(sku)
            if barcode:
                exist_barcodes.add(barcode)
            if asin:
                exist_asins.add(asin)

            if ok % 200 == 0:
                logger.info("导入进度：ok=%d, skipped=%d, failed=%d", ok, len(skipped_items), len(failed_items))

        except Exception as e:
            msg = str(e)
            failed_items.append({"row": row_no, "reason": "exception", "message": msg})
            logger.exception("导入失败 row=%d：%s", row_no, msg)

    skipped = len(skipped_items)
    failed = len(failed_items)

    logger.info("导入完成：ok=%d, skipped=%d, failed=%d, total=%d", ok, skipped, failed, total)

    return {
        "inserted": ok,
        "skipped": skipped,
        "failed": failed,
        "total": total,
        "skipped_items": skipped_items,
        "failed_items": failed_items,
    }


from decimal import Decimal
from typing import Any, Iterable, Tuple, Optional

def _norm_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s != "" else None

def _norm_dec(v: Any) -> Optional[Decimal]:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    s = str(v).strip()
    if s == "":
        return None
    try:
        return Decimal(s)
    except Exception:
        return None

def _iter_payload_materials(payload: Any) -> Iterable[Any]:
    """
    payload.生产配套 可能是：
    - None
    - list
    - Pydantic RootModel (有 .root)
    - 其它可迭代对象
    """
    prod = getattr(payload, "生产配套", None)
    if prod is None:
        return []

    # RootModel
    root = getattr(prod, "root", None)
    if root is not None:
        return root or []

    # 直接是 list/tuple
    if isinstance(prod, (list, tuple)):
        return prod

    # 兜底：可迭代
    try:
        return list(prod)
    except Exception:
        return []

def _materials_tuple_from_goods(g: Any) -> Tuple[Tuple[str, str, str], ...]:
    out = []
    for m in (getattr(g, "materials", None) or []):
        name = _norm_str(getattr(m, "material_name", None)) or _norm_str(getattr(m, "name", None)) or ""
        unit = _norm_str(getattr(m, "unit", None)) or ""
        qty  = getattr(m, "quantity", None)
        if qty is None:
            qty = getattr(m, "qty", None)
        qty_s = _norm_str(qty) or ""
        if not name and not unit and not qty_s:
            continue
        out.append((name, unit, qty_s))
    return tuple(sorted(out))

def _materials_tuple_from_payload(payload: Any) -> Tuple[Tuple[str, str, str], ...]:
    out = []
    for m in _iter_payload_materials(payload) or []:
        name = _norm_str(getattr(m, "name", None)) or _norm_str(getattr(m, "material_name", None)) or ""
        unit = _norm_str(getattr(m, "unit", None)) or ""
        qty  = getattr(m, "qty", None)
        if qty is None:
            qty = getattr(m, "quantity", None)
        qty_s = _norm_str(qty) or ""
        if not name and not unit and not qty_s:
            continue
        out.append((name, unit, qty_s))
    return tuple(sorted(out))


def would_change_goods(g: Any, payload: Any) -> bool:
    s   = getattr(payload, "销售信息", None)
    sup = getattr(payload, "供应信息", None)
    cs  = getattr(payload, "报关信息", None)

    # -------- sale --------
    if s:
        if _norm_str(getattr(g, "sku", None)) != _norm_str(getattr(s, "SKU", None)): return True
        if _norm_str(getattr(g, "barcode", None)) != _norm_str(getattr(s, "产品条码", None)): return True
        if _norm_str(getattr(g, "asin", None)) != _norm_str(getattr(s, "ASIN", None)): return True

        if _norm_str(getattr(g, "product_name", None)) != _norm_str(getattr(s, "产品", None)): return True
        if _norm_str(getattr(g, "category", None)) != _norm_str(getattr(s, "大类目", None)): return True
        if _norm_str(getattr(g, "subcategory", None)) != _norm_str(getattr(s, "小品类", None)): return True
        if _norm_str(getattr(g, "season", None)) != _norm_str(getattr(s, "季节性", None)): return True
        if _norm_str(getattr(g, "channel", None)) != _norm_str(getattr(s, "销售渠道", None)): return True
        if _norm_str(getattr(g, "owner", None)) != _norm_str(getattr(s, "责任人", None)): return True
        if _norm_str(getattr(g, "carton_mark", None)) != _norm_str(getattr(s, "自定义箱唛", None)): return True
        if _norm_str(getattr(g, "item_no", None)) != _norm_str(getattr(s, "货号", None)): return True
        if _norm_str(getattr(g, "color", None)) != _norm_str(getattr(s, "颜色", None)): return True
        if _norm_str(getattr(g, "size", None)) != _norm_str(getattr(s, "尺寸", None)): return True

        if _norm_dec(getattr(g, "sale_price", None)) != _norm_dec(getattr(s, "销售价", None)): return True

    # -------- supply --------
    gsup = getattr(g, "supply", None)
    if sup:
        if _norm_str(getattr(gsup, "vendor", None)) != _norm_str(getattr(sup, "供应商", None)): return True
        if _norm_dec(getattr(gsup, "purchase_price", None)) != _norm_dec(getattr(sup, "采购价", None)): return True
        if _norm_str(getattr(gsup, "pkg_size", None)) != _norm_str(getattr(sup, "单品包装尺寸", None)): return True
        if _norm_dec(getattr(gsup, "pkg_weight", None)) != _norm_dec(getattr(sup, "单品包装重量", None)): return True
        if _norm_str(getattr(gsup, "packing_ratio", None)) != _norm_str(getattr(sup, "装箱系数", None)): return True
        if _norm_dec(getattr(gsup, "carton_l", None)) != _norm_dec(getattr(sup, "外箱长", None)): return True
        if _norm_dec(getattr(gsup, "carton_w", None)) != _norm_dec(getattr(sup, "外箱宽", None)): return True
        if _norm_dec(getattr(gsup, "carton_h", None)) != _norm_dec(getattr(sup, "外箱高", None)): return True

    # -------- customs --------
    gcus = getattr(g, "customs", None)
    if cs:
        if _norm_str(getattr(gcus, "name_cn", None)) != _norm_str(getattr(cs, "中文品名", None)): return True
        if _norm_str(getattr(gcus, "name_en", None)) != _norm_str(getattr(cs, "英文品名", None)): return True
        if _norm_str(getattr(gcus, "hscode", None)) != _norm_str(getattr(cs, "海关编码", None)): return True
        if _norm_str(getattr(gcus, "declaration", None)) != _norm_str(getattr(cs, "申报要素", None)): return True
        if _norm_dec(getattr(gcus, "declared_price", None)) != _norm_dec(getattr(cs, "申报价", None)): return True
        if _norm_str(getattr(gcus, "image_note", None)) != _norm_str(getattr(cs, "图片", None)): return True

    # -------- materials --------
    gm = _materials_tuple_from_goods(g)
    pm = _materials_tuple_from_payload(payload)
    if gm != pm:
        return True

    return False


async def batch_update_excel_to_db(
    session: AsyncSession,
    file_bytes: bytes,
    *,
    sheet_name: str | int | None = 0,
) -> Dict[str, Any]:
    """
    批量修改规则：
    - Excel 格式与 import_excel_to_db 一致
    - 仅当 SKU + 产品条码 + ASIN 三者都不为空，且能匹配到 DB 同一条 goods 时才更新
    - 其它情况：跳过（skipped）
    - 单行数据格式错误/异常：failed
    """
    updated: int = 0
    skipped_items: List[Dict[str, Any]] = []
    failed_items: List[Dict[str, Any]] = []

    logger.info("开始批量修改 Excel：sheet=%s, file_size=%d bytes", sheet_name, len(file_bytes))

    # 1) 校验 sheet 参数（复用你导入的逻辑）
    sheet_names = sniff_sheets(file_bytes)
    if sheet_name is None:
        sheet_arg: str | int = 0
    elif isinstance(sheet_name, int):
        if sheet_name < 0 or sheet_name >= len(sheet_names):
            raise ValueError(f"工作表索引越界: {sheet_name}；可用工作表：{sheet_names}")
        sheet_arg = sheet_name
    else:
        s = str(sheet_name).strip()
        if s.isdigit():
            idx = int(s)
            if idx < 0 or idx >= len(sheet_names):
                raise ValueError(f"工作表索引越界: {idx}；可用工作表：{sheet_names}")
            sheet_arg = idx
        else:
            if s not in sheet_names:
                raise ValueError(f"未找到名为 '{s}' 的工作表；可用工作表：{sheet_names}")
            sheet_arg = s

    # 2) 读 DataFrame（与导入一致）
    df = pd.read_excel(
        io.BytesIO(file_bytes),
        sheet_name=sheet_arg,
        engine="openpyxl",
        dtype=str,
        keep_default_na=True,
    )
    df.rename(columns={c: _clean_header(c) for c in df.columns}, inplace=True)

    material_mode = _detect_material_mode(list(df.columns))

    # 清洗 ID 字段（与导入一致）
    for col in ID_STR_COLS:
        if col in df.columns:
            df[col] = df[col].map(_clean_id_string)

    # 去掉空行（SKU 和 产品都空则去掉）——沿用你导入的逻辑
    if "SKU" in df.columns and "产品" in df.columns:
        df = df[~(df.get("SKU").isna() & df.get("产品").isna())]

    total = int(len(df))
    logger.info("开始逐行批量修改：rows=%d, material_mode=%s", total, material_mode)

    # 3) 主循环：逐行解析 -> 三键匹配 -> update
    for idx, row in df.iterrows():
        row_no = int(idx) + 2  # Excel 行号（含表头）
        try:
            payload = _row_to_goods_in(row, material_mode=material_mode)

            sku = (payload.销售信息.SKU or "").strip()
            barcode = (payload.销售信息.产品条码 or "").strip()
            asin = (payload.销售信息.ASIN or "").strip()

            # ✅ 必须三键齐全
            if not sku or not barcode or not asin:
                skipped_items.append({
                    "row": row_no,
                    "reason": "missing_keys",
                    "message": "SKU/产品条码/ASIN 必须同时填写才允许批量修改",
                    "sku": sku or None,
                    "barcode": barcode or None,
                    "asin": asin or None,
                })
                continue

            # ✅ 三键匹配到同一条 goods
            q = await session.execute(
                select(Goods)
                .options(
                    selectinload(Goods.supply),
                    selectinload(Goods.customs),
                    selectinload(Goods.materials),
                )
                .where(
                    and_(
                        Goods.sku == sku,
                        Goods.barcode == barcode,
                        Goods.asin == asin,
                    )
                )
            )

            g = q.scalar_one_or_none()
            if not g:
                skipped_items.append({
                    "row": row_no,
                    "reason": "not_found",
                    "message": "未找到 SKU+产品条码+ASIN 同时匹配的商品，已跳过",
                    "sku": sku,
                    "barcode": barcode,
                    "asin": asin,
                })
                continue
            if not would_change_goods(g, payload):
                skipped_items.append({
                    "row": row_no,
                    "reason": "no_change",
                    "message": "按更新规则不会改变任何字段，已跳过",
                    "sku": sku,
                    "barcode": barcode,
                    "asin": asin,
                })
                continue

            # ✅ 执行更新（复用仓储的 update 逻辑）
            # 注意：我们先通过三键确认唯一记录，再用 barcode 更新，不会误改其它商品
            updated_goods = await update_goods_by_barcode(session, barcode, payload)
            if not updated_goods:
                skipped_items.append({
                    "row": row_no,
                    "reason": "update_target_missing",
                    "message": "根据条码未找到可更新商品，已跳过（请检查数据一致性）",
                    "sku": sku,
                    "barcode": barcode,
                    "asin": asin,
                })
                continue

            updated += 1

            if updated % 200 == 0:
                logger.info("批量修改进度：updated=%d, skipped=%d, failed=%d", updated, len(skipped_items), len(failed_items))

        except Exception as e:
            msg = str(e)
            failed_items.append({
                "row": row_no,
                "reason": "exception",
                "message": msg,
            })
            logger.exception("批量修改失败 row=%d：%s", row_no, msg)

    skipped = len(skipped_items)
    failed = len(failed_items)

    logger.info("批量修改完成：updated=%d, skipped=%d, failed=%d, total=%d", updated, skipped, failed, total)

    return {
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
        "total": total,
        "skipped_items": skipped_items,
        "failed_items": failed_items,
    }