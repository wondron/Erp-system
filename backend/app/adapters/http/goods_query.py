# app/adapters/http/goods_query.py
from __future__ import annotations
from typing import Literal, List, Optional
from decimal import Decimal
from datetime import datetime
from pathlib import Path
import math, logging, os
from types import SimpleNamespace as NS
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field, field_validator
from types import SimpleNamespace as NS
from sqlalchemy.ext.asyncio import AsyncSession
from dataclasses import dataclass
from sqlalchemy import select
from app.infrastructure.orm_models import Goods

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
    export_goods_xlsx_by_barcodes, 
    export_carton_pdf,
    export_goods_pdf,
    export_labels_pdf,
    list_goods_with_count,
    list_all_barcodes,
    export_goods_xlsx_all,
)

# 如果你使用了“轻量 Update Schema”，记得从对应位置导入：
# from app.domain.models_update import GoodsUpdate
from app.domain.models import GoodsIn  # 也可以用你已存在的 Update 版 Schema

router = APIRouter(prefix="/goods", tags=["goods"])
logger = logging.getLogger('repo.goods')

# ------------------------------ 1) 获取所有商品（分页） ------------------------------
@router.get("", summary="获取所有商品信息（分页+排序+总数）")
async def get_all_goods(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    size: int = Query(50, ge=1, le=200, description="每页条数"),
    order_by: str = Query("id", description="排序字段名，例如 sku, asin, barcode, sale_price等"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="排序顺序 asc 或 倒序 desc"),
    session: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * size
    items, total = await list_goods_with_count(
        session, offset=offset, limit=size, order_by=order_by, order=order
    )
    logger.info(f"获取商品列表 page={page}, size={size}, total={total}, order_by={order_by} {order}")
    return {
        "page": page,
        "size": size,
        "total": total,
        "order_by": order_by,
        "order": order,
        "items": [serialize_goods(g) for g in items],
    }

@router.get("/barcodes", summary="获取所有商品条码列表")
async def get_all_barcodes(
    session: AsyncSession = Depends(get_db),
):
    barcodes = await list_all_barcodes(session)
    return {"items": barcodes, "total": len(barcodes)}


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
    name: str = Field(..., description="材料名称")
    qty: Decimal = Field(..., description="用量")
    unit: Optional[str] = Field(None, description="用量单位；不传默认=件")

    @field_validator("unit", mode="before")
    @classmethod
    def default_unit(cls, v):
        return v or "件"

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

def _norm_str(x: Optional[str]) -> Optional[str]:
    if x is None:
        return None
    s = str(x).strip()
    return s if s else None

async def _ensure_unique_on_update(
    session: AsyncSession,
    *,
    current_goods_id: int,
    sku: Optional[str],
    asin: Optional[str],
    barcode: str,
) -> None:
    """
    预检测唯一性（排除当前 goods）。
    - sku 唯一（你表上已有 uq_goods_sku）
    - barcode 唯一（你表上已有 uq_goods_barcode）
    - asin 若你也要求唯一，这里做预检测；建议 DB 也加 UniqueConstraint("asin") + 允许多 NULL
    """
    # SKU
    if sku:
        q = await session.execute(
            select(Goods.id).where(Goods.sku == sku, Goods.id != current_goods_id)
        )
        if q.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail=f"SKU 已存在：{sku}")

    # ASIN
    if asin:
        q = await session.execute(
            select(Goods.id).where(Goods.asin == asin, Goods.id != current_goods_id)
        )
        if q.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail=f"ASIN 已存在：{asin}")

    # BARCODE（路径参数是“当前条码”；如果你允许改条码，需要对“目标新条码”做检测）
    # 这里按你的逻辑：以路径参数 barcode 为准，不允许 body.barcode 改；所以只做“数据库里是否有重复条码且不是当前 goods”
    if barcode:
        q = await session.execute(
            select(Goods.id).where(Goods.barcode == barcode, Goods.id != current_goods_id)
        )
        if q.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail=f"条码已存在：{barcode}")

