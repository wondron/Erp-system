# app/infrastructure/services/goods_importer.py
from __future__ import annotations
import io
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Tuple

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.infrastructure.orm_models import Goods 
from app.domain.models import GoodsIn, SalesInfoIn, SupplyInfoIn, CustomsInfoIn, ProductionIn, MaterialItemIn
from app.infrastructure.repositories_goods import create_goods, get_goods_by_sku
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
) -> Tuple[int, int, List[Dict[str, Any]]]:
    ok: int = 0
    skipped: int = 0
    errors: List[Dict[str, Any]] = []

    logger.info(
        "开始导入 Excel：sheet=%s, upsert_by_sku=%s, file_size=%d bytes",
        sheet_name, upsert_by_sku, len(file_bytes),
    )

    # --- 嗅探工作表，并做 sheet 参数合法性校验 ---
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

    # --- 读取 DataFrame：全部当字符串读入 ---
    df = pd.read_excel(
        io.BytesIO(file_bytes),
        sheet_name=sheet_arg,
        engine="openpyxl",
        dtype=str,
        keep_default_na=True,
    )

    # 清洗表头
    df.rename(columns={c: _clean_header(c) for c in df.columns}, inplace=True)
    material_mode = _detect_material_mode(list(df.columns))

    # 清洗 ID 字段（SKU/ASIN/条码...）
    for col in ID_STR_COLS:
        if col in df.columns:
            df[col] = df[col].map(_clean_id_string)

    # 去掉空行（SKU 和 产品都空则跳过）
    if "SKU" in df.columns and "产品" in df.columns:
        before = len(df)
        df = df[~(df.get("SKU").isna() & df.get("产品").isna())]
        after = len(df)
        if after != before:
            logger.info("清理空行：before=%d, after=%d, removed=%d", before, after, before - after)

    # =========================
    # ✅ 批量预取：数据库中已存在的 SKU / barcode / ASIN
    # =========================
    sku_list: list[str] = []
    barcode_list: list[str] = []
    asin_list: list[str] = []

    if "SKU" in df.columns:
        sku_list = [s for s in df["SKU"].dropna().astype(str).map(str.strip).tolist() if s]
        sku_list = list(dict.fromkeys(sku_list))  # 保序去重

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

    # =========================
    # ✅ Excel 内部去重（同文件重复也拦）
    # =========================
    seen_skus: set[str] = set()
    seen_barcodes: set[str] = set()
    seen_asins: set[str] = set()

    # --- 主循环 ---
    total_rows = len(df)
    logger.info("开始逐行导入：rows=%d, material_mode=%s", total_rows, material_mode)

    for idx, row in df.iterrows():
        row_no = int(idx) + 2  # Excel 行号（含表头）
        try:
            payload = _row_to_goods_in(row, material_mode=material_mode)

            sku = (payload.销售信息.SKU or "").strip()
            barcode = (payload.销售信息.产品条码 or "").strip()
            asin = (payload.销售信息.ASIN or "").strip()

            # ---- 1) Excel 内部重复：SKU ----
            if sku:
                if sku in seen_skus:
                    skipped += 1
                    errors.append({"row": row_no, "error": f"Excel 内重复 SKU: {sku}"})
                    continue
                seen_skus.add(sku)

            # ---- 2) Excel 内部重复：条码 ----
            if barcode:
                if barcode in seen_barcodes:
                    skipped += 1
                    errors.append({"row": row_no, "error": f"Excel 内重复 条码: {barcode}"})
                    continue
                seen_barcodes.add(barcode)

            # ---- 3) Excel 内部重复：ASIN ----
            if asin:
                if asin in seen_asins:
                    skipped += 1
                    errors.append({"row": row_no, "error": f"Excel 内重复 ASIN: {asin}"})
                    continue
                seen_asins.add(asin)

            # ---- 4) DB 已存在：SKU ----
            if upsert_by_sku and sku and sku in exist_skus:
                skipped += 1
                errors.append({"row": row_no, "error": f"已存在 SKU: {sku}"})
                continue

            # ---- 5) DB 已存在：条码 ----
            if barcode and barcode in exist_barcodes:
                skipped += 1
                errors.append({"row": row_no, "error": f"已存在 条码: {barcode}"})
                continue

            # ---- 6) DB 已存在：ASIN ----
            if asin and asin in exist_asins:
                skipped += 1
                errors.append({"row": row_no, "error": f"已存在 ASIN: {asin}"})
                continue

            await create_goods(session, payload)
            ok += 1

            # ✅ 插入成功后把 key 放入 exist_*，防止后续行再次插入
            if sku:
                exist_skus.add(sku)
            if barcode:
                exist_barcodes.add(barcode)
            if asin:
                exist_asins.add(asin)

            # 可选：每 N 行打一次进度
            if ok % 200 == 0:
                logger.info(
                    "导入进度：ok=%d, skipped=%d, processed=%d/%d",
                    ok, skipped, (row_no - 1), total_rows,
                )

        except Exception as e:
            msg = str(e)
            errors.append({"row": row_no, "error": msg})
            logger.exception("导入失败 row=%d：%s", row_no, msg)

    logger.info("导入完成：ok=%d, skipped=%d, errors=%d", ok, skipped, len(errors))
    return ok, skipped, errors