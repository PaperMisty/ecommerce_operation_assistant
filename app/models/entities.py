from datetime import datetime, timezone
from typing import Any
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    """职责:生成带UTC时区的当前时间"""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """职责:SQLAlchemy 2.0 声明式ORM模型基类"""
    pass


# ==================== 1. 用户与店铺域 (3张表) ====================

class User(Base):
    """职责:系统用户与角色权限表 (users)"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="operator", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Store(Base):
    """职责:电商店铺基础信息表 (stores)"""
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_name: Mapped[str] = mapped_column(String(128), nullable=False)
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    external_store_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    owner_name: Mapped[str] = mapped_column(String(64), nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class PlatformAccount(Base):
    """职责:平台账号授权安全元数据占位表，严禁保存明文凭证 (platform_accounts)"""
    __tablename__ = "platform_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    account_name: Mapped[str] = mapped_column(String(128), nullable=False)
    auth_status: Mapped[str] = mapped_column(String(32), default="unauthorized", nullable=False)
    auth_meta_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


# ==================== 2. 商品、SKU与库存域 (5张表) ====================

class Product(Base):
    """职责:核心商品聚合根表 (products)"""
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=False)
    price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    target_audience: Mapped[str] = mapped_column(Text, default="")
    selling_points: Mapped[str] = mapped_column(Text, default="")
    product_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    images_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class PlatformProductMapping(Base):
    """职责:多平台商品与SKU映射关系表 (platform_product_mappings)"""
    __tablename__ = "platform_product_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    platform_product_id: Mapped[str] = mapped_column(String(128), nullable=False)
    platform_sku_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mapping_status: Mapped[str] = mapped_column(String(32), default="mapped")
    raw_payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ProductSKU(Base):
    """职责:商品SKU规格与价格成本表 (product_skus)"""
    __tablename__ = "product_skus"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    sku_code: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    sku_name: Mapped[str] = mapped_column(String(255), nullable=False)
    spec_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    platform_sku_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class InventoryItem(Base):
    """职责:SKU实时库存与预警阈值表 (inventory_items)"""
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("product_skus.id", ondelete="CASCADE"), unique=True, index=True)
    stock_qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warning_threshold: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    location_text: Mapped[str] = mapped_column(String(128), default="默认仓-A区")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class InventoryMovement(Base):
    """职责:SKU出入库与盘点流水账本表 (inventory_movements)"""
    __tablename__ = "inventory_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("product_skus.id", ondelete="CASCADE"), index=True)
    movement_type: Mapped[str] = mapped_column(String(32), nullable=False)  # inbound, outbound, adjust
    change_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    before_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    after_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    reason_text: Mapped[str] = mapped_column(String(255), default="")
    reference_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


# ==================== 3. 竞品与链接解析域 (4张表) ====================

class Competitor(Base):
    """职责:商品关联竞品档案表 (competitors)"""
    __tablename__ = "competitors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    url: Mapped[str] = mapped_column(String(512), default="")
    price: Mapped[float] = mapped_column(Float, default=0.0)
    sales_hint: Mapped[str] = mapped_column(String(128), default="")
    title: Mapped[str] = mapped_column(String(255), default="")
    main_image: Mapped[str | None] = mapped_column(String(512), nullable=True)
    selling_points: Mapped[str] = mapped_column(Text, default="")
    review_keywords: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class CompetitorMonitor(Base):
    """职责:竞品定时监控配置表 (competitor_monitors)"""
    __tablename__ = "competitor_monitors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    competitor_id: Mapped[int] = mapped_column(ForeignKey("competitors.id", ondelete="CASCADE"), index=True)
    monitor_status: Mapped[str] = mapped_column(String(32), default="active")
    interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CompetitorMonitorSnapshot(Base):
    """职责:竞品监控历史价格与卖点快照表 (competitor_monitor_snapshots)"""
    __tablename__ = "competitor_monitor_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    monitor_id: Mapped[int] = mapped_column(ForeignKey("competitor_monitors.id", ondelete="CASCADE"), index=True)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    sales_hint: Mapped[str] = mapped_column(String(128), default="")
    selling_points: Mapped[str] = mapped_column(Text, default="")
    raw_payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PublicLinkParseTask(Base):
    """职责:合规公开链接有限信息提取任务表 (public_link_parse_tasks)"""
    __tablename__ = "public_link_parse_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    source_url: Mapped[str] = mapped_column(String(512), nullable=False)
    task_status: Mapped[str] = mapped_column(String(32), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


# ==================== 4. AI诊断、内容方案与异步素材域 (5张表) ====================

class ProductDiagnosis(Base):
    """职责:商品7维结构化诊断结果表 (product_diagnoses)"""
    __tablename__ = "product_diagnoses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str] = mapped_column(String(32), default="ai_generated")
    positioning: Mapped[str] = mapped_column(Text, nullable=False)
    price_band: Mapped[str] = mapped_column(Text, nullable=False)
    audience_insights: Mapped[str] = mapped_column(Text, nullable=False)
    pain_points: Mapped[str] = mapped_column(Text, nullable=False)
    selling_point_analysis: Mapped[str] = mapped_column(Text, nullable=False)
    risks: Mapped[str] = mapped_column(Text, nullable=False)
    recommendations: Mapped[str] = mapped_column(Text, nullable=False)
    raw_output: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class CreativePlan(Base):
    """职责:主图方案与短视频脚本表 (creative_plans)"""
    __tablename__ = "creative_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    plan_type: Mapped[str] = mapped_column(String(32), nullable=False)  # main_image, video_script
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    rationale_text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="draft")  # draft, selected, archived
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class GenerationJob(Base):
    """职责:图片与视频异步生成任务队列及锁状态表 (generation_jobs)"""
    __tablename__ = "generation_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    creative_plan_id: Mapped[int] = mapped_column(ForeignKey("creative_plans.id", ondelete="CASCADE"), index=True)
    job_kind: Mapped[str] = mapped_column(String(32), nullable=False)  # image, video
    job_status: Mapped[str] = mapped_column(String(32), default="pending")  # pending, running, succeeded, failed, cancelled, timeout
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GenerationJobEvent(Base):
    """职责:异步生成任务事件时间线日志表 (generation_job_events)"""
    __tablename__ = "generation_job_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("generation_jobs.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)  # queued, running, succeeded, failed, retry, cancelled, timeout
    event_message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class GeneratedAsset(Base):
    """职责:已生成图片与视频素材库表 (generated_assets)"""
    __tablename__ = "generated_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    creative_plan_id: Mapped[int] = mapped_column(ForeignKey("creative_plans.id", ondelete="CASCADE"), index=True)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)  # image, video
    asset_url: Mapped[str] = mapped_column(String(512), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), default="mock-media-v1")
    width: Mapped[int] = mapped_column(Integer, default=1080)
    height: Mapped[int] = mapped_column(Integer, default=1080)
    duration_sec: Mapped[int] = mapped_column(Integer, default=0)
    review_status: Mapped[str] = mapped_column(String(32), default="pending")  # pending, approved, rejected
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    usage_scene: Mapped[str] = mapped_column(String(128), default="首图/信息流测试")
    score: Mapped[int] = mapped_column(Integer, default=5)
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    remark: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


# ==================== 5. 推广短链、投放建议与经营复盘域 (6张表) ====================

class PromotionLink(Base):
    """职责:商品推广短链与UTM参数表 (promotion_links)"""
    __tablename__ = "promotion_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    link_name: Mapped[str] = mapped_column(String(128), nullable=False)
    target_url: Mapped[str] = mapped_column(String(512), nullable=False)
    tracking_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    utm_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="active")
    click_count: Mapped[int] = mapped_column(Integer, default=0)
    scene_text: Mapped[str] = mapped_column(String(128), default="短视频挂载")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PromotionLinkClick(Base):
    """职责:推广短链点击追踪流水表 (promotion_link_clicks)"""
    __tablename__ = "promotion_link_clicks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    promotion_link_id: Mapped[int] = mapped_column(ForeignKey("promotion_links.id", ondelete="CASCADE"), index=True)
    clicked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    client_ip: Mapped[str] = mapped_column(String(64), default="127.0.0.1")
    user_agent: Mapped[str] = mapped_column(String(255), default="")


class AdRecommendation(Base):
    """职责:AI投放策略建议与人工确认(HITL)记录表 (ad_recommendations)"""
    __tablename__ = "ad_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    objective_text: Mapped[str] = mapped_column(Text, nullable=False)
    audience_segments_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    budget_plan_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    creative_tests_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    bid_strategy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    risk_controls_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    next_steps_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    confirm_status: Mapped[str] = mapped_column(String(32), default="pending")  # pending, confirmed, rejected
    confirmed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirm_remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AdExperiment(Base):
    """职责:投放A/B测试实验计划表 (ad_experiments)"""
    __tablename__ = "ad_experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    related_asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    related_link_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    experiment_name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_text: Mapped[str] = mapped_column(Text, nullable=False)
    audience_text: Mapped[str] = mapped_column(Text, nullable=False)
    budget_amount: Mapped[float] = mapped_column(Float, default=500.0)
    success_metric_text: Mapped[str] = mapped_column(String(255), default="CTR >= 3.5%, ROI >= 2.2")
    hypothesis_text: Mapped[str] = mapped_column(Text, default="")
    experiment_status: Mapped[str] = mapped_column(String(32), default="draft")  # draft, confirmed, running, finished, cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class PerformanceRecord(Base):
    """职责:周期经营数据回填表 (performance_records)"""
    __tablename__ = "performance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    creative_plan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generated_asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    promotion_link_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    experiment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    period_start: Mapped[str] = mapped_column(String(32), nullable=False)
    period_end: Mapped[str] = mapped_column(String(32), nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    ctr: Mapped[float] = mapped_column(Float, default=0.0)
    conversions: Mapped[int] = mapped_column(Integer, default=0)
    conversion_rate: Mapped[float] = mapped_column(Float, default=0.0)
    spend: Mapped[float] = mapped_column(Float, default=0.0)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    roi: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ReviewReport(Base):
    """职责:AI周期经营复盘报告表 (review_reports)"""
    __tablename__ = "review_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    period_start: Mapped[str] = mapped_column(String(32), nullable=False)
    period_end: Mapped[str] = mapped_column(String(32), nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    insights_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    next_actions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
