# app/adapters/http/goods_query.py
from __future__ import annotations
from typing import Literal, List, Optional
from decimal import Decimal
from datetime import datetime
from pathlib import Path
import math

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field
from types import SimpleNamespace as NS
from sqlalchemy.ext.asyncio import AsyncSession
from dataclasses import dataclass

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
    export_labels_pdf,
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
class SupplyBlock(BaseModel):
    vendor: Optional[str] = None
    purchase_price: Optional[float] = None
    pkg_size: Optional[str] = None
    pkg_weight: Optional[float] = None
    packing_ratio: Optional[int] = None
    carton_l: Optional[int] = None
    carton_w: Optional[int] = None
    carton_h: Optional[int] = None

class CustomsBlock(BaseModel):
    name_cn: Optional[str] = None
    name_en: Optional[str] = None
    hscode: Optional[str] = None
    declaration: Optional[str] = None
    declared_price: Optional[float] = None
    image_note: Optional[str] = None

class MaterialItem(BaseModel):
    name: str = Field(..., description="材料名称，对应 material_name")
    qty: float = Field(..., description="用量，对应 quantity")

class GoodsSerializedIn(BaseModel):
    # 核心字段（全部可选以便做“部分更新”；若你想强制某些字段必填可改为必填）
    id: Optional[int] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    season: Optional[str] = None
    product_name: Optional[str] = None
    channel: Optional[str] = None
    owner: Optional[str] = None
    sku: Optional[str] = None
    asin: Optional[str] = None
    barcode: Optional[str] = None
    carton_mark: Optional[str] = None
    item_no: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    sale_price: Optional[float] = None

    # 嵌套块
    supply: Optional[SupplyBlock] = None
    customs: Optional[CustomsBlock] = None
    materials: Optional[List[MaterialItem]] = None


@dataclass
class _Patch:
    销售信息: object | None = None
    供应信息: object | None = None
    报关信息: object | None = None
    生产配套: object | None = None
    replace_materials: bool = True   # 默认 True：替换模式


@router.put("/by-barcode/{barcode}", summary="根据产品条码和 JSON 数据修改信息（按 serialize_goods 结构）")
async def update_by_barcode_api(
    barcode: str,
    body: GoodsSerializedIn,
    session: AsyncSession = Depends(get_db),
    replace_materials: bool = Query(True, description="是否全量替换材料"),
):
    patch = _Patch(replace_materials=replace_materials)

    # ---- 销售信息（把英文字段映射到仓储期望的中文字段名）----
    if any([
        body.sku, body.asin, body.product_name, body.category, body.subcategory, body.carton_mark, body.item_no,
        body.season, body.channel, body.owner, body.color, body.size, body.sale_price is not None
    ]):
        patch.销售信息 = NS(
            SKU=body.sku,
            ASIN=body.asin,
            产品=body.product_name,
            大类目=body.category,
            小品类=body.subcategory,
            季节性=body.season,
            销售渠道=body.channel,
            责任人=body.owner,
            颜色=body.color,
            尺寸=body.size,
            销售价=(Decimal(str(body.sale_price)) if body.sale_price is not None else None),
            产品条码=barcode,           # 以路径参数为准
            自定义箱唛=body.carton_mark,
            货号=body.item_no,
        )

    # ---- 供应信息（supply → 中文字段）----
    if body.supply is not None:
        s = body.supply
        patch.供应信息 = NS(
            供应商=s.vendor,
            采购价=(Decimal(str(s.purchase_price)) if s.purchase_price is not None else None),
            单品包装尺寸=s.pkg_size,
            单品包装重量=(Decimal(str(s.pkg_weight)) if s.pkg_weight is not None else None),
            装箱系数=s.packing_ratio,
            外箱长=s.carton_l,
            外箱宽=s.carton_w,
            外箱高=s.carton_h,
        )

    # ---- 报关信息（customs → 中文字段）----
    if body.customs is not None:
        c = body.customs
        patch.报关信息 = NS(
            中文品名=c.name_cn,
            英文品名=c.name_en,
            海关编码=c.hscode,
            申报要素=c.declaration,
            申报价=(Decimal(str(c.declared_price)) if c.declared_price is not None else None),
            图片=c.image_note,
        )

    # ---- 生产配套（materials 列表 → 传给仓储；仓储侧下节会兼容 list）----
    if body.materials is not None:
        patch.生产配套 = [{"name": m.name, "qty": Decimal(str(m.qty))} for m in body.materials]

    g = await update_goods_by_barcode(session, barcode, patch)
    if not g:
        raise HTTPException(status_code=404, detail="商品不存在")
    return serialize_goods(g)



#---------------------------------------------------------------------------------
@router.get("/download_template", summary="下载商品导入模板")
async def download_template():
    BASE_DIR = Path(__file__).resolve().parents[2]   # backend/app
    TEMPLATE_PATH = BASE_DIR / "app_tasks" / "resource" / "product_temp.xlsx"
    if not TEMPLATE_PATH.exists():
        raise HTTPException(status_code=404, detail="模板文件不存在")

    return FileResponse(
        path=TEMPLATE_PATH,
        filename=TEMPLATE_PATH.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )



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


# ------------------------------ 6) 根据条码和数量打印PDF ------------------------------
class ExportNum(BaseModel): 
    name: str = Field(..., description="要打印的条码或箱唛") 
    qty: int = Field(..., gt=0, description="数量(>0)") 

class DayinData(BaseModel): 
    materials: Optional[List[ExportNum]] = None 

@router.put("/print_pdf", summary="根据产品条码或箱唛和数量生成商品条码PDF")
async def generate_labels_pdf(
    body: DayinData,
    session: AsyncSession = Depends(get_db),
    label_type: Literal["barcode", "carton_mark"] = Query(
        "barcode",
        description="选择按条码(barcode) 还是按箱唛(carton_mark) 生成标签"
    ),
):
    items = body.materials or []
    if not items:
        raise HTTPException(status_code=400, detail="未输入任何条码或箱唛")
    
    print_data = {}
    add_num = 0
    for item in items:
        if item.qty == -1:
            if label_type == 'barcode':
                add_num = 24
            else:
                add_num = 6
        else:
            if label_type == 'barcode':
                add_num = math.ceil(item.qty / 23) * 24
            else:
                add_num = item.qty

        if item.name in print_data:
            print_data[item.name] += add_num
        else:
            print_data[item.name] = add_num

    stream = await export_labels_pdf(session, print_data, label_type)
    ts = datetime.now().strftime("%y%m%d%H%M")
    filename = f"pdf-{ts}.pdf"

    return StreamingResponse(
        stream,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )