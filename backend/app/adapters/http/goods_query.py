# app/adapters/http/goods_query.py
from __future__ import annotations
from typing import List, Optional, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

# 异步会话依赖
from app.infrastructure.db import get_db

# 仓储函数
from app.infrastructure.repositories_goods import (
    list_goods,
    get_goods_by_barcodes,
    update_goods_by_barcode,
    delete_goods_by_barcode,
    delete_goods_by_barcodes,
    serialize_goods,
    export_goods_xlsx_by_barcodes,  # ★ 新增：把查询结果导出成 Excel
    export_carton_pdf,
    export_goods_pdf,
)

# 如果你使用了“轻量 Update Schema”，记得从对应位置导入：
# from app.domain.models_update import GoodsUpdate
from app.domain.models import GoodsIn  # 也可以用你已存在的 Update 版 Schema

router = APIRouter(prefix="/goods", tags=["goods"])

# ------------------------------ 1) 获取所有商品（分页） ------------------------------
@router.get("", summary="获取所有商品信息（分页）")
async def get_all_goods(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    size: int = Query(50, ge=1, le=200, description="每页条数"),
    session: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * size
    items = await list_goods(session, offset=offset, limit=size)
    return {
        "page": page,
        "size": size,
        "items": [serialize_goods(g) for g in items],
    }


# ------------------------------ 2) 根据产品条码列表查询 ------------------------------
class BarcodesIn(BaseModel):
    barcodes: List[str]


@router.post("/by-barcodes", summary="根据产品条码的list返回商品信息")
async def goods_by_barcodes(
    payload: BarcodesIn,
    session: AsyncSession = Depends(get_db),
):
    rows = await get_goods_by_barcodes(session, payload.barcodes)
    return [serialize_goods(g) for g in rows]


# ------------------------------ 3) 根据产品条码更新 ------------------------------
class GoodsUpdateAny(BaseModel):
    # 兼容你之前的结构：四大块字段都可选
    销售信息: Optional[dict] = None
    供应信息: Optional[dict] = None
    报关信息: Optional[dict] = None
    生产配套: Optional[dict] = None
    replace_materials: bool = True


@router.put("/by-barcode/{barcode}", summary="根据产品条码和json数据修改信息")
async def update_by_barcode_api(
    barcode: str,
    payload: GoodsUpdateAny,  # 或者替换成你的 GoodsUpdate
    session: AsyncSession = Depends(get_db),
):
    # 将 dict 动态装配成你仓储所需的 Pydantic 对象（若你已经有 GoodsUpdate 类，直接用它即可）
    from app.domain.models import SalesInfoIn, SupplyInfoIn, CustomsInfoIn, ProductionIn

    class _Patch:
        销售信息 = None
        供应信息 = None
        报关信息 = None
        生产配套 = None
        replace_materials: bool = payload.replace_materials

    patch = _Patch()
    if payload.销售信息 is not None:
        patch.销售信息 = SalesInfoIn(**payload.销售信息)
    if payload.供应信息 is not None:
        patch.供应信息 = SupplyInfoIn(**payload.供应信息)
    if payload.报关信息 is not None:
        patch.报关信息 = CustomsInfoIn(**payload.报关信息)
    if payload.生产配套 is not None:
        # 兼容 RootModel
        patch.生产配套 = ProductionIn(__root__=payload.生产配套)

    g = await update_goods_by_barcode(session, barcode, patch)
    if not g:
        raise HTTPException(status_code=404, detail="商品不存在")
    return serialize_goods(g)


# ------------------------------ 4) 根据产品条码删除 ------------------------------
@router.delete("/by-barcode/{barcode}", summary="根据产品条码删除")
async def delete_by_barcode_api(
    barcode: str,
    session: AsyncSession = Depends(get_db),
):
    ok = await delete_goods_by_barcode(session, barcode)
    if not ok:
        raise HTTPException(status_code=404, detail="商品不存在")
    return {"deleted": True, "barcode": barcode}


@router.delete("/by-barcodes", summary="根据产品条码列表批量删除")
async def delete_by_barcodes_api(
    payload: BarcodesIn,
    session: AsyncSession = Depends(get_db),
):
    """
    请求体:
    { "barcodes": ["810101409417", "6901234567890"] }
    """
    result = await delete_goods_by_barcodes(session, payload.barcodes)
    return result


# ------------------------------ 5) 根据条码导出 Excel ------------------------------
@router.post("/export/by-barcodes", summary="根据条码集合导出（按模板）")
async def export_goods_by_barcodes_api(
    payload: BarcodesIn,
    session: AsyncSession = Depends(get_db),
):
    stream = await export_goods_xlsx_by_barcodes(session, payload.barcodes, sheet_name="Sheet1")
    ts = datetime.now().strftime("%y%m%d%H%M")   # 时间戳，形如 20250915_112530
    filename = f"productinfo_{ts}.xlsx"

    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
    
    
@router.post("/export/product-label", summary="根据条码导出产品贴 PDF")
async def export_product_label(
    barcode: str,
    session: AsyncSession = Depends(get_db),
):
    stream = await export_goods_pdf(session, barcode)
    ts = datetime.now().strftime("%y%m%d%H%M")   # 例如 2509161945
    filename = f"product-label-{ts}.pdf"

    return StreamingResponse(
        stream,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )

@router.post("/export/carton-mark", summary="根据条码导出箱唛 PDF")
async def export_carton_mark(
    barcode: str,
    session: AsyncSession = Depends(get_db),
):
    stream = await export_carton_pdf(session, barcode)  # 这里调用你写的 export_carton_pdf
    ts = datetime.now().strftime("%y%m%d%H%M")
    filename = f"carton-mark-{ts}.pdf"

    return StreamingResponse(
        stream,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )