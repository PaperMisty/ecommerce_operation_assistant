import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.infrastructure.database import AsyncSessionLocal
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


async def ensure_default_users(db: AsyncSession) -> None:
    """职责:初始化管理员、运营人员与查看人员三个默认角色账号"""
    res = await db.execute(select(User).limit(1))
    if res.scalar_one_or_none() is not None:
        return

    # 创建三类标准权限角色测试账号，默认密码均为 123456
    default_pwd = hash_password("123456")
    users = [
        User(username="admin", display_name="系统管理员", password_hash=default_pwd, role="admin", status="active"),
        User(username="operator", display_name="金牌运营专员", password_hash=default_pwd, role="operator", status="active"),
        User(username="viewer", display_name="数据查看员", password_hash=default_pwd, role="viewer", status="active"),
    ]
    db.add_all(users)
    await db.commit()


async def seed_demo_workspace_data(db: AsyncSession) -> dict[str, Any]:
    """职责:一键生成覆盖全链路23张表的电商单品运营演示数据"""
    await ensure_default_users(db)

    # 检查是否已存在演示店铺，若存在则直接返回摘要
    existing_store = (
        await db.execute(select(Store).where(Store.store_name == "极客智造官方旗舰店"))
    ).scalar_one_or_none()
    if existing_store:
        prod = (
            await db.execute(select(Product).where(Product.store_id == existing_store.id).limit(1))
        ).scalar_one_or_none()
        return {
            "status": "already_seeded",
            "store_id": existing_store.id,
            "product_id": prod.id if prod else 1,
            "message": "演示数据已就绪，可直接进入工作台体验完整闭环",
        }

    # 1. 创建店铺与安全脱敏平台账号占位
    store = Store(
        store_name="极客智造官方旗舰店",
        platform="天猫/抖音双栖",
        external_store_id="TM-STORE-88901",
        owner_name="张运营",
        remark="主营人体工学办公与数码周边核心单品",
    )
    db.add(store)
    await db.flush()

    account = PlatformAccount(
        store_id=store.id,
        platform="抖音小店",
        account_name="极客智造_官方号",
        auth_status="authorized",
        auth_meta_json={"scope": "product.read,ad.plan.suggest", "masked_app_id": "dy_***9921"},
        remark="仅保存OAuth安全元数据，不保存明文Token与Cookie",
    )
    db.add(account)

    # 2. 创建核心商品与平台映射
    product = Product(
        store_id=store.id,
        name="云感Pro人体工学护腰办公椅",
        platform="抖音电商",
        category="家具建材/办公椅",
        price=599.0,
        cost=245.0,
        target_audience="22-38岁久坐程序员、设计师、居家办公白领",
        selling_points="自适应双翼追腰系统、4D透气特网、135度大仰角午休、SGS四级防爆气压杆",
        product_url="https://example.com/products/ergonomic-chair-pro",
        images_json=["https://placehold.co/800x800/2563eb/ffffff?text=Chair+Pro+Main"],
        status="active",
    )
    db.add(product)
    await db.flush()

    mapping = PlatformProductMapping(
        product_id=product.id,
        platform="抖音电商",
        platform_product_id="DY-PROD-339102",
        platform_sku_id="DY-SKU-001",
        mapping_status="mapped",
        raw_payload_json={"sync_channel": "open_api_placeholder"},
    )
    db.add(mapping)

    # 3. 创建3个SKU规格、库存记录与出入库流水（包含低库存预警与积压场景）
    sku_specs = [
        ("CHAIR-BLK-PRO", "曜石黑-带脚托旗舰版", {"color": "曜石黑", "footrest": True}, 599.0, 245.0, 12, 4, 20, 42),
        ("CHAIR-GRY-STD", "星云灰-标准办公版", {"color": "星云灰", "footrest": False}, 499.0, 205.0, 85, 5, 25, 28),
        ("CHAIR-WHT-LUX", "极光白-定制礼盒版", {"color": "极光白", "footrest": True}, 699.0, 290.0, 95, 0, 20, 0),
    ]
    for code, name, spec, prc, cst, stock, locked, warn, out_qty in sku_specs:
        sku = ProductSKU(
            product_id=product.id,
            sku_code=code,
            sku_name=name,
            spec_json=spec,
            price=prc,
            cost=cst,
            status="active",
            platform_sku_id=f"PLAT-{code}",
        )
        db.add(sku)
        await db.flush()

        inv = InventoryItem(
            sku_id=sku.id,
            stock_qty=stock,
            locked_qty=locked,
            warning_threshold=warn,
            location_text="华东嘉兴一号仓",
        )
        db.add(inv)

        if out_qty > 0:
            mov = InventoryMovement(
                sku_id=sku.id,
                movement_type="outbound",
                change_qty=-out_qty,
                before_qty=stock + out_qty,
                after_qty=stock,
                reason_text="近7天抖音大促订单出库汇总",
                reference_type="order_batch",
                reference_id="BATCH-202610",
            )
            db.add(mov)

    # 4. 创建竞品、竞品监控与公开链接解析任务
    comp1 = Competitor(
        product_id=product.id,
        name="某米经典护腰椅2代",
        platform="抖音电商",
        url="https://example.com/competitor/chair-a",
        price=649.0,
        sales_hint="月销 1.2万+",
        title="某米人体工学电脑椅久坐不累办公家用",
        selling_points="品牌知名度高、简约外观、两段式腰靠",
        review_keywords="网布偏硬、扶手容易晃动、安装螺丝难对齐",
    )
    comp2 = Competitor(
        product_id=product.id,
        name="某歌入门级网布转椅",
        platform="天猫",
        url="https://example.com/competitor/chair-b",
        price=459.0,
        sales_hint="月销 8000+",
        title="家用书房透气网布转椅学生宿舍电脑椅",
        selling_points="低价走量、多色可选",
        review_keywords="腰托支撑力不够、坐垫半年后塌陷、轮子声音大",
    )
    db.add_all([comp1, comp2])
    await db.flush()

    monitor = CompetitorMonitor(
        competitor_id=comp1.id,
        monitor_status="active",
        interval_minutes=120,
        next_run_at=utc_now() + timedelta(hours=2),
    )
    db.add(monitor)
    await db.flush()

    snapshot = CompetitorMonitorSnapshot(
        monitor_id=monitor.id,
        price=649.0,
        sales_hint="月销 1.2万+",
        selling_points="品牌知名度高、两段式腰靠",
        raw_payload_json={"captured_by": "public_meta_parser"},
    )
    parse_task = PublicLinkParseTask(
        product_id=product.id,
        source_url="https://example.com/competitor/chair-a",
        task_status="succeeded",
        attempts=1,
        result_json={"title": comp1.title, "price_detected": 649.0, "compliance": "public_meta_only"},
    )
    db.add_all([snapshot, parse_task])

    # 5. 创建初始商品诊断、主图方案、视频脚本、生成任务与素材
    diag = ProductDiagnosis(
        product_id=product.id,
        source_type="ai_generated",
        positioning="高质价比技术型护腰椅，精准切入22-38岁久坐办公人群的腰椎酸痛痛点。",
        price_band="售价599元（毛利率59.1%），比头部竞品(649元)低50元，比低端款配置高两个代际。",
        audience_insights="核心受众每天久坐超过8小时，高度关注腰部动态贴合感与夏天透气性。",
        pain_points="竞品差评集中于：网布塌陷、扶手晃动、安装繁琐。",
        selling_point_analysis="自适应双翼追腰+SGS四级气压杆直击竞品软肋，具备强转化说服力。",
        risks="曜石黑旗舰版(CHAIR-BLK-PRO)可用库存仅剩8件，需防范投流超卖。",
        recommendations="主图强化腰托动态贴合对比；视频前3秒展示网布高弹承重测试；同步补充曜石黑库存。",
        raw_output={"engine": "seed_demo"},
    )
    plan_img = CreativePlan(
        product_id=product.id,
        plan_type="main_image",
        title="方向A：腰椎动态贴合X光对比首图",
        content_json={
            "visual_structure": "左右分屏：左侧普通椅子悬空伤腰红线警示，右侧云感Pro双翼紧密托举绿色贴合线",
            "core_copy": "久坐10小时不酸腰｜双翼动态追腰黑科技",
            "selling_point": "自适应双翼追腰系统",
        },
        rationale_text="直观可视化解决久坐痛点，信息流首屏抓停率最高。",
        status="selected",
    )
    plan_vid = CreativePlan(
        product_id=product.id,
        plan_type="video_script",
        title="脚本1：20斤哑铃砸网布暴力承重实测",
        content_json={
            "hook": "千万别乱买几百块的办公椅！来看20斤哑铃暴力测试！",
            "storyboard": "镜头1：哑铃自由落体砸向4D特网高弹回弹；镜头2：程序员后仰135度秒睡；镜头3：SGS钢印特写。",
            "voiceover": "很多椅子坐半年就塌，云感Pro采用进口高弹特网，双翼追腰怎么动都贴合！",
            "cta": "点击左下角小黄车立减100元，还享3年质保！",
        },
        rationale_text="用极具视觉冲击力的实验破除竞品‘坐垫塌陷’差评顾虑。",
        status="selected",
    )
    db.add_all([diag, plan_img, plan_vid])
    await db.flush()

    job = GenerationJob(
        product_id=product.id,
        creative_plan_id=plan_img.id,
        job_kind="image",
        job_status="succeeded",
        attempts=1,
        max_attempts=3,
        result_json={"asset_url": "https://placehold.co/1080x1080/1d4ed8/ffffff?text=AI+Main+Image+V1"},
        started_at=utc_now() - timedelta(minutes=5),
        finished_at=utc_now() - timedelta(minutes=4),
    )
    db.add(job)
    await db.flush()

    ev1 = GenerationJobEvent(job_id=job.id, event_type="queued", event_message="主图生成任务已入队")
    ev2 = GenerationJobEvent(job_id=job.id, event_type="running", event_message="Worker锁定任务并调用渲染引擎")
    ev3 = GenerationJobEvent(job_id=job.id, event_type="succeeded", event_message="素材生成完毕并自动同步至素材库")
    asset = GeneratedAsset(
        product_id=product.id,
        creative_plan_id=plan_img.id,
        asset_type="image",
        asset_url="https://placehold.co/1080x1080/1d4ed8/ffffff?text=AI+Main+Image+V1",
        model_name="wanx-v2-mock",
        width=1080,
        height=1080,
        review_status="approved",
        version_no=1,
        usage_scene="千川信息流首图测款",
        score=5,
        tags_json=["高点击", "痛点对比", "护腰"],
        remark="人工审核通过，画面痛点突出",
    )
    db.add_all([ev1, ev2, ev3, asset])
    await db.flush()

    # 6. 创建推广短链、投放建议、运行中投放实验、经营数据与复盘报告
    link = PromotionLink(
        product_id=product.id,
        link_name="抖音测评视频评论区置顶短链",
        target_url=product.product_url or "https://example.com/products/1",
        tracking_code="chair2026",
        utm_json={"utm_source": "douyin", "utm_medium": "video_comment", "utm_campaign": "pro_launch"},
        status="active",
        click_count=128,
        scene_text="短视频评论区置顶引流",
    )
    db.add(link)
    await db.flush()

    click_log = PromotionLinkClick(
        promotion_link_id=link.id,
        client_ip="114.247.50.12",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
    )
    ad_rec = AdRecommendation(
        product_id=product.id,
        summary_text="围绕痛点对比主图与哑铃测评视频开展千川oCPM控成本投放。",
        objective_text="稳定冷启动CTR >= 4.0%，首周ROI >= 2.6",
        audience_segments_json=[{"segment_name": "办公椅/久坐腰靠高意向人群", "age_range": "22-38", "priority": "P0"}],
        budget_plan_json={"daily_budget_cny": 800.0, "testing_ratio": "30%", "scaling_ratio": "70%"},
        creative_tests_json=[{"test_group": "X光腰托对比图 vs 哑铃实测视频", "metric_focus": "CTR & ROI"}],
        bid_strategy_json={"bid_mode": "目标ROI控成本", "target_roi": 2.6},
        risk_controls_json=["曜石黑SKU可售不足3天时立即暂停放量"],
        next_steps_json=["人工确认通过后启动A/B赛马实验"],
        confirm_status="confirmed",
        confirmed_by="admin",
        confirmed_at=utc_now() - timedelta(days=1),
        confirm_remark="策略合理，批准执行首轮A/B测试",
    )
    ad_exp = AdExperiment(
        product_id=product.id,
        related_asset_id=asset.id,
        related_link_id=link.id,
        experiment_name="实验A组：痛点对比图+测评视频联合赛马",
        target_text="验证双翼追腰痛点视觉能否将CTR提升至4%以上",
        audience_text="22-38岁一二线城市职场久坐人群",
        budget_amount=800.0,
        success_metric_text="CTR >= 4.0%, ROI >= 2.5",
        hypothesis_text="直观展示腰部支撑对比可降低比价流失率",
        experiment_status="running",
    )
    db.add_all([click_log, ad_rec, ad_exp])
    await db.flush()

    perf = PerformanceRecord(
        product_id=product.id,
        creative_plan_id=plan_img.id,
        generated_asset_id=asset.id,
        promotion_link_id=link.id,
        experiment_id=ad_exp.id,
        period_start="2026-10-18",
        period_end="2026-10-24",
        impressions=45000,
        clicks=1890,
        ctr=4.2,
        conversions=68,
        conversion_rate=3.6,
        spend=9800.0,
        revenue=40732.0,
        roi=4.16,
        notes="痛点对比主图表现优异，但曜石黑规格库存消耗极快",
    )
    review = ReviewReport(
        product_id=product.id,
        period_start="2026-10-18",
        period_end="2026-10-24",
        summary_text="首周测试CTR达4.2%，ROI达4.16，远超2.6目标线；但主力曜石黑SKU濒临断货，极光白定制版动销为0。",
        insights_json=[
            {"dimension": "爆款素材验证", "finding": "X光腰托对比图CTR高达4.2%，用户对腰部支撑可视化买单意愿极强"},
            {"dimension": "SKU结构失衡", "finding": "订单90%集中在曜石黑带脚托版，极光白礼盒版价格偏高导致滞销"},
        ],
        next_actions_json=[
            {"action": "回到【诊断】环节：针对极光白礼盒版补充赠品或调价策略，开启第二轮诊断优化", "target_tab": "诊断"},
            {"action": "前往【店铺库存建议】：紧急补货曜石黑SKU，防止运行中实验超卖", "target_tab": "商品&竞品"},
        ],
    )
    db.add_all([perf, review])
    await db.commit()

    return {
        "status": "seeded",
        "store_id": store.id,
        "product_id": product.id,
        "message": "已成功初始化全链路23张表完整演示数据",
    }


