from fastapi import APIRouter
from app.adapters.http import users
from app.adapters.http import login
from app.adapters.http import files
from app.adapters.http import goods_import
from app.adapters.http import goods_query

api_router = APIRouter()
api_router.include_router(users.router)
api_router.include_router(login.router)
api_router.include_router(files.router)
api_router.include_router(goods_import.router)
api_router.include_router(goods_query.router)