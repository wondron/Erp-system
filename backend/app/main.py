from fastapi import FastAPI
from app.adapters.http.routes import api_router
from fastapi.routing import APIRoute
from app.infrastructure.db import init_db
import logging


logger = logging.getLogger("uvicorn")

app = FastAPI(title="ERP System")
app.include_router(api_router)


# # init DB
# @app.on_event("startup")
# async def startup():
#     await init_db()


# # register all bounded context routes
# register_routes(app)



def _log_routes(app: FastAPI) -> None:
    routes = [r for r in app.routes if isinstance(r, APIRoute)]
    logger.info("---- Mounted Routes ----")
    for r in routes:
        methods = ",".join(sorted(m for m in r.methods if m not in {"HEAD", "OPTIONS"}))
        endpoint = f"{r.endpoint.__module__}.{r.endpoint.__name__}"
        tags = ",".join(r.tags or [])
        logger.info(f"{methods:10} {r.path:35} tags=[{tags}] name={r.name} -> {endpoint}")
    logger.info(f"Total API routes: {len(routes)}")
    
    
@app.on_event("startup")
async def _print_routes_on_startup():
    _log_routes(app)