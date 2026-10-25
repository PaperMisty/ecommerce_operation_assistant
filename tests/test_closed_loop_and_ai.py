import asyncio
import httpx
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_full_closed_loop_mock_and_real_ai() -> None:
    """职责:先后验证Mock全链路闭环、Session Cookie属性以及.env真实API与Langfuse调用"""
    # 1. 启动FastAPI Lifespan(初始化PostgreSQL 23张表与连接池)
    from app.infrastructure.database import AsyncSessionLocal, async_engine
    from app.infrastructure.http_client import init_http_pool
    from app.models.entities import Base
    from app.services.demo_and_jobs import ensure_default_users

    await init_http_pool()
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        await ensure_default_users(session)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://testserver",
        follow_redirects=False,
    ) as client:
        # 2. 测试登录接口并校验 Set-Cookie 的 HttpOnly + SameSite=lax + Secure 属性
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "123456"},
        )
        assert login_res.status_code == 200
        set_cookie_header = login_res.headers.get("set-cookie", "").lower()
        assert "eoa_session_id=" in set_cookie_header
        assert "httponly" in set_cookie_header
        assert "samesite=lax" in set_cookie_header
        assert "secure" in set_cookie_header

        # 3. 校验 Session Cookie 会话保持 (/api/v1/auth/me)
        me_res = await client.get("/api/v1/auth/me")
        assert me_res.status_code == 200
        assert me_res.json()["username"] == "admin"

        # 4. 初始化全链路23张表演示数据
        demo_res = await client.post("/api/v1/workspace/demo-data")
        assert demo_res.status_code == 200
        store_id = demo_res.json()["store_id"]
        product_id = demo_res.json()["product_id"]

        # 5. 第一阶段(Mock模式): 测试本地只读聚合的店铺库存监控与AI库存建议
        inv_mock_res = await client.post(
            f"/api/v1/stores/{store_id}/inventory-advice/generate?mode=mock"
        )
        assert inv_mock_res.status_code == 200
        inv_data = inv_mock_res.json()
        assert len(inv_data["readonly_pre_calculated"]["sku_metrics"]) >= 3
        assert len(inv_data["ai_advice"]["restock_recommendations"]) >= 1

        # 6. 第一阶段(Mock模式): 测试单品运营完整闭环 (诊断->方案->异步素材->短链->投放HITL确认->导入->复盘)
        diag_mock_res = await client.post(
            f"/api/v1/products/{product_id}/diagnoses/generate?mode=mock"
        )
        assert diag_mock_res.status_code == 200
        diag_id = diag_mock_res.json()["id"]

        edit_diag_res = await client.patch(
            f"/api/v1/products/{product_id}/diagnoses/{diag_id}",
            json={"positioning": "【人工微调】高质价比人体工学护腰旗舰椅"},
        )
        assert edit_diag_res.status_code == 200

        img_plans_res = await client.post(
            f"/api/v1/products/{product_id}/creative-plans/main-images/generate?mode=mock"
        )
        assert img_plans_res.status_code == 200
        assert len(img_plans_res.json()) >= 3
        plan_id = img_plans_res.json()[0]["id"]

        vid_plans_res = await client.post(
            f"/api/v1/products/{product_id}/creative-plans/video-scripts/generate?mode=mock"
        )
        assert vid_plans_res.status_code == 200
        assert len(vid_plans_res.json()) >= 3

        job_res = await client.post(
            f"/api/v1/products/{product_id}/creative-plans/{plan_id}/images/generate"
        )
        assert job_res.status_code == 200
        await asyncio.sleep(1.0)

        ad_rec_res = await client.post(
            f"/api/v1/products/{product_id}/ad-recommendations/generate?mode=mock"
        )
        assert ad_rec_res.status_code == 200
        rec_id = ad_rec_res.json()["id"]

        confirm_res = await client.patch(
            f"/api/v1/products/{product_id}/ad-recommendations/{rec_id}/confirmation",
            json={"confirm_status": "confirmed", "confirm_remark": "运营负责人审核通过"},
        )
        assert confirm_res.status_code == 200
        assert confirm_res.json()["confirm_status"] == "confirmed"

        csv_body = (
            "period_start,period_end,impressions,clicks,conversions,spend,revenue,notes\n"
            "2026-10-20,2026-10-22,10000,450,20,1500.0,6000.0,正常数据行\n"
            "2026-10-23,2026-10-25,-500,100,5,500.0,1000.0,故意错误负数行\n"
        )
        import_res = await client.post(
            f"/api/v1/products/{product_id}/performance-records/import",
            files={"file": ("perf.csv", csv_body.encode("utf-8"), "text/csv")},
        )
        assert import_res.status_code == 200
        assert import_res.json()["success_count"] == 1
        assert import_res.json()["failed_count"] == 1

        rev_mock_res = await client.post(
            f"/api/v1/products/{product_id}/review-reports/generate?mode=mock"
        )
        assert rev_mock_res.status_code == 200

        # 7. 第二阶段(Real模式): 调用 .env 中的真实大模型(deepseek-v4.1-flash)与Langfuse观测
        diag_real_res = await client.post(
            f"/api/v1/products/{product_id}/diagnoses/generate?mode=real"
        )
        assert diag_real_res.status_code == 200
        real_diag_data = diag_real_res.json()
        assert len(real_diag_data["positioning"]) > 5
        assert len(real_diag_data["recommendations"]) > 5

        inv_real_res = await client.post(
            f"/api/v1/stores/{store_id}/inventory-advice/generate?mode=real"
        )
        assert inv_real_res.status_code == 200
        real_inv_data = inv_real_res.json()
        assert len(real_inv_data["ai_advice"]["store_health_summary"]) > 5
