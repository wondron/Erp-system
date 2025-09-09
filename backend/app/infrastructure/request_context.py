# app/infrastructure/request_context.py
from __future__ import annotations
from typing import Optional
from uuid import uuid4
from fastapi import Header, Request, Depends
from pydantic import BaseModel
from app.core.security import decode_access_token  # 下面 B) 会提供

class RequestContext(BaseModel):
    request_id: str
    trace_id: str
    user_id: Optional[str] = None
    username: Optional[str] = None
    roles: list[str] = []
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    token_sub: Optional[str] = None
    token_raw: Optional[str] = None

async def get_request_context(
    request: Request,
    authorization: Optional[str] = Header(default=None, convert_underscores=False),
    x_request_id: Optional[str] = Header(default=None, convert_underscores=False),
    trace_id: Optional[str] = Header(default=None, alias="Trace-Id"),
    x_user_id: Optional[str] = Header(default=None, convert_underscores=False),
):
    # request-id/trace-id 兜底
    rid = x_request_id or request.headers.get("X-Request-ID") or str(uuid4())
    tid = trace_id or request.headers.get("Trace-Id") or request.headers.get("X-Trace-Id") or rid

    # IP / UA
    forwarded = request.headers.get("X-Forwarded-For")
    ip = (forwarded.split(",")[0].strip() if forwarded else request.client.host if request.client else None)
    ua = request.headers.get("User-Agent")

    user_id = x_user_id
    username = None
    roles: list[str] = []
    token_sub = None
    token_raw = None

    # 解析 Bearer Token
    if authorization and authorization.lower().startswith("bearer "):
        token_raw = authorization.split(" ", 1)[1]
        payload = decode_access_token(token_raw)  # 返回 dict 或 None
        if payload:
            token_sub = str(payload.get("sub") or payload.get("id") or "")
            username = payload.get("username") or payload.get("user_name") or payload.get("accountName")
            user_id = user_id or token_sub or payload.get("uid") or payload.get("id")
            scopes = payload.get("scope") or payload.get("scopes") or payload.get("authorities") or []
            if isinstance(scopes, str):
                scopes = [scopes]
            roles = list(scopes)

    return RequestContext(
        request_id=rid, trace_id=tid, ip=ip, user_agent=ua,
        user_id=user_id, username=username, roles=roles,
        token_sub=token_sub, token_raw=token_raw
    )

# FastAPI 依赖注入别名，便于引用
RequestCtx = Depends(get_request_context)
