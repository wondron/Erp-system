# app/adapters/http/customs.py
from __future__ import annotations

import io
import logging
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from starlette.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
from app.infrastructure.db import get_db

# ✅ 直接复用你已有的业务函数
from app.app_tasks.process_BaoGuan import _handle_excel_with_baoguan


logger = logging.getLogger("api.customs")
router = APIRouter(prefix="/customs", tags=["customs"])


@router.post(
    "/pack",
    summary="上传 Excel 并生成报关资料 ZIP（5 个 xlsx）",
)
async def customs_pack_zip(
    file: UploadFile = File(..., description="Excel 文件（.xlsx）"),
    session: AsyncSession = Depends(get_db),  # 预留，当前不使用
):
    logger.info("收到报关生成请求：filename=%s", file.filename)

    if not file.filename:
        raise HTTPException(status_code=400, detail="未收到文件名")

    if not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 文件")

    raw = await file.read()
    # logger.info("Excel 文件读取完成：size=%d bytes", len(raw))

    try:
        zip_bytes = _handle_excel_with_baoguan(raw)
        ts = datetime.now().strftime("%y%m%d%H%M%S")
        filename = f"customs_{ts}.zip"

        buf = io.BytesIO(zip_bytes)
        buf.seek(0)

        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("报关生成失败：%s", str(e), exc_info=True)
        raise HTTPException(status_code=400, detail=f"生成失败：{e}")


@router.get(
    "/template",
    summary="下载报关资料模板 Excel",
)
async def download_customs_template():
    template_path = Path("app/app_tasks/resource/customs_template.xlsx")

    if not template_path.exists() or not template_path.is_file():
        raise HTTPException(status_code=404, detail=f"模板文件不存在：{template_path}")

    try:
        data = template_path.read_bytes()
    except Exception as e:
        logger.error("读取模板失败：%s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"读取模板失败：{e}")
    filename = f"customs_template.xlsx"
    buf = io.BytesIO(data)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )