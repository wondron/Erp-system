# app/adapters/http/goods_import.py
from __future__ import annotations  # 推荐：延迟解析注解，避免此类导入顺序问题
from sqlalchemy.ext.asyncio import AsyncSession  # 必须：提供 AsyncSession 类型

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from app.infrastructure.db import get_db
from app.infrastructure.services.goods_importer import import_excel_to_db, sniff_sheets

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
    # 先读取 content，确保 except 分支能用到
    if not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 文件")
    content = await file.read()

    try:
        sheet_arg = _normalize_sheet_arg(sheet)
        inserted, skipped, errors = await import_excel_to_db(
            session, content, sheet_name=sheet_arg, upsert_by_sku=upsert
        )
        return {
            "filename": file.filename,
            "inserted": inserted,
            "skipped": skipped,
            "errors": errors,
        }
    except Exception as e:
        # 友好报错：附上可用工作表名
        try:
            sheets = sniff_sheets(content)
            raise HTTPException(status_code=400, detail=f"{e}；可用工作表：{sheets}")
        except Exception:
            raise HTTPException(status_code=400, detail=str(e))