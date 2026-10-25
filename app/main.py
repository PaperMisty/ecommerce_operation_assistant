from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes import router as v1_router
from app.core.config import get_settings
from app.infrastructure.database import AsyncSessionLocal, async_engine, close_db_pool
from app.infrastructure.http_client import close_http_pool, init_http_pool
from app.models.entities import Base
from app.services.demo_and_jobs import ensure_default_users


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """职责:管理FastAPI应用生命周期，复用数据库连接池与HTTP连接池并自动建表"""
    # 1. 初始化全局异步HTTP连接池
    await init_http_pool()

    # 2. 自动在PostgreSQL容器中创建23张核心业务表并初始化默认角色账号
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await ensure_default_users(session)

    yield

    # 3. 优雅释放全局连接池资源
    await close_http_pool()
    await close_db_pool()


def create_app() -> FastAPI:
    """职责:构造并配置FastAPI主应用实例"""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    # 配置CORS允许携带HttpOnly Session Cookie (allow_credentials=True)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(v1_router, prefix=settings.api_v1_prefix)

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """职责:提供服务存活与当前AI模式健康检查"""
        return {"status": "ok", "ai_mode": settings.ai_mode}

    return app


app = create_app()
