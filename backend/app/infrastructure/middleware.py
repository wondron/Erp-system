from __future__ import annotations
from uuid import uuid4
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response



class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        rid = request.headers.get("X-Request-ID") or str(uuid4())
        # 透传给后续 handler
        request.state.request_id = rid
        response: Response = await call_next(request)
        # 回写到响应头，便于排查
        response.headers["X-Request-ID"] = rid
        return response