@router.put("/by-barcode/{barcode}", summary="根据产品条码和 JSON 数据修改信息（按 serialize_goods 结构）")
async def update_by_barcode_api(
    barcode: str,
    body: GoodsSerializedIn,
    session: AsyncSession = Depends(get_db),
    replace_materials: bool = Query(True, description="是否全量替换材料"),
):
    barcode = _norm_str(barcode) or ""
    if not barcode:
        raise HTTPException(status_code=400, detail="条码不能为空")

    logger.info("更新商品信息：条码=%s，数据=%s", barcode, body)
    
    # 先拿到当前商品（用于排除自己 + 如果不存在直接 404）
    cur_res = await session.execute(select(Goods).where(Goods.barcode == barcode))
    cur = cur_res.scalar_one_or_none()
    if not cur:
        raise HTTPException(status_code=404, detail="商品不存在")

    # 规范化字段
    sku = _norm_str(body.sku)
    asin = _norm_str(body.asin)

    # ✅ 唯一性预检测（sku/asin/barcode）
    await _ensure_unique_on_update(
        session,
        current_goods_id=cur.id,
        sku=sku,
        asin=asin,
        barcode=barcode,
    )

    patch = _Patch(replace_materials=replace_materials)

    # ---- 销售信息（英文字段映射到中文字段名）----
    if any([
        sku, asin, body.product_name, body.category, body.subcategory, body.carton_mark, body.item_no,
        body.season, body.channel, body.owner, body.color, body.size, body.sale_price is not None
    ]):
        patch.销售信息 = NS(
            SKU=sku,
            ASIN=asin,
            产品=body.product_name,
            大类目=body.category,
            小品类=body.subcategory,
            季节性=body.season,
            销售渠道=body.channel,
            责任人=body.owner,
            颜色=body.color,
            尺寸=body.size,
            销售价=(Decimal(str(body.sale_price)) if body.sale_price is not None else None),
            产品条码=barcode,  # ✅ 仍以路径参数为准
            自定义箱唛=body.carton_mark,
            货号=body.item_no,
        )

    # ---- 供应信息 ----
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

    # ---- 报关信息 ----
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

    # ---- 生产配套（materials：加 unit；不传默认 件）----
    if body.materials is not None:
        patch.生产配套 = [
            {
                "name": _norm_str(m.name),
                "qty": Decimal(str(m.qty)),
                "unit": _norm_str(m.unit) or "件",
            }
            for m in body.materials
            if _norm_str(m.name) is not None
        ]

    g = await update_goods_by_barcode(session, barcode, patch)
    if not g:
        # 理论上不会到这（上面已查 cur），留着兜底
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
    logger.info("收到删除请求（单条），barcode=%s", barcode)

    try:
        backup_path = await _backup_all_goods_before_delete(
            session, prefix="goods_delete"
        )
    except Exception:
        logger.exception("删除前备份失败，已中止删除，barcode=%s", barcode)
        raise HTTPException(status_code=500, detail="删除前备份失败，操作已中止")

    logger.info("开始执行删除（单条），barcode=%s", barcode)
    ok = await delete_goods_by_barcode(session, barcode)

    if not ok:
        logger.warning("删除失败（商品不存在），barcode=%s", barcode)
        raise HTTPException(status_code=404, detail="商品不存在")

    logger.info(
        "删除成功（单条），barcode=%s，backup=%s",
        barcode, backup_path
    )
    return {"deleted": True, "barcode": barcode, "backup": backup_path}



@router.delete("/by-barcodes", summary="根据产品条码列表批量删除")
async def delete_by_barcodes_api(
    payload: BarcodesIn,
    session: AsyncSession = Depends(get_db),
):
    barcodes = payload.barcodes or []
    logger.info(
        "收到删除请求（批量），count=%d",
        len(barcodes)
    )

    try:
        backup_path = await _backup_all_goods_before_delete(
            session, prefix="goods_delete"
        )
    except Exception:
        logger.exception("批量删除前备份失败，已中止删除")
        raise HTTPException(status_code=500, detail="删除前备份失败，操作已中止")

    logger.info("开始执行删除（批量），count=%d", len(barcodes))
    result = await delete_goods_by_barcodes(session, barcodes)

    logger.info(
        "批量删除完成，deleted=%d，not_found=%d，backup=%s",
        result.get("count", 0),
        len(result.get("not_found", [])),
        backup_path,
    )

    result["backup"] = backup_path
    return result


def _backup_dir() -> Path:
    # goods_query.py: backend/app/adapters/http/goods_query.py
    # parents[3] -> backend
    base_dir = Path(__file__).resolve().parents[3]
    d = base_dir / "backup"
    if not d.exists():
        d.mkdir(parents=True, exist_ok=True)
        logger.info("创建备份目录：%s", d)
    return d

async def _backup_all_goods_before_delete(session: AsyncSession, *, prefix: str) -> str:
    logger.info("开始执行删除前全量备份，prefix=%s", prefix)

    stream = await export_goods_xlsx_all(session, sheet_name="Sheet1")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{ts}.xlsx"
    save_path = _backup_dir() / filename

    stream.seek(0)
    with open(save_path, "wb") as f:
        f.write(stream.read())

    logger.info("删除前全量备份完成，文件=%s", save_path)
    return str(save_path)


async def _backup_all_goods_before_delete(session: AsyncSession, *, prefix: str) -> str:
    stream = await export_goods_xlsx_all(session, sheet_name="Sheet1")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{ts}.xlsx"
    save_path = _backup_dir() / filename
    stream.seek(0)
    with open(save_path, "wb") as f:
        f.write(stream.read())
    return str(save_path)


# ------------------------------ 5) 根据条码导出 Excel ------------------------------
@router.post("/export/by-barcodes", summary="根据条码集合导出（按模板）")
async def export_goods_by_barcodes_api(
    payload: BarcodesIn,
    session: AsyncSession = Depends(get_db),
):
    logger.info(f'调用export_goods_by_barcodes_api，条码集合:{payload.barcodes}')
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
    logger.info(f'调用export_product_label，barcode:{barcode}')
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
        "carton_mark",
        description="选择按条码(barcode) 还是按箱唛(carton_mark) 生成标签"
    ),
):
    # label_type = 'carton_mark'
    items = body.materials or []
    logger.info(f'调用generate_labels_pdf，items:{items}, type:{label_type}')
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
                add_num = math.ceil(item.qty / 6) * 6

        if item.name in print_data:
            print_data[item.name] += add_num
        else:
            print_data[item.name] = add_num

    stream = await export_labels_pdf(session, print_data, label_type)
    ts = datetime.now().strftime("%y%m%d%H%M")

    filename = f"pdf-{ts}.pdf"
    # save_dir = "/data/Erp-system/export"
    # os.makedirs(save_dir, exist_ok=True)
    # save_path = os.path.join(save_dir, filename)
    # # 注意：stream 是一个 BytesIO 对象
    # stream.seek(0)
    # with open(save_path, "wb") as f:
    #     f.write(stream.read())
    # stream.seek(0)  # 重置指针供后续 StreamingResponse 读取

    return StreamingResponse(
        stream,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )