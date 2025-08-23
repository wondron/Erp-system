# backend/app/adapters/http/purchasing.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.db import get_db
from app import models

router = APIRouter()

class PurchaseOrderIn(BaseModel):
    supplier_id: int
    item_id: int
    qty: float
    price: float

@router.post("/orders")
async def create_po(po: PurchaseOrderIn, db: AsyncSession = Depends(get_db)):
    order = models.PurchaseOrder(supplier_id=po.supplier_id)
    line = models.PurchaseOrderLine(item_id=po.item_id, qty=po.qty, price=po.price)
    order.lines.append(line)
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return {"id": order.id, "status": order.status, "lines": [ {"item_id": l.item_id, "qty": l.qty, "price": l.price} for l in order.lines ]}