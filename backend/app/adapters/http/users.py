# backend/app/adapters/http/users.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.infrastructure.db import get_db
from app.infrastructure.repositories_user import UserRepo


# 解耦：把 HTTP 层的数据形状与你的领域对象/ORM 分开，内外各自演进不互相牵制。
# 安全：response_model=UserOut 会过滤多余字段，避免返回敏感信息。
# 可维护：自动文档（/docs）、自动校验（422）、更清晰的类型提示。
class UserCreateIn(BaseModel):
    #发送缺字段/超长/类型不对时，FastAPI 自动返回 422，不用你手写判断
    first_name: str = Field(..., min_length=1, max_length=64)   
    last_name: str = Field(..., min_length=1, max_length=64)
    
    
class UserOut(BaseModel):
    """
    只返回 id/first_name/last_name，避免把内部敏感字段带出去
    """
    id: int  # 用户名字，字符串类型
    first_name: str
    last_name: str   # 用户姓氏，字符串类型



router = APIRouter(prefix="/users", tags=["Users"])


"""
@router.post("")：注册 POST /users 路由（因为 router 前缀是 /users）。
response_model=UserOut：把返回数据按 UserOut 结构过滤并校验（只会返回 id/first_name/last_name）。同时用于自动生成 Swagger 文档。
status_code=201：语义是“已创建”。
"""
@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreateIn, db: Session = Depends(get_db)):
    """
    body: UserCreateIn：请求体用 Pydantic 模型校验（必填、类型、长度），不合规 FastAPI 自动回 422。
    
    这是因为用了pydantic.BaseModel为基类才会去做这个校验
    
    db: Session = Depends(get_db)：通过 依赖注入拿到 SQLAlchemy Session
                 （你在 get_db() 里统一开关事务）。
    """
    repo = UserRepo(db)
    try:
        new_id = repo.add(first_name=body.first_name, last_name=body.last_name)
    except IntegrityError:
        # 例如违反唯一约束时
        raise HTTPException(status_code=409, detail="User already exists")
    # 这里不需要手动 commit；get_db() 在请求结束时会 commit（请在 get_db 中添加 commit）
    u = repo.get(new_id)
    if not u:
        raise HTTPException(status_code=500, detail="Create failed unexpectedly")
    # 显式映射到响应模型，最稳妥
    return UserOut(id=u.id, first_name=u.first_name, last_name=u.last_name)

"""
get("" ---> 空字符串会跟 prefix 拼起来，最终路径是 /users, 如果写成 "/"，最终就是 /users/
"""
@router.get("", response_model=list[UserOut])
def list_users_by_lastname(
    last_name: str = Query(..., description="按姓氏精确匹配"),
    db: Session = Depends(get_db),
):
    repo = UserRepo(db)
    rows = repo.list_by_lastname(last_name)
    # rows 可能是领域对象列表或 dict 列表，两种都兼容：
    out: list[UserOut] = []
    for r in rows:
        if isinstance(r, dict):
            out.append(UserOut(**r))
        else:
            out.append(UserOut(id=r.id, first_name=r.first_name, last_name=r.last_name))
    return out
