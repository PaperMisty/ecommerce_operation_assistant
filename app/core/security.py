import secrets
import time
from typing import Any
import bcrypt
from fastapi import Response, Request, HTTPException, status
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from app.core.config import get_settings

# 内存级服务端会话缓存表 (支持快速吊销与状态验证)
_ACTIVE_SESSIONS: dict[str, dict[str, Any]] = {}


def hash_password(plain_password: str) -> str:
    """职责:对明文密码执行Bcrypt哈希加密"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """职责:校验明文密码与哈希值是否匹配"""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except ValueError:
        return False


def _get_serializer() -> URLSafeTimedSerializer:
    """职责:构造带时间戳签名的Session序列化器"""
    settings = get_settings()
    return URLSafeTimedSerializer(settings.session_secret_key, salt="eoa-session-cookie")


def create_session_cookie(
    response: Response,
    user_id: int,
    username: str,
    role: str,
) -> str:
    """职责:创建服务端Session并在响应头种下HttpOnly+Lax+Secure的Cookie"""
    settings = get_settings()
    # 生成随机Session句柄并构建会话载荷
    session_nonce = secrets.token_hex(16)
    payload: dict[str, Any] = {
        "sid": session_nonce,
        "user_id": user_id,
        "username": username,
        "role": role,
        "issued_at": int(time.time()),
    }
    _ACTIVE_SESSIONS[session_nonce] = payload

    # 签名打包Cookie值并写入Set-Cookie响应头
    signed_cookie_val = _get_serializer().dumps(payload)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=signed_cookie_val,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
    return signed_cookie_val


def clear_session_cookie(request: Request, response: Response) -> None:
    """职责:销毁服务端Session并清除客户端Cookie"""
    settings = get_settings()
    raw_cookie = request.cookies.get(settings.session_cookie_name)
    if raw_cookie:
        try:
            data = _get_serializer().loads(
                raw_cookie, max_age=settings.session_max_age_seconds
            )
            _ACTIVE_SESSIONS.pop(data.get("sid", ""), None)
        except (BadSignature, SignatureExpired):
            pass

    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def verify_session_cookie(request: Request) -> dict[str, Any]:
    """职责:从请求Cookie中解析并校验当前登录会话"""
    settings = get_settings()
    raw_cookie = request.cookies.get(settings.session_cookie_name)
    if not raw_cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未检测到有效登录Cookie，请先登录",
        )

    # 校验签名与有效期
    try:
        payload: dict[str, Any] = _get_serializer().loads(
            raw_cookie, max_age=settings.session_max_age_seconds
        )
    except SignatureExpired as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录会话已过期，请重新登录",
        ) from exc
    except BadSignature as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="非法会话Cookie签名",
        ) from exc

    return payload
