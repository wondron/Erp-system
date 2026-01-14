# app/adapters/http/goods_import.py
from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional, List
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query

from app.infrastructure.db import get_db
from app.infrastructure.services.goods_importer import import_excel_to_db, sniff_sheets

logger = logging.getLogger('api.goods_import')
router = APIRouter(prefix="/goods", tags=["goods"])


def _normalize_sheet_arg(sheet: str | int | None) -> str | int:
    if sheet is None:
        return 0
    if isinstance(sheet, int):
        return sheet
    s = sheet.strip()
    return int(s) if s.isdigit() else s


# -------------------------
# ✅ 方案B：响应模型（不兼容旧 errors）
# -------------------------
class ImportRowItem(BaseModel):
    row: int = Field(..., description="Excel 行号（含表头）")
    reason: str = Field(..., description="机器可读原因码")
    message: str = Field(..., description="给人看的原因")
    sku: Optional[str] = None
    barcode: Optional[str] = None
    asin: Optional[str] = None


class ImportGoodsResp(BaseModel):
    filename: str
    inserted: int
    skipped: int
    failed: int
    total: int
    skipped_items: List[ImportRowItem] = Field(default_factory=list)
    failed_items: List[ImportRowItem] = Field(default_factory=list)


@router.post("/import", summary="从Excel导入商品数据", response_model=ImportGoodsResp)
async def import_goods(
    file: UploadFile = File(..., description="Excel 文件（.xlsx）"),
    sheet: str | int | None = Query(default=0, description="工作表名或索引，默认第1个"),
    upsert: bool = Query(default=True, description="同SKU是否跳过/更新（当前实现为跳过）"),
    session: AsyncSession = Depends(get_db),
):
    logger.info("收到商品导入请求：filename=%s, sheet=%s, upsert=%s", file.filename, sheet, upsert)

    if not file.filename.lower().endswith(".xlsx"):
        logger.warning("导入失败：文件类型不支持 (%s)", file.filename)
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 文件")

    content = await file.read()
    logger.info("Excel 文件读取完成：size=%d bytes", len(content))

    try:
        sheet_arg = _normalize_sheet_arg(sheet)

        result = await import_excel_to_db(
            session,
            content,
            sheet_name=sheet_arg,
            upsert_by_sku=upsert,
        )
        logger.info(
            "商品导入完成：filename=%s, inserted=%d, skipped=%d, failed=%d, total=%d",
            file.filename,
            int(result.get("inserted", 0) or 0),
            int(result.get("skipped", 0) or 0),
            int(result.get("failed", 0) or 0),
            int(result.get("total", 0) or 0),
        )
        return {
            "filename": file.filename,
            **result,
        }

    except Exception as e:
        logger.error(
            "商品导入异常：filename=%s, sheet=%s, error=%s",
            file.filename, sheet, str(e),
            exc_info=True,
        )
        try:
            sheets = sniff_sheets(content)
            raise HTTPException(status_code=400, detail=f"{e}；可用工作表：{sheets}")
        except Exception:
            raise HTTPException(status_code=400, detail=str(e))
