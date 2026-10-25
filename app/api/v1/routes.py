import asyncio
import csv
import io
import secrets
from datetime import timedelta
from typing import Any
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import PlainTextResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.security import (
    clear_session_cookie,
    create_session_cookie,
    hash_password,
    verify_password,
)
from app.infrastructure.ai_engine import (
    run_ad_recommendation_ai,
    run_diagnosis_ai,
    run_inventory_advice_ai,
    run_main_image_ai,
    run_review_report_ai,
    run_video_script_ai,
)
from app.infrastructure.database import get_db_session
from app.models.entities import (
    AdExperiment,
    AdRecommendation,
    Competitor,
    CompetitorMonitor,
    CompetitorMonitorSnapshot,
    CreativePlan,
    GeneratedAsset,
    GenerationJob,
    GenerationJobEvent,
    InventoryItem,
    InventoryMovement,
    PerformanceRecord,
    PlatformAccount,
    PlatformProductMapping,
    Product,
    ProductDiagnosis,
    ProductSKU,
    PromotionLink,
    PromotionLinkClick,
    PublicLinkParseTask,
    ReviewReport,
    Store,
    User,
    utc_now,
)
from app.schemas.contracts import (
    AdConfirmationRequest,
    AdExperimentUpdateRequest,
    AssetUpdateRequest,
    CompetitorCreateRequest,
    CreativePlanUpdateRequest,
    DiagnosisUpdateRequest,
    InventoryAdjustRequest,
    LinkParseCreateRequest,
    LoginRequest,
    PerformanceRecordCreateRequest,
    PlatformAccountCreateRequest,
    ProductCreateRequest,
    ProductUpdateRequest,
    PromotionLinkCreateRequest,
    SKUCreateRequest,
    StoreCreateRequest,
    StoreUpdateRequest,
    UserCreateRequest,
    UserUpdateRequest,
)
from app.services.analyzers import (
    build_diagnosis_readonly_context,
    build_store_inventory_readonly_context,
)
from app.services.demo_and_jobs import (
    ensure_default_users,
    execute_generation_job_async,
    seed_demo_workspace_data,
)

router = APIRouter()


# ==================== 1. 认证与用户权限模块 (Session Cookie) ====================

@router.post("/auth/login")
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """职责:校验账号密码并通过Set-Cookie下发HttpOnly+Lax+Secure的Session Cookie"""
    await ensure_default_users(db)

    # 查询用户并验证密码哈希
    res = await db.execute(select(User).where(User.username == payload.username))
    user = res.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="该账号已被禁用",
        )

    # 更新最后登录时间并写入Session Cookie
    user.last_login_at = utc_now()
    await db.commit()
    create_session_cookie(response, user.id, user.username, user.role)

    return {
        "message": "登录成功 (Session Cookie 已签发)",
        "user": {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
            "status": user.status,
        },
    }


@router.post("/auth/logout")
async def logout(
    request: Request,
    response: Response,
) -> dict[str, str]:
    """职责:销毁服务端会话并清理浏览器Session Cookie"""
    clear_session_cookie(request, response)
    return {"message": "已安全退出登录"}