async def execute_generation_job_async(job_id: int) -> None:
    """职责:后台异步协程消费图片/视频生成任务并自动同步素材入库"""
    await asyncio.sleep(0.3)
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(GenerationJob).where(GenerationJob.id == job_id))
        job = res.scalar_one_or_none()
        if not job or job.job_status == "cancelled":
            return

        # 1. 锁定任务并切换为 running 状态
        job.job_status = "running"
        job.attempts += 1
        job.locked_at = utc_now()
        job.locked_by = "async-worker-1"
        job.started_at = utc_now()
        db.add(
            GenerationJobEvent(
                job_id=job.id,
                event_type="running",
                event_message=f"异步Worker已锁定任务 (第{job.attempts}次尝试)，正在合成{job.job_kind}素材...",
            )
        )
        await db.commit()

        # 2. 模拟异步渲染耗时并再次检查是否被用户中途取消
        await asyncio.sleep(0.5)
        await db.refresh(job)
        if job.job_status == "cancelled":
            return

        # 3. 标记任务成功并自动写入 generated_assets 素材库
        asset_url = (
            f"https://placehold.co/1080x1080/059669/ffffff?text=Generated+{job.job_kind.upper()}+Job+{job.id}"
            if job.job_kind == "image"
            else f"https://placehold.co/1080x1920/7c3aed/ffffff?text=Generated+VIDEO+Job+{job.id}"
        )
        job.job_status = "succeeded"
        job.finished_at = datetime.now(timezone.utc)
        job.result_json = {"asset_url": asset_url, "generated_by": "async_worker"}

        db.add(
            GenerationJobEvent(
                job_id=job.id,
                event_type="succeeded",
                event_message=f"素材生成成功，产出地址: {asset_url}",
            )
        )
        db.add(
            GeneratedAsset(
                product_id=job.product_id,
                creative_plan_id=job.creative_plan_id,
                asset_type=job.job_kind,
                asset_url=asset_url,
                model_name="eoa-media-synth-v1",
                width=1080,
                height=1080 if job.job_kind == "image" else 1920,
                duration_sec=15 if job.job_kind == "video" else 0,
                review_status="pending",
                version_no=job.attempts,
                usage_scene="千川信息流测款",
                score=5,
                tags_json=[job.job_kind, "AI合成", "待审核"],
                remark="由异步任务自动落库",
            )
        )
        await db.commit()
