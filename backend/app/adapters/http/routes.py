from fastapi import APIRouter
from app.adapters.http import users


api_router = APIRouter()
api_router.include_router(users.router)



# 你已有的其他模块：
# api_router.include_router(masterdata.router)
# api_router.include_router(purchasing.router)
# api_router.include_router(inventory.router)