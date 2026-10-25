from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import (
    AdExperiment,
    Competitor,
    InventoryItem,
    InventoryMovement,
    PerformanceRecord,
    Product,
    ProductSKU,
    ReviewReport,
)


async def build_diagnosis_readonly_context(
    db: AsyncSession,
    product_id: int,
) -> dict[str, Any]:
    """职责:只读聚合本地数据库多表数据并预计算商品诊断定量指标"""
    # 1. 查询主商品与关联SKU规格列表
    prod_res = await db.execute(select(Product).where(Product.id == product_id))
    product = prod_res.scalar_one_or_none()
    if not product:
        raise ValueError(f"商品ID {product_id} 不存在")

    sku_res = await db.execute(
        select(ProductSKU).where(ProductSKU.product_id == product_id)
    )
    skus = list(sku_res.scalars().all())

    # 2. 查询竞品列表
    comp_res = await db.execute(
        select(Competitor).where(Competitor.product_id == product_id)
    )
    competitors = list(comp_res.scalars().all())

    # 3. 查询近期经营数据与上一轮复盘报告（支撑“从复盘回到诊断”闭环）
    perf_res = await db.execute(
        select(PerformanceRecord)
        .where(PerformanceRecord.product_id == product_id)
        .order_by(PerformanceRecord.id.desc())
        .limit(5)
    )
    perf_records = list(perf_res.scalars().all())

    review_res = await db.execute(
        select(ReviewReport)
        .where(ReviewReport.product_id == product_id)
        .order_by(ReviewReport.id.desc())
        .limit(1)
    )
    latest_review = review_res.scalar_one_or_none()

    # 4. 执行确定性数学预计算（毛利率、竞品均价偏离度）
    gross_margin_pct = (
        round(((product.price - product.cost) / product.price) * 100, 2)
        if product.price > 0
        else 0.0
    )
    comp_prices = [c.price for c in competitors if c.price > 0]
    avg_comp_price = round(sum(comp_prices) / len(comp_prices), 2) if comp_prices else product.price
    price_vs_comp_pct = (
        round(((product.price - avg_comp_price) / avg_comp_price) * 100, 2)
        if avg_comp_price > 0
        else 0.0
    )

    # 5. 组装并返回只读上下文结构
    return {
        "product": {
            "id": product.id,
            "name": product.name,
            "platform": product.platform,
            "category": product.category,
            "price": product.price,
            "cost": product.cost,
            "target_audience": product.target_audience,
            "selling_points": product.selling_points,
        },
        "skus": [
            {"sku_code": s.sku_code, "sku_name": s.sku_name, "price": s.price, "cost": s.cost}
            for s in skus
        ],
        "competitors": [
            {
                "name": c.name,
                "price": c.price,
                "sales_hint": c.sales_hint,
                "selling_points": c.selling_points,
                "review_keywords": c.review_keywords,
            }
            for c in competitors
        ],
        "pre_calculated": {
            "gross_margin_pct": gross_margin_pct,
            "avg_competitor_price": avg_comp_price,
            "price_vs_competitor_pct": price_vs_comp_pct,
        },
        "recent_performance": [
            {
                "period": f"{p.period_start}~{p.period_end}",
                "ctr": p.ctr,
                "conversion_rate": p.conversion_rate,
                "roi": p.roi,
            }
            for p in perf_records
        ],
        "latest_review": (
            {
                "summary_text": latest_review.summary_text,
                "insights": latest_review.insights_json,
                "next_actions": latest_review.next_actions_json,
            }
            if latest_review
            else None
        ),
    }


async def build_store_inventory_readonly_context(
    db: AsyncSession,
    store_id: int,
) -> dict[str, Any]:
    """职责:只读聚合店铺下5张库存与实验表并预计算周转天数DOS与防超卖指标"""
    # 1. 查询店铺下所有商品及运行中的投放实验
    prod_res = await db.execute(select(Product).where(Product.store_id == store_id))
    products = {p.id: p for p in prod_res.scalars().all()}
    if not products:
        return {"store_id": store_id, "sku_metrics": [], "total_tied_up_capital": 0.0}

    exp_res = await db.execute(
        select(AdExperiment).where(
            AdExperiment.product_id.in_(list(products.keys())),
            AdExperiment.experiment_status == "running",
        )
    )
    running_exp_product_ids = {e.product_id for e in exp_res.scalars().all()}

    # 2. 查询所有关联SKU与库存记录
    sku_res = await db.execute(
        select(ProductSKU).where(ProductSKU.product_id.in_(list(products.keys())))
    )
    skus = list(sku_res.scalars().all())
    sku_ids = [s.id for s in skus]

    inv_res = await db.execute(
        select(InventoryItem).where(InventoryItem.sku_id.in_(sku_ids))
    )
    inv_map = {item.sku_id: item for item in inv_res.scalars().all()}

    mov_res = await db.execute(
        select(InventoryMovement).where(InventoryMovement.sku_id.in_(sku_ids))
    )
    movements = list(mov_res.scalars().all())

    # 3. 逐个SKU计算可用库存、日均消耗、预计可售天数DOS及风险标记
    sku_metrics: list[dict[str, Any]] = []
    total_capital = 0.0

    for sku in skus:
        inv = inv_map.get(sku.id)
        stock_qty = inv.stock_qty if inv else 0
        locked_qty = inv.locked_qty if inv else 0
        warn_threshold = inv.warning_threshold if inv else 20
        available_qty = max(stock_qty - locked_qty, 0)

        # 统计该SKU历史出库总量并折算7天日均消耗速率
        outbound_qty = sum(
            abs(m.change_qty)
            for m in movements
            if m.sku_id == sku.id and m.movement_type == "outbound"
        )
        daily_burn_rate = round(max(outbound_qty / 7.0, 1.5), 2)
        days_of_supply = round(available_qty / daily_burn_rate, 1)

        # 判定四级库存状态
        if available_qty <= 0:
            stock_status = "OUT_OF_STOCK"
        elif available_qty <= warn_threshold:
            stock_status = "LOW_STOCK"
        elif available_qty > warn_threshold * 3 and outbound_qty == 0:
            stock_status = "OVERSTOCK"
        else:
            stock_status = "HEALTHY"

        # 计算建议补货量（目标维持15天安全库存）与积压资金
        target_15d_qty = int(daily_burn_rate * 15)
        suggested_restock = max(target_15d_qty - available_qty, warn_threshold) if stock_status in ("OUT_OF_STOCK", "LOW_STOCK") else 0
        tied_up_capital = round(available_qty * sku.cost, 2)
        total_capital += tied_up_capital

        # 跨模块判定广告超卖风险：可售天数<3天且商品有running投放实验
        ad_oversell_risk = (days_of_supply < 3.0) and (sku.product_id in running_exp_product_ids)

        sku_metrics.append(
            {
                "sku_id": sku.id,
                "sku_code": sku.sku_code,
                "sku_name": sku.sku_name,
                "product_id": sku.product_id,
                "product_name": products[sku.product_id].name,
                "stock_qty": stock_qty,
                "locked_qty": locked_qty,
                "available_qty": available_qty,
                "warning_threshold": warn_threshold,
                "daily_burn_rate": daily_burn_rate,
                "days_of_supply": days_of_supply,
                "stock_status": stock_status,
                "suggested_restock_qty": suggested_restock,
                "tied_up_capital": tied_up_capital,
                "ad_oversell_risk": ad_oversell_risk,
            }
        )

    return {
        "store_id": store_id,
        "sku_metrics": sku_metrics,
        "total_tied_up_capital": round(total_capital, 2),
    }
