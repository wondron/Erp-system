# app/adapters/http/goods_import.py
from __future__ import annotations  # 推荐：延迟解析注解，避免此类导入顺序问题
from sqlalchemy.ext.asyncio import AsyncSession  # 必须：提供 AsyncSession 类型

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
    return int(s) if s.isdigit() else s  # "0"→0；"Sheet1" 保持字符串



@router.post("/import", summary="从Excel导入商品数据")
async def import_goods(
    file: UploadFile = File(..., description="Excel 文件（.xlsx）"),
    sheet: str | int | None = Query(default=0, description="工作表名或索引，默认第1个"),
    upsert: bool = Query(default=True, description="同SKU是否跳过/更新（当前实现为跳过）"),
    session: AsyncSession = Depends(get_db),
):
    # ---------- 入口日志 ----------
    logger.info(
        "收到商品导入请求：filename=%s, sheet=%s, upsert=%s",
        file.filename,
        sheet,
        upsert,
    )

    if not file.filename.lower().endswith(".xlsx"):
        logger.warning(
            "导入失败：文件类型不支持 (%s)",
            file.filename,
        )
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 文件")

    content = await file.read()
    logger.info("Excel 文件读取完成：size=%d bytes", len(content))

    try:
        sheet_arg = _normalize_sheet_arg(sheet)

        inserted, skipped, errors = await import_excel_to_db(
            session,
            content,
            sheet_name=sheet_arg,
            upsert_by_sku=upsert,
        )

        # ---------- 成功日志 ----------
        logger.info(
            "商品导入完成：filename=%s, inserted=%d, skipped=%d, errors=%d",
            file.filename,
            inserted,
            skipped,
            len(errors),
        )

        return {
            "filename": file.filename,
            "inserted": inserted,
            "skipped": skipped,
            "errors": errors,
        }

    except Exception as e:
        # ---------- 异常日志 ----------
        logger.error(
            "商品导入异常：filename=%s, sheet=%s, error=%s",
            file.filename,
            sheet,
            str(e),
            exc_info=True,   # ✅ 一定要有
        )
        # 友好报错：附上可用工作表名
        try:
            sheets = sniff_sheets(content)
            raise HTTPException(
                status_code=400,
                detail=f"{e}；可用工作表：{sheets}",
            )
        except Exception:
            raise HTTPException(status_code=400, detail=str(e))