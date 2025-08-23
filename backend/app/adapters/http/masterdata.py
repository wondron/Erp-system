# backend/app/adapters/http/masterdata.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.db import get_db
from app import models

router = APIRouter()

class ItemIn(BaseModel):
    sku: str
    name: str
    uom: str

@router.post("/items")
async def create_item(item: ItemIn, db: AsyncSession = Depends(get_db)):
    obj = models.Item(**item.dict())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj
    