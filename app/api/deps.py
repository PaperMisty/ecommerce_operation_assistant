from collections.abc import Callable, Coroutine
from typing import Any
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_session_cookie
from app.infrastructure.database import get_db_session
from app.models.entities import User


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """职责:校验请求中的Session Cookie并返回当前登录用户实体"""
    payload = verify_session_cookie(request)
    user_id = payload.get("user_id")
    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if not user or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用",
        )
    return user


def require_roles(
    *allowed_roles: str,
) -> Callable[..., Coroutine[Any, Any, User]]:
    """职责:构造基于角色权限(RBAC)的路由守卫依赖项"""

    async def _role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        """职责:验证当前登录用户角色是否在允许列表中"""
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足：当前角色 '{current_user.role}' 无权执行此操作，需要角色 {allowed_roles}",
            )
        return current_user

    return _role_checker
