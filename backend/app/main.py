from fastapi import FastAPI
from app.adapters.http.routes import register_routes
from app.infrastructure.db import init_db


app = FastAPI(title="ERP System")


# init DB
@app.on_event("startup")
async def startup():
    await init_db()


# register all bounded context routes
register_routes(app)