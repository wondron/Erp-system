# app/infrastructure/services/goods_importer.py
from __future__ import annotations
import io
import re
from decimal import Decimal
from typing import Any, Dict, List, Tuple

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import GoodsIn, SalesInfoIn, SupplyInfoIn, CustomsInfoIn, ProductionIn
from app.infrastructure.repositories_goods import create_goods, get_goods_by_sku


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


def _to_str(val) -> str | None:
    """文本统一清洗：空/NaN/'nan'/'none'/'null' -> None，其余去首尾空白。"""
    if pd.isna(val) or val == "":
        return None
    s = str(val).strip()
    if s == "" or s.lower() in ("nan", "none", "null"):
        return None
    return s


def _to_decimal(val) -> Decimal | None:
    if pd.isna(val) or val == "":
        return None
    try:
        return Decimal(str(val))
    except Exception:
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


def _row_to_goods_in(row: pd.Series) -> GoodsIn:
    """将一行 DataFrame 转为入库的 Pydantic 对象（已清理 NaN/空值）"""

    # 销售信息
    sales_data: Dict[str, Any] = {}
    for xls, field in SALES_COLS.items():
        v = row.get(xls)
        if field in ("销售价",):
            sales_data[field] = _to_decimal(v)
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
            supply_data[field] = _to_decimal(v)
        else:
            supply_data[field] = _to_str(v)

    # 报关信息
    customs_data: Dict[str, Any] = {}
    for xls, field in CUSTOMS_COLS.items():
        v = row.get(xls)
        customs_data[field] = _to_decimal(v) if field in ("申报价",) else _to_str(v)

    # 生产配套：仅在清洗后非空才写入，避免 NaN 混入 JSON
    prod_root: Dict[str, Any] = {}
    for col in row.index:
        c = str(col)
        if not c.startswith("材料"):
            continue
        val = row[col]
        cleaned = _to_decimal(val) if c.endswith("用量") else _to_str(val)
        if cleaned is not None:
            prod_root[c] = cleaned

    return GoodsIn(
        销售信息=SalesInfoIn(**sales_data),
        供应信息=SupplyInfoIn(**supply_data),
        报关信息=CustomsInfoIn(**customs_data),
        生产配套=ProductionIn(root=prod_root),  # pydantic v2 RootModel
    )


async def import_excel_to_db(
    session: AsyncSession,
    file_bytes: bytes,
    *,
    sheet_name: str | int | None = 0,
    upsert_by_sku: bool = True,
) -> Tuple[int, int, List[Dict[str, Any]]]:
    # --- 先初始化，避免任意异常路径出现“未关联的局部变量” ---
    ok: int = 0
    skipped: int = 0
    errors: List[Dict[str, Any]] = []

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

    # --- 读取 DataFrame：关键是 dtype=str，先全部当字符串读入 ---
    df = pd.read_excel(
        io.BytesIO(file_bytes),
        sheet_name=sheet_arg,
        engine="openpyxl",
        dtype=str,            # 防止把 SKU/条码/ASIN 读成数字或科学计数
        keep_default_na=True, # 空单元格保持 NaN，后续统一清洗
    )

    # 清洗表头
    df.rename(columns={c: _clean_header(c) for c in df.columns}, inplace=True)

    # 清洗 ID 字段
    for col in ID_STR_COLS:
        if col in df.columns:
            df[col] = df[col].map(_clean_id_string)

    # 去掉空行（SKU 和 产品都空则跳过）
    has_sku = "SKU" in df.columns
    has_product = "产品" in df.columns
    if has_sku and has_product:
        df = df[~(df.get("SKU").isna() & df.get("产品").isna())]

    # --- 主循环 ---
    for idx, row in df.iterrows():
        try:
            payload = _row_to_goods_in(row)
            sku = payload.销售信息.SKU

            if upsert_by_sku and sku:
                exist = await get_goods_by_sku(session, sku)
                if exist:
                    skipped += 1
                    errors.append({"row": int(idx) + 2, "error": f"已存在 SKU: {sku}"})
                    continue

            await create_goods(session, payload)
            ok += 1

        except Exception as e:
            errors.append({"row": int(idx) + 2, "error": str(e)})

    return ok, skipped, errors
