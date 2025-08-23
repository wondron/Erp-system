# backend/app/adapters/http/inventory.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.infrastructure.db import get_db
from app import models

router = APIRouter()

@router.get("/stock/{item_id}")
async def get_stock(item_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.PurchaseOrderLine).where(models.PurchaseOrderLine.item_id == item_id))
    lines = result.scalars().all()
    qty = sum(l.qty for l in lines)
    return {"item_id": item_id, "qty_on_hand": qty}