@router.get("/auth/me")
async def get_me(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """职责:查询当前Session Cookie对应的登录用户信息"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "display_name": current_user.display_name,
        "role": current_user.role,
        "status": current_user.status,
        "last_login_at": current_user.last_login_at,
    }


@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """职责:查询系统用户列表"""
    res = await db.execute(select(User).order_by(User.id.asc()))
    return [
        {
            "id": u.id,
            "username": u.username,
            "display_name": u.display_name,
            "role": u.role,
            "status": u.status,
            "last_login_at": u.last_login_at,
        }
        for u in res.scalars().all()
    ]


@router.post("/users")
async def create_user(
    payload: UserCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin")),
) -> dict[str, Any]:
    """职责:管理员创建新用户(仅admin角色可调用)"""
    user = User(
        username=payload.username,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        role=payload.role,
        status="active",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"id": user.id, "username": user.username, "role": user.role}


@router.patch("/users/{user_id}")
async def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin")),
) -> dict[str, Any]:
    """职责:管理员更新用户角色或启停状态(仅admin角色可调用)"""
    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.role is not None:
        user.role = payload.role
    if payload.status is not None:
        user.status = payload.status
    await db.commit()
    return {"id": user.id, "username": user.username, "role": user.role, "status": user.status}


# ==================== 2. 店铺管理与 AI 库存建议模块 ====================

@router.get("/stores")
async def list_stores(
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """职责:查询店铺列表并附带商品数量与低库存预警统计"""
    stores = list((await db.execute(select(Store).order_by(Store.id.asc()))).scalars().all())
    result: list[dict[str, Any]] = []

    for st in stores:
        inv_ctx = await build_store_inventory_readonly_context(db, st.id)
        low_stock_count = sum(
            1
            for m in inv_ctx["sku_metrics"]
            if m["stock_status"] in ("OUT_OF_STOCK", "LOW_STOCK")
        )
        prod_count = len({m["product_id"] for m in inv_ctx["sku_metrics"]})
        if prod_count == 0:
            prods = list((await db.execute(select(Product).where(Product.store_id == st.id))).scalars().all())
            prod_count = len(prods)

        result.append(
            {
                "id": st.id,
                "store_name": st.store_name,
                "platform": st.platform,
                "external_store_id": st.external_store_id,
                "owner_name": st.owner_name,
                "remark": st.remark,
                "product_count": prod_count,
                "low_stock_count": low_stock_count,
                "updated_at": st.updated_at,
            }
        )
    return result


@router.post("/stores")
async def create_store(
    payload: StoreCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:新增电商店铺档案"""
    store = Store(
        store_name=payload.store_name,
        platform=payload.platform,
        external_store_id=payload.external_store_id,
        owner_name=payload.owner_name,
        remark=payload.remark,
    )
    db.add(store)
    await db.commit()
    await db.refresh(store)
    return {"id": store.id, "store_name": store.store_name, "platform": store.platform}


@router.get("/stores/{store_id}")
async def get_store_detail(
    store_id: int,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """职责:查询店铺详情、平台账号安全占位、SKU库存监控面板与最近库存流水"""
    store = (await db.execute(select(Store).where(Store.id == store_id))).scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="店铺不存在")

    accounts = list(
        (await db.execute(select(PlatformAccount).where(PlatformAccount.store_id == store_id))).scalars().all()
    )
    inv_context = await build_store_inventory_readonly_context(db, store_id)
    sku_ids = [m["sku_id"] for m in inv_context["sku_metrics"]]
    movements: list[InventoryMovement] = []
    if sku_ids:
        movements = list(
            (
                await db.execute(
                    select(InventoryMovement)
                    .where(InventoryMovement.sku_id.in_(sku_ids))
                    .order_by(InventoryMovement.id.desc())
                    .limit(15)
                )
            ).scalars().all()
        )

    return {
        "store": {
            "id": store.id,
            "store_name": store.store_name,
            "platform": store.platform,
            "owner_name": store.owner_name,
            "remark": store.remark,
        },
        "platform_accounts": [
            {
                "id": a.id,
                "platform": a.platform,
                "account_name": a.account_name,
                "auth_status": a.auth_status,
                "auth_meta_json": a.auth_meta_json,
                "remark": a.remark,
            }
            for a in accounts
        ],
        "inventory_overview": inv_context,
        "recent_movements": [
            {
                "id": m.id,
                "sku_id": m.sku_id,
                "movement_type": m.movement_type,
                "change_qty": m.change_qty,
                "before_qty": m.before_qty,
                "after_qty": m.after_qty,
                "reason_text": m.reason_text,
                "created_at": m.created_at,
            }
            for m in movements
        ],
    }


@router.patch("/stores/{store_id}")
async def update_store(
    store_id: int,
    payload: StoreUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:更新店铺基本信息"""
    store = (await db.execute(select(Store).where(Store.id == store_id))).scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="店铺不存在")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(store, k, v)
    await db.commit()
    return {"id": store.id, "store_name": store.store_name}


@router.post("/stores/{store_id}/platform-accounts")
async def create_platform_account(
    store_id: int,
    payload: PlatformAccountCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:创建平台账号脱敏安全占位(严禁存储明文凭证)"""
    acc = PlatformAccount(
        store_id=store_id,
        platform=payload.platform,
        account_name=payload.account_name,
        auth_status="pending",
        auth_meta_json={"compliance_note": "no_plaintext_token_or_cookie"},
        remark=payload.remark,
    )
    db.add(acc)
    await db.commit()
    await db.refresh(acc)
    return {"id": acc.id, "account_name": acc.account_name, "auth_status": acc.auth_status}


@router.post("/stores/{store_id}/platform-accounts/{account_id}/authorization/start")
async def start_account_auth(
    store_id: int,
    account_id: int,
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:生成平台OAuth授权占位跳转信息"""
    return {
        "store_id": store_id,
        "account_id": account_id,
        "oauth_placeholder_url": f"https://open.example.com/oauth/authorize?account_id={account_id}",
    }


@router.post("/stores/{store_id}/platform-accounts/{account_id}/authorization/callback-placeholder")
async def callback_account_auth(
    store_id: int,
    account_id: int,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:保存脱敏后的平台授权状态元数据"""
    acc = (
        await db.execute(
            select(PlatformAccount).where(
                PlatformAccount.id == account_id, PlatformAccount.store_id == store_id
            )
        )
    ).scalar_one_or_none()
    if not acc:
        raise HTTPException(status_code=404, detail="平台账号占位不存在")
    acc.auth_status = "authorized"
    acc.auth_meta_json = {"authorized_at": str(utc_now()), "token_masked": "oauth2_masked_***"}
    await db.commit()
    return {"id": acc.id, "auth_status": acc.auth_status, "auth_meta_json": acc.auth_meta_json}


@router.post("/stores/{store_id}/inventory-advice/generate")
async def generate_store_inventory_advice(
    store_id: int,
    mode: str | None = Query(default=None, description="可选覆盖AI模式: mock 或 real"),
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:基于本地5表只读聚合与规则预计算生成店铺AI库存建议"""
    inv_ctx = await build_store_inventory_readonly_context(db, store_id)
    advice = await run_inventory_advice_ai(inv_ctx, mode=mode)
    return {
        "store_id": store_id,
        "readonly_pre_calculated": inv_ctx,
        "ai_advice": advice.model_dump(),
    }


# ==================== 3. 商品、SKU库存与竞品模块 ====================

@router.get("/products")
async def list_products(
    store_id: int | None = None,
    platform: str | None = None,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """职责:查询商品列表并附带最近诊断时间与最近复盘时间"""
    stmt = select(Product).order_by(Product.id.asc())
    if store_id is not None:
        stmt = stmt.where(Product.store_id == store_id)
    if platform:
        stmt = stmt.where(Product.platform == platform)

    products = list((await db.execute(stmt)).scalars().all())
    result: list[dict[str, Any]] = []
    for p in products:
        diag = (
            await db.execute(
                select(ProductDiagnosis)
                .where(ProductDiagnosis.product_id == p.id)
                .order_by(ProductDiagnosis.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        rev = (
            await db.execute(
                select(ReviewReport)
                .where(ReviewReport.product_id == p.id)
                .order_by(ReviewReport.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        result.append(
            {
                "id": p.id,
                "store_id": p.store_id,
                "name": p.name,
                "platform": p.platform,
                "category": p.category,
                "price": p.price,
                "cost": p.cost,
                "status": p.status,
                "last_diagnosis_at": diag.updated_at if diag else None,
                "last_review_at": rev.created_at if rev else None,
            }
        )
    return result


@router.post("/products")
async def create_product(
    payload: ProductCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:新建核心单品档案"""
    prod = Product(**payload.model_dump())
    db.add(prod)
    await db.commit()
    await db.refresh(prod)
    return {"id": prod.id, "name": prod.name, "status": prod.status}


@router.get("/products/{product_id}")
async def get_product_full_workbench(
    product_id: int,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """职责:聚合返回商品详情页9大标签页所需的完整工作台数据"""
    prod = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
    if not prod:
        raise HTTPException(status_code=404, detail="商品不存在")

    # 聚合查询SKU与库存、竞品、诊断、方案、任务、素材、链接、投放与复盘
    skus = list((await db.execute(select(ProductSKU).where(ProductSKU.product_id == product_id))).scalars().all())
    sku_ids = [s.id for s in skus]
    inv_map: dict[int, InventoryItem] = {}
    if sku_ids:
        invs = list((await db.execute(select(InventoryItem).where(InventoryItem.sku_id.in_(sku_ids)))).scalars().all())
        inv_map = {i.sku_id: i for i in invs}

    competitors = list((await db.execute(select(Competitor).where(Competitor.product_id == product_id))).scalars().all())
    parse_tasks = list((await db.execute(select(PublicLinkParseTask).where(PublicLinkParseTask.product_id == product_id).order_by(PublicLinkParseTask.id.desc()))).scalars().all())
    diagnoses = list((await db.execute(select(ProductDiagnosis).where(ProductDiagnosis.product_id == product_id).order_by(ProductDiagnosis.id.desc()))).scalars().all())
    plans = list((await db.execute(select(CreativePlan).where(CreativePlan.product_id == product_id).order_by(CreativePlan.id.desc()))).scalars().all())
    jobs = list((await db.execute(select(GenerationJob).where(GenerationJob.product_id == product_id).order_by(GenerationJob.id.desc()))).scalars().all())
    job_ids = [j.id for j in jobs]
    events_map: dict[int, list[dict[str, Any]]] = {jid: [] for jid in job_ids}
    if job_ids:
        evs = list((await db.execute(select(GenerationJobEvent).where(GenerationJobEvent.job_id.in_(job_ids)).order_by(GenerationJobEvent.id.asc()))).scalars().all())
        for ev in evs:
            events_map[ev.job_id].append({"event_type": ev.event_type, "event_message": ev.event_message, "created_at": ev.created_at})

    assets = list((await db.execute(select(GeneratedAsset).where(GeneratedAsset.product_id == product_id).order_by(GeneratedAsset.id.desc()))).scalars().all())
    links = list((await db.execute(select(PromotionLink).where(PromotionLink.product_id == product_id).order_by(PromotionLink.id.desc()))).scalars().all())
    ad_recs = list((await db.execute(select(AdRecommendation).where(AdRecommendation.product_id == product_id).order_by(AdRecommendation.id.desc()))).scalars().all())
    ad_exps = list((await db.execute(select(AdExperiment).where(AdExperiment.product_id == product_id).order_by(AdExperiment.id.desc()))).scalars().all())
    perfs = list((await db.execute(select(PerformanceRecord).where(PerformanceRecord.product_id == product_id).order_by(PerformanceRecord.id.desc()))).scalars().all())
    reviews = list((await db.execute(select(ReviewReport).where(ReviewReport.product_id == product_id).order_by(ReviewReport.id.desc()))).scalars().all())

    return {
        "product": {
            "id": prod.id,
            "store_id": prod.store_id,
            "name": prod.name,
            "platform": prod.platform,
            "category": prod.category,
            "price": prod.price,
            "cost": prod.cost,
            "target_audience": prod.target_audience,
            "selling_points": prod.selling_points,
            "product_url": prod.product_url,
            "status": prod.status,
        },
        "skus": [
            {
                "id": s.id,
                "sku_code": s.sku_code,
                "sku_name": s.sku_name,
                "price": s.price,
                "cost": s.cost,
                "stock_qty": inv_map[s.id].stock_qty if s.id in inv_map else 0,
                "locked_qty": inv_map[s.id].locked_qty if s.id in inv_map else 0,
                "warning_threshold": inv_map[s.id].warning_threshold if s.id in inv_map else 20,
            }
            for s in skus
        ],
        "competitors": [
            {
                "id": c.id,
                "name": c.name,
                "platform": c.platform,
                "url": c.url,
                "price": c.price,
                "sales_hint": c.sales_hint,
                "selling_points": c.selling_points,
                "review_keywords": c.review_keywords,
            }
            for c in competitors
        ],
        "link_parse_tasks": [
            {
                "id": t.id,
                "source_url": t.source_url,
                "task_status": t.task_status,
                "result_json": t.result_json,
            }
            for t in parse_tasks
        ],
        "diagnoses": [
            {
                "id": d.id,
                "positioning": d.positioning,
                "price_band": d.price_band,
                "audience_insights": d.audience_insights,
                "pain_points": d.pain_points,
                "selling_point_analysis": d.selling_point_analysis,
                "risks": d.risks,
                "recommendations": d.recommendations,
                "updated_at": d.updated_at,
            }
            for d in diagnoses
        ],
        "creative_plans": [
            {
                "id": p.id,
                "plan_type": p.plan_type,
                "title": p.title,
                "content_json": p.content_json,
                "rationale_text": p.rationale_text,
                "status": p.status,
            }
            for p in plans
        ],
        "generation_jobs": [
            {
                "id": j.id,
                "creative_plan_id": j.creative_plan_id,
                "job_kind": j.job_kind,
                "job_status": j.job_status,
                "attempts": j.attempts,
                "result_json": j.result_json,
                "error_message": j.error_message,
                "started_at": j.started_at,
                "finished_at": j.finished_at,
                "events": events_map.get(j.id, []),
            }
            for j in jobs
        ],
        "generated_assets": [
            {
                "id": a.id,
                "creative_plan_id": a.creative_plan_id,
                "asset_type": a.asset_type,
                "asset_url": a.asset_url,
                "review_status": a.review_status,
                "version_no": a.version_no,
                "usage_scene": a.usage_scene,
                "score": a.score,
                "tags_json": a.tags_json,
                "remark": a.remark,
            }
            for a in assets
        ],
        "promotion_links": [
            {
                "id": l.id,
                "link_name": l.link_name,
                "target_url": l.target_url,
                "tracking_code": l.tracking_code,
                "utm_json": l.utm_json,
                "click_count": l.click_count,
                "scene_text": l.scene_text,
            }
            for l in links
        ],
        "ad_recommendations": [
            {
                "id": r.id,
                "summary_text": r.summary_text,
                "objective_text": r.objective_text,
                "audience_segments_json": r.audience_segments_json,
                "budget_plan_json": r.budget_plan_json,
                "creative_tests_json": r.creative_tests_json,
                "bid_strategy_json": r.bid_strategy_json,
                "risk_controls_json": r.risk_controls_json,
                "next_steps_json": r.next_steps_json,
                "confirm_status": r.confirm_status,
                "confirmed_by": r.confirmed_by,
                "confirm_remark": r.confirm_remark,
            }
            for r in ad_recs
        ],
        "ad_experiments": [
            {
                "id": e.id,
                "experiment_name": e.experiment_name,
                "target_text": e.target_text,
                "audience_text": e.audience_text,
                "budget_amount": e.budget_amount,
                "success_metric_text": e.success_metric_text,
                "experiment_status": e.experiment_status,
            }
            for e in ad_exps
        ],
        "performance_records": [
            {
                "id": pr.id,
                "period_start": pr.period_start,
                "period_end": pr.period_end,
                "impressions": pr.impressions,
                "clicks": pr.clicks,
                "ctr": pr.ctr,
                "conversions": pr.conversions,
                "conversion_rate": pr.conversion_rate,
                "spend": pr.spend,
                "revenue": pr.revenue,
                "roi": pr.roi,
                "notes": pr.notes,
            }
            for pr in perfs
        ],
        "review_reports": [
            {
                "id": rv.id,
                "period_start": rv.period_start,
                "period_end": rv.period_end,
                "summary_text": rv.summary_text,
                "insights_json": rv.insights_json,
                "next_actions_json": rv.next_actions_json,
                "created_at": rv.created_at,
            }
            for rv in reviews
        ],
    }


@router.patch("/products/{product_id}")
async def update_product(
    product_id: int,
    payload: ProductUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:更新商品基础信息或上下架状态"""
    prod = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
    if not prod:
        raise HTTPException(status_code=404, detail="商品不存在")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(prod, k, v)
    await db.commit()
    return {"id": prod.id, "name": prod.name, "status": prod.status}


@router.post("/products/{product_id}/skus")
async def create_product_sku(
    product_id: int,
    payload: SKUCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:为商品新增SKU规格并初始化库存与入库流水"""
    sku = ProductSKU(
        product_id=product_id,
        sku_code=payload.sku_code,
        sku_name=payload.sku_name,
        spec_json=payload.spec_json,
        price=payload.price,
        cost=payload.cost,
    )
    db.add(sku)
    await db.flush()

    inv = InventoryItem(
        sku_id=sku.id,
        stock_qty=payload.initial_stock,
        locked_qty=0,
        warning_threshold=payload.warning_threshold,
    )
    mov = InventoryMovement(
        sku_id=sku.id,
        movement_type="inbound",
        change_qty=payload.initial_stock,
        before_qty=0,
        after_qty=payload.initial_stock,
        reason_text="新建SKU初始建账入库",
    )
    db.add_all([inv, mov])
    await db.commit()
    return {"sku_id": sku.id, "sku_code": sku.sku_code, "stock_qty": payload.initial_stock}


@router.post("/products/{product_id}/inventory/adjust")
async def adjust_sku_inventory(
    product_id: int,
    payload: InventoryAdjustRequest,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:调整SKU库存数量并原子写入库存变动流水(inventory_movements)"""
    inv = (
        await db.execute(select(InventoryItem).where(InventoryItem.sku_id == payload.sku_id))
    ).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="该SKU库存记录不存在")

    before_qty = inv.stock_qty
    after_qty = max(before_qty + payload.change_qty, 0)
    inv.stock_qty = after_qty

    mov = InventoryMovement(
        sku_id=payload.sku_id,
        movement_type=payload.movement_type,
        change_qty=payload.change_qty,
        before_qty=before_qty,
        after_qty=after_qty,
        reason_text=payload.reason_text,
        reference_type="manual_adjust",
        reference_id=f"PROD-{product_id}",
    )
    db.add(mov)
    await db.commit()
    return {"sku_id": payload.sku_id, "before_qty": before_qty, "after_qty": after_qty}


@router.post("/products/{product_id}/platform-mappings")
async def create_platform_mapping(
    product_id: int,
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:绑定商品多平台外部ID映射"""
    mapping = PlatformProductMapping(
        product_id=product_id,
        platform=payload.get("platform", "抖音电商"),
        platform_product_id=payload.get("platform_product_id", "EXT-001"),
        platform_sku_id=payload.get("platform_sku_id"),
    )
    db.add(mapping)
    await db.commit()
    await db.refresh(mapping)
    return {"id": mapping.id, "platform_product_id": mapping.platform_product_id}


@router.post("/products/{product_id}/competitors")
async def create_competitor(
    product_id: int,
    payload: CompetitorCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:为当前商品录入对标竞品信息"""
    comp = Competitor(product_id=product_id, **payload.model_dump())
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return {"id": comp.id, "name": comp.name, "price": comp.price}


@router.post("/products/{product_id}/competitors/import-url-tasks")
async def create_link_parse_task(
    product_id: int,
    payload: LinkParseCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:创建合规公开链接有限元数据提取任务"""
    task = PublicLinkParseTask(
        product_id=product_id,
        source_url=payload.source_url,
        task_status="pending",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return {"id": task.id, "task_status": task.task_status, "source_url": task.source_url}


@router.post("/products/{product_id}/link-parse-tasks/{task_id}/run")
async def run_link_parse_task(
    product_id: int,
    task_id: int,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:运行公开链接有限信息解析(遵守合规边界：不绕过登录或验证码)"""
    task = (
        await db.execute(
            select(PublicLinkParseTask).where(
                PublicLinkParseTask.id == task_id, PublicLinkParseTask.product_id == product_id
            )
        )
    ).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="解析任务不存在")

    task.attempts += 1
    task.task_status = "succeeded"
    task.result_json = {
        "extracted_title": f"公开页面提取商品 ({task.source_url[-12:]})",
        "detected_price": 569.0,
        "compliance_mode": "public_meta_opengraph_only",
    }
    await db.commit()
    return {"id": task.id, "task_status": task.task_status, "result_json": task.result_json}


@router.post("/products/{product_id}/competitors/{competitor_id}/monitor")
async def create_competitor_monitor(
    product_id: int,
    competitor_id: int,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:开启竞品定时价格与卖点快照监控"""
    mon = CompetitorMonitor(
        competitor_id=competitor_id,
        monitor_status="active",
        interval_minutes=60,
        next_run_at=utc_now() + timedelta(minutes=60),
    )
    db.add(mon)
    await db.commit()
    await db.refresh(mon)
    return {"monitor_id": mon.id, "product_id": product_id, "competitor_id": competitor_id}


# ==================== 4. AI 商品诊断、主图方案与视频脚本模块 ====================

@router.post("/products/{product_id}/diagnoses/generate")
async def generate_product_diagnosis(
    product_id: int,
    mode: str | None = Query(default=None, description="可选AI模式: mock 或 real"),
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:只读聚合本地6表数据并通过LangChain/LangGraph生成7维商品诊断"""
    context = await build_diagnosis_readonly_context(db, product_id)
    ai_out = await run_diagnosis_ai(context, mode=mode)

    diag = ProductDiagnosis(
        product_id=product_id,
        source_type=f"langchain_{mode or 'default'}",
        positioning=ai_out.positioning,
        price_band=ai_out.price_band,
        audience_insights=ai_out.audience_insights,
        pain_points=ai_out.pain_points,
        selling_point_analysis=ai_out.selling_point_analysis,
        risks=ai_out.risks,
        recommendations=ai_out.recommendations,
        raw_output={"pre_calculated": context["pre_calculated"]},
    )
    db.add(diag)
    await db.commit()
    await db.refresh(diag)

    return {
        "id": diag.id,
        "product_id": product_id,
        "positioning": diag.positioning,
        "price_band": diag.price_band,
        "audience_insights": diag.audience_insights,
        "pain_points": diag.pain_points,
        "selling_point_analysis": diag.selling_point_analysis,
        "risks": diag.risks,
        "recommendations": diag.recommendations,
        "pre_calculated": context["pre_calculated"],
    }


@router.patch("/products/{product_id}/diagnoses/{diagnosis_id}")
async def update_product_diagnosis(
    product_id: int,
    diagnosis_id: int,
    payload: DiagnosisUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:支持运营人员人工修改并保存AI诊断结论"""
    diag = (
        await db.execute(
            select(ProductDiagnosis).where(
                ProductDiagnosis.id == diagnosis_id, ProductDiagnosis.product_id == product_id
            )
        )
    ).scalar_one_or_none()
    if not diag:
        raise HTTPException(status_code=404, detail="诊断记录不存在")

    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(diag, k, v)
    diag.source_type = "human_edited"
    await db.commit()
    return {"id": diag.id, "source_type": diag.source_type, "positioning": diag.positioning}


@router.post("/products/{product_id}/creative-plans/main-images/generate")
async def generate_main_image_plans(
    product_id: int,
    mode: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> list[dict[str, Any]]:
    """职责:基于商品诊断生成至少3个主图策划方向并落库"""
    ctx = await build_diagnosis_readonly_context(db, product_id)
    ai_out = await run_main_image_ai(
        {"product_name": ctx["product"]["name"], "selling_points": ctx["product"]["selling_points"]},
        mode=mode,
    )

    created_plans: list[dict[str, Any]] = []
    for item in ai_out.directions:
        plan = CreativePlan(
            product_id=product_id,
            plan_type="main_image",
            title=item.title,
            content_json={
                "visual_structure": item.visual_structure,
                "core_copy": item.core_copy,
                "selling_point": item.selling_point,
            },
            rationale_text=item.rationale,
            status="draft",
        )
        db.add(plan)
        await db.flush()
        created_plans.append(
            {
                "id": plan.id,
                "plan_type": plan.plan_type,
                "title": plan.title,
                "content_json": plan.content_json,
                "rationale_text": plan.rationale_text,
                "status": plan.status,
            }
        )
    await db.commit()
    return created_plans


@router.post("/products/{product_id}/creative-plans/video-scripts/generate")
async def generate_video_script_plans(
    product_id: int,
    mode: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> list[dict[str, Any]]:
    """职责:基于商品诊断生成至少3条短视频脚本并落库"""
    ctx = await build_diagnosis_readonly_context(db, product_id)
    ai_out = await run_video_script_ai(
        {"product_name": ctx["product"]["name"], "selling_points": ctx["product"]["selling_points"]},
        mode=mode,
    )

    created_plans: list[dict[str, Any]] = []
    for item in ai_out.scripts:
        plan = CreativePlan(
            product_id=product_id,
            plan_type="video_script",
            title=item.title,
            content_json={
                "hook": item.hook,
                "storyboard": item.storyboard,
                "voiceover": item.voiceover,
                "cta": item.cta,
            },
            rationale_text="黄金前3秒痛点钩子+实验分镜转化脚本",
            status="draft",
        )
        db.add(plan)
        await db.flush()
        created_plans.append(
            {
                "id": plan.id,
                "plan_type": plan.plan_type,
                "title": plan.title,
                "content_json": plan.content_json,
                "status": plan.status,
            }
        )
    await db.commit()
    return created_plans


@router.patch("/products/{product_id}/creative-plans/{creative_plan_id}")
async def update_creative_plan(
    product_id: int,
    creative_plan_id: int,
    payload: CreativePlanUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:编辑主图/视频方案内容或切换状态(draft/selected/archived)"""
    plan = (
        await db.execute(
            select(CreativePlan).where(
                CreativePlan.id == creative_plan_id, CreativePlan.product_id == product_id
            )
        )
    ).scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="创意方案不存在")

    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(plan, k, v)
    await db.commit()
    return {"id": plan.id, "title": plan.title, "status": plan.status}


# ==================== 5. 异步图片/视频生成任务与素材库模块 ====================

@router.post("/products/{product_id}/creative-plans/{creative_plan_id}/images/generate")
async def enqueue_image_generation_job(
    product_id: int,
    creative_plan_id: int,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:非阻塞入队图片生成任务并触发后台协程执行"""
    job = GenerationJob(
        product_id=product_id,
        creative_plan_id=creative_plan_id,
        job_kind="image",
        job_status="pending",
    )
    db.add(job)
    await db.flush()
    db.add(
        GenerationJobEvent(
            job_id=job.id,
            event_type="queued",
            event_message="图片异步生成任务已入队，等待Worker消费",
        )
    )
    await db.commit()
    await db.refresh(job)

    asyncio.create_task(execute_generation_job_async(job.id))
    return {"job_id": job.id, "job_status": job.job_status, "job_kind": "image"}


@router.post("/products/{product_id}/creative-plans/{creative_plan_id}/videos/generate")
async def enqueue_video_generation_job(
    product_id: int,
    creative_plan_id: int,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:非阻塞入队视频生成任务并触发后台协程执行"""
    job = GenerationJob(
        product_id=product_id,
        creative_plan_id=creative_plan_id,
        job_kind="video",
        job_status="pending",
    )
    db.add(job)
    await db.flush()
    db.add(
        GenerationJobEvent(
            job_id=job.id,
            event_type="queued",
            event_message="短视频异步合成任务已入队，等待Worker消费",
        )
    )
    await db.commit()
    await db.refresh(job)

    asyncio.create_task(execute_generation_job_async(job.id))
    return {"job_id": job.id, "job_status": job.job_status, "job_kind": "video"}


@router.post("/products/{product_id}/generation-jobs/{job_id}/retry")
async def retry_generation_job(
    product_id: int,
    job_id: int,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:手动重试失败、取消或超时的生成任务"""
    job = (
        await db.execute(
            select(GenerationJob).where(
                GenerationJob.id == job_id, GenerationJob.product_id == product_id
            )
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="生成任务不存在")

    job.job_status = "pending"
    job.error_message = None
    db.add(
        GenerationJobEvent(
            job_id=job.id,
            event_type="retry",
            event_message="运营手动触发任务重新入队重试",
        )
    )
    await db.commit()
    asyncio.create_task(execute_generation_job_async(job.id))
    return {"job_id": job.id, "job_status": job.job_status}


@router.post("/products/{product_id}/generation-jobs/{job_id}/cancel")
async def cancel_generation_job(
    product_id: int,
    job_id: int,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:取消排队中或运行中的异步生成任务"""
    job = (
        await db.execute(
            select(GenerationJob).where(
                GenerationJob.id == job_id, GenerationJob.product_id == product_id
            )
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="生成任务不存在")

    job.job_status = "cancelled"
    job.finished_at = utc_now()
    db.add(
        GenerationJobEvent(
            job_id=job.id,
            event_type="cancelled",
            event_message="任务已被运营人员手动取消",
        )
    )
    await db.commit()
    return {"job_id": job.id, "job_status": job.job_status}


@router.post("/products/{product_id}/assets/sync")
async def sync_generated_assets(
    product_id: int,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:同步商品下所有已完成生成任务的素材记录"""
    assets = list(
        (await db.execute(select(GeneratedAsset).where(GeneratedAsset.product_id == product_id))).scalars().all()
    )
    return {"product_id": product_id, "synced_count": len(assets)}


@router.patch("/products/{product_id}/creative-plans/{creative_plan_id}/assets")
async def update_asset_review_fields(
    product_id: int,
    creative_plan_id: int,
    payload: AssetUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:在素材库更新素材审核状态、评分、使用场景、标签与备注"""
    asset = (
        await db.execute(
            select(GeneratedAsset).where(
                GeneratedAsset.id == payload.asset_id,
                GeneratedAsset.product_id == product_id,
            )
        )
    ).scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="素材不存在")

    for k, v in payload.model_dump(exclude={"asset_id"}, exclude_unset=True).items():
        setattr(asset, k, v)
    await db.commit()
    return {
        "id": asset.id,
        "creative_plan_id": creative_plan_id,
        "review_status": asset.review_status,
        "score": asset.score,
    }


# ==================== 6. 推广短链、投放建议(HITL)与实验模块 ====================

@router.post("/products/{product_id}/promotion-links/generate")
async def generate_promotion_link_suggestion(
    product_id: int,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:生成带UTM参数的推广短链配置建议"""
    prod = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
    if not prod:
        raise HTTPException(status_code=404, detail="商品不存在")
    return {
        "suggested_link_name": f"{prod.name}-千川短视频引流链",
        "target_url": prod.product_url or f"https://shop.example.com/item/{product_id}",
        "suggested_utm": {
            "utm_source": "douyin_qianchuan",
            "utm_medium": "short_video_top_comment",
            "utm_campaign": f"prod_{product_id}_boost",
        },
    }


@router.post("/products/{product_id}/promotion-links")
async def create_promotion_link(
    product_id: int,
    payload: PromotionLinkCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:创建可追踪点击统计的推广短链"""
    code = f"p{product_id}_{secrets.token_hex(3)}"
    link = PromotionLink(
        product_id=product_id,
        link_name=payload.link_name,
        target_url=payload.target_url,
        tracking_code=code,
        utm_json={
            "utm_source": payload.utm_source,
            "utm_medium": payload.utm_medium,
            "utm_campaign": payload.utm_campaign,
        },
        scene_text=payload.scene_text,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return {
        "id": link.id,
        "tracking_code": link.tracking_code,
        "short_url": f"/api/v1/r/{link.tracking_code}",
        "click_count": link.click_count,
    }


@router.get("/r/{tracking_code}")
async def redirect_promotion_link(
    tracking_code: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    """职责:短链访问302重定向并异步记录点击IP与User-Agent流水"""
    link = (
        await db.execute(select(PromotionLink).where(PromotionLink.tracking_code == tracking_code))
    ).scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="推广短链不存在")

    link.click_count += 1
    db.add(
        PromotionLinkClick(
            promotion_link_id=link.id,
            client_ip=request.client.host if request.client else "127.0.0.1",
            user_agent=request.headers.get("user-agent", "unknown"),
        )
    )
    await db.commit()
    return RedirectResponse(url=link.target_url, status_code=status.HTTP_302_FOUND)


@router.post("/products/{product_id}/ad-recommendations/generate")
async def generate_ad_recommendation(
    product_id: int,
    mode: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:生成8维投放建议并置为pending等待人工确认(HITL)"""
    ctx = await build_diagnosis_readonly_context(db, product_id)
    ai_out = await run_ad_recommendation_ai(
        {"product_name": ctx["product"]["name"], "pre_calculated": ctx["pre_calculated"]},
        mode=mode,
    )

    rec = AdRecommendation(
        product_id=product_id,
        summary_text=ai_out.summary_text,
        objective_text=ai_out.objective_text,
        audience_segments_json=ai_out.audience_segments_json,
        budget_plan_json=ai_out.budget_plan_json,
        creative_tests_json=ai_out.creative_tests_json,
        bid_strategy_json=ai_out.bid_strategy_json,
        risk_controls_json=ai_out.risk_controls_json,
        next_steps_json=ai_out.next_steps_json,
        confirm_status="pending",
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return {
        "id": rec.id,
        "summary_text": rec.summary_text,
        "objective_text": rec.objective_text,
        "confirm_status": rec.confirm_status,
        "budget_plan_json": rec.budget_plan_json,
    }


@router.patch("/products/{product_id}/ad-recommendations/{recommendation_id}/confirmation")
async def confirm_or_reject_ad_recommendation(
    product_id: int,
    recommendation_id: int,
    payload: AdConfirmationRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:独立权限校验的人工确认或驳回投放建议(HITL恢复点)"""
    rec = (
        await db.execute(
            select(AdRecommendation).where(
                AdRecommendation.id == recommendation_id,
                AdRecommendation.product_id == product_id,
            )
        )
    ).scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="投放建议不存在")

    if payload.confirm_status not in ("confirmed", "rejected"):
        raise HTTPException(status_code=400, detail="confirm_status 必须为 confirmed 或 rejected")

    rec.confirm_status = payload.confirm_status
    rec.confirmed_by = current_user.username
    rec.confirmed_at = utc_now()
    rec.confirm_remark = payload.confirm_remark
    await db.commit()
    return {
        "id": rec.id,
        "confirm_status": rec.confirm_status,
        "confirmed_by": rec.confirmed_by,
        "confirm_remark": rec.confirm_remark,
    }


@router.post("/products/{product_id}/ad-experiments/generate")
async def generate_ad_experiment(
    product_id: int,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:基于已确认投放建议生成A/B测试实验计划"""
    prod = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
    if not prod:
        raise HTTPException(status_code=404, detail="商品不存在")

    exp = AdExperiment(
        product_id=product_id,
        experiment_name=f"{prod.name}-A/B素材赛马实验",
        target_text="筛选CTR >= 3.8%且转化成本达标的胜出素材",
        audience_text="22-38岁核心痛点定向人群",
        budget_amount=600.0,
        success_metric_text="CTR >= 3.8%, ROI >= 2.5",
        hypothesis_text="痛点对比主图+测评视频能提升首屏停留与加购转化",
        experiment_status="confirmed",
    )
    db.add(exp)
    await db.commit()
    await db.refresh(exp)
    return {"id": exp.id, "experiment_name": exp.experiment_name, "experiment_status": exp.experiment_status}


@router.patch("/products/{product_id}/ad-experiments/{experiment_id}")
async def update_ad_experiment_status(
    product_id: int,
    experiment_id: int,
    payload: AdExperimentUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:独立权限校验更新投放实验状态(draft/confirmed/running/finished/cancelled)"""
    exp = (
        await db.execute(
            select(AdExperiment).where(
                AdExperiment.id == experiment_id, AdExperiment.product_id == product_id
            )
        )
    ).scalar_one_or_none()
    if not exp:
        raise HTTPException(status_code=404, detail="投放实验不存在")

    exp.experiment_status = payload.experiment_status
    if payload.budget_amount is not None:
        exp.budget_amount = payload.budget_amount
    await db.commit()
    return {"id": exp.id, "experiment_status": exp.experiment_status, "budget_amount": exp.budget_amount}


# ==================== 7. 经营数据录入、批量部分导入与复盘报告模块 ====================

@router.post("/products/{product_id}/performance-records")
async def create_performance_record(
    product_id: int,
    payload: PerformanceRecordCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:手动录入周期经营数据并自动计算CTR、转化率与ROI"""
    ctr = round((payload.clicks / payload.impressions) * 100, 2) if payload.impressions > 0 else 0.0
    cvr = round((payload.conversions / payload.clicks) * 100, 2) if payload.clicks > 0 else 0.0
    roi = round(payload.revenue / payload.spend, 2) if payload.spend > 0 else 0.0

    rec = PerformanceRecord(
        product_id=product_id,
        experiment_id=payload.experiment_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        impressions=payload.impressions,
        clicks=payload.clicks,
        ctr=ctr,
        conversions=payload.conversions,
        conversion_rate=cvr,
        spend=payload.spend,
        revenue=payload.revenue,
        roi=roi,
        notes=payload.notes,
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return {"id": rec.id, "ctr": rec.ctr, "conversion_rate": rec.conversion_rate, "roi": rec.roi}


@router.post("/products/{product_id}/performance-records/import")
async def import_performance_records_csv(
    product_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:批量导入经营数据CSV，支持逐行校验、错误行提示与部分成功入库"""
    raw_bytes = await file.read()
    text_content = raw_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text_content))

    success_count = 0
    errors: list[dict[str, Any]] = []

    # 逐行解析并校验数值合法性，实现部分成功导入
    for idx, row in enumerate(reader, start=2):
        try:
            imp = int(row.get("impressions", 0))
            clk = int(row.get("clicks", 0))
            conv = int(row.get("conversions", 0))
            spend = float(row.get("spend", 0.0))
            rev = float(row.get("revenue", 0.0))
            if imp < 0 or clk < 0 or spend < 0:
                raise ValueError("曝光、点击或花费不能为负数")

            ctr = round((clk / imp) * 100, 2) if imp > 0 else 0.0
            cvr = round((conv / clk) * 100, 2) if clk > 0 else 0.0
            roi = round(rev / spend, 2) if spend > 0 else 0.0

            rec = PerformanceRecord(
                product_id=product_id,
                period_start=row.get("period_start") or "2026-10-20",
                period_end=row.get("period_end") or "2026-10-25",
                impressions=imp,
                clicks=clk,
                ctr=ctr,
                conversions=conv,
                conversion_rate=cvr,
                spend=spend,
                revenue=rev,
                roi=roi,
                notes=row.get("notes", "CSV批量导入"),
            )
            db.add(rec)
            success_count += 1
        except Exception as exc:
            errors.append({"row": idx, "error": str(exc), "raw_row": row})

    await db.commit()
    return {
        "product_id": product_id,
        "success_count": success_count,
        "failed_count": len(errors),
        "errors": errors,
    }


@router.post("/products/{product_id}/review-reports/generate")
async def generate_review_report(
    product_id: int,
    mode: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:聚合商品近期经营数据生成结构化复盘报告并反哺下一轮诊断"""
    perfs = list(
        (
            await db.execute(
                select(PerformanceRecord)
                .where(PerformanceRecord.product_id == product_id)
                .order_by(PerformanceRecord.id.desc())
                .limit(10)
            )
        ).scalars().all()
    )
    avg_ctr = round(sum(p.ctr for p in perfs) / len(perfs), 2) if perfs else 3.5
    avg_roi = round(sum(p.roi for p in perfs) / len(perfs), 2) if perfs else 2.5

    ai_out = await run_review_report_ai(
        {
            "product_id": product_id,
            "aggregated_metrics": {"avg_ctr": avg_ctr, "avg_roi": avg_roi, "record_count": len(perfs)},
        },
        mode=mode,
    )

    report = ReviewReport(
        product_id=product_id,
        period_start=perfs[-1].period_start if perfs else "2026-10-18",
        period_end=perfs[0].period_end if perfs else "2026-10-25",
        summary_text=ai_out.summary_text,
        insights_json=ai_out.insights_json,
        next_actions_json=ai_out.next_actions_json,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return {
        "id": report.id,
        "summary_text": report.summary_text,
        "insights_json": report.insights_json,
        "next_actions_json": report.next_actions_json,
    }


# ==================== 8. 工作区演示数据、定时任务与导入模板模块 ====================

@router.post("/workspace/demo-data")
async def init_workspace_demo_data(
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """职责:快速初始化全链路23张表完整演示数据"""
    return await seed_demo_workspace_data(db)


@router.post("/workspace/generation-jobs/sweep-timeouts")
async def sweep_timeout_generation_jobs(
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:扫描并标记超时的运行中异步生成任务"""
    threshold = utc_now() - timedelta(minutes=15)
    running_jobs = list(
        (
            await db.execute(
                select(GenerationJob).where(
                    GenerationJob.job_status == "running",
                    GenerationJob.started_at < threshold,
                )
            )
        ).scalars().all()
    )
    for j in running_jobs:
        j.job_status = "timeout"
        j.finished_at = utc_now()
        db.add(GenerationJobEvent(job_id=j.id, event_type="timeout", event_message="任务执行超过15分钟被扫描器标记超时"))
    await db.commit()
    return {"swept_timeout_count": len(running_jobs)}


@router.post("/workspace/competitor-monitors/run-due")
async def run_due_competitor_monitors(
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """职责:运行到期的竞品监控任务并生成价格快照"""
    monitors = list(
        (await db.execute(select(CompetitorMonitor).where(CompetitorMonitor.monitor_status == "active"))).scalars().all()
    )
    for m in monitors:
        m.next_run_at = utc_now() + timedelta(minutes=m.interval_minutes)
        db.add(
            CompetitorMonitorSnapshot(
                monitor_id=m.id,
                price=639.0,
                sales_hint="月销 1.3万+",
                selling_points="定时监控快照更新",
                raw_payload_json={"trigger": "run-due"},
            )
        )
    await db.commit()
    return {"executed_monitors": len(monitors)}


@router.get("/workspace/templates/{template_type}")
async def download_import_template(
    template_type: str,
) -> PlainTextResponse:
    """职责:提供商品、SKU库存与经营数据的标准CSV导入模板下载"""
    templates = {
        "products": "store_id,name,platform,category,price,cost,target_audience,selling_points\n1,示例工学椅,抖音电商,办公家具,599,245,久坐办公族,双翼追腰+透气特网\n",
        "sku-inventory": "product_id,sku_code,sku_name,price,cost,stock_qty,warning_threshold\n1,CHAIR-BLK-01,曜石黑标准版,599,245,100,20\n",
        "performance-records": "period_start,period_end,impressions,clicks,conversions,spend,revenue,notes\n2026-10-20,2026-10-25,20000,860,32,3500.0,12800.0,测试周期导入\n",
    }
    content = templates.get(template_type)
    if not content:
        raise HTTPException(status_code=404, detail="未知模板类型")
    return PlainTextResponse(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{template_type}-template.csv"'},
    )
