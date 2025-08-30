from fastapi import APIRouter
from app.adapters.http import users
from app.adapters.http import login
from app.adapters.http import files

api_router = APIRouter()
api_router.include_router(users.router)
api_router.include_router(login.router)
api_router.include_router(files.router)