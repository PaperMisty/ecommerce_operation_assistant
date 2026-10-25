from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """职责:管理系统全局环境变量与配置参数"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 基础服务配置
    app_name: str = "电商运营助手 (Ecommerce Operation Assistant)"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False
    backend_host: str = Field(default="0.0.0.0", alias="BACKEND_HOST")
    backend_port: int = Field(default=8001, alias="BACKEND_PORT")

    # 数据库异步连接池配置 (复用本地 WSL2 Docker PostgreSQL 容器)
    database_url: str = Field(
        default="postgresql+asyncpg://eoa_user:eoa_pass@127.0.0.1:5432/ecommerce_operation_assistant",
        alias="DATABASE_URL",
    )
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Session Cookie 安全配置 (HttpOnly + Lax + Secure)
    session_cookie_name: str = "eoa_session_id"
    session_secret_key: str = "eoa-super-secret-session-key-2026"
    session_max_age_seconds: int = 86400 * 7
    cookie_secure: bool = Field(default=False, alias="COOKIE_SECURE")
    cookie_samesite: str = "lax"

    # AI 编排双模开关: "mock" (默认先跑通Mock) 或 "real" (调用.env真实API)
    ai_mode: str = Field(default="mock", alias="AI_MODE")

    # .env 中的大模型 API 配置
    qwen_api_key: str = Field(default="", alias="qwen_api_key")
    qwen_base_url: str = Field(
        default="https://llm-0pkln5lgrdv476r1.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        alias="qwen_base_url",
    )
    llm_model: str = Field(default="deepseek-v4.1-flash", alias="model")

    # .env 中的 Langfuse 观测层配置
    langfuse_secret_key: str = Field(default="", alias="LANGFUSE_SECRET_KEY")
    langfuse_public_key: str = Field(default="", alias="LANGFUSE_PUBLIC_KEY")
    langfuse_base_url: str = Field(
        default="https://jp.cloud.langfuse.com", alias="LANGFUSE_BASE_URL"
    )


@lru_cache
def get_settings() -> Settings:
    """职责:获取全局单例配置对象"""
    return Settings()
