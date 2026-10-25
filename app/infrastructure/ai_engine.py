import json
import os
import re
from typing import Any, TypeVar
from pydantic import BaseModel
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END

from app.core.config import get_settings
from app.schemas.contracts import (
    AdRecommendationAIOutput,
    DiagnosisAIOutput,
    InventoryAdviceAIOutput,
    MainImageAIOutput,
    MainImageDirectionItem,
    RestockItemSchema,
    ReviewReportAIOutput,
    VideoScriptAIOutput,
    VideoScriptItem,
)

T = TypeVar("T", bound=BaseModel)

# 全局复用的ChatOpenAI客户端缓存
_llm_instance: ChatOpenAI | None = None


def get_langfuse_callbacks() -> list[Any]:
    """职责:构造Langfuse可观测层CallbackHandler列表"""
    settings = get_settings()
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return []

    # 同步环境变量供Langfuse SDK内部读取
    os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
    os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
    os.environ["LANGFUSE_BASE_URL"] = settings.langfuse_base_url
    os.environ["LANGFUSE_HOST"] = settings.langfuse_base_url

    try:
        from langfuse.langchain import CallbackHandler

        return [CallbackHandler()]
    except Exception:
        return []


def get_chat_llm() -> ChatOpenAI:
    """职责:获取或初始化全局复用的LangChain ChatOpenAI实例"""
    global _llm_instance
    settings = get_settings()
    if _llm_instance is None:
        _llm_instance = ChatOpenAI(
            api_key=settings.qwen_api_key,
            base_url=settings.qwen_base_url,
            model=settings.llm_model,
            temperature=0.3,
            max_retries=2,
            timeout=45.0,
        )
    return _llm_instance


def _extract_json_block(raw_text: str) -> str:
    """职责:从模型原始输出文本中清理思考标签并提取纯净JSON字符串"""
    # 移除可能包含的 <think>...</think> 推理标签
    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
    # 提取 ```json ... ``` 代码块
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
    if fenced:
        return fenced.group(1)
    # 兜底提取最外层花括号
    brace_match = re.search(r"(\{.*\})", cleaned, flags=re.DOTALL)
    if brace_match:
        return brace_match.group(1)
    return cleaned


async def invoke_langchain_structured(
    schema_cls: type[T],
    system_prompt: str,
    user_context: dict[str, Any],
) -> T:
    """职责:通过LangChain与Langfuse调用真实大模型并解析为Pydantic结构化对象"""
    parser = PydanticOutputParser(pydantic_object=schema_cls)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "{system_prompt}\n\n请严格只输出合法的JSON对象，不要附加额外解释。\n{format_instructions}",
            ),
            ("human", "业务只读聚合上下文数据如下：\n{context_json}"),
        ]
    )

    # 组装LangChain LCEL异步调用链并挂载Langfuse观测回调
    llm = get_chat_llm()
    chain = prompt | llm
    callbacks = get_langfuse_callbacks()
    response_msg = await chain.ainvoke(
        {
            "system_prompt": system_prompt,
            "format_instructions": parser.get_format_instructions(),
            "context_json": json.dumps(user_context, ensure_ascii=False, indent=2),
        },
        config={"callbacks": callbacks} if callbacks else None,
    )

    # 提取文本并校验转换为目标Pydantic模型
    content_str = (
        response_msg.content
        if isinstance(response_msg.content, str)
        else json.dumps(response_msg.content, ensure_ascii=False)
    )
    json_str = _extract_json_block(content_str)
    return schema_cls.model_validate_json(json_str)


# ==================== 各业务节点的 Mock 与 Real 双模编排函数 ====================

async def run_diagnosis_ai(
    context: dict[str, Any],
    mode: str | None = None,
) -> DiagnosisAIOutput:
    """职责:基于本地只读聚合上下文执行商品7维结构化诊断(支持Mock与Real双模式)"""
    active_mode = (mode or get_settings().ai_mode).lower()
    product_name = context.get("product", {}).get("name", "核心主推商品")
    margin_pct = context.get("pre_calculated", {}).get("gross_margin_pct", 52.5)
    comp_diff = context.get("pre_calculated", {}).get("price_vs_competitor_pct", -5.2)
    has_last_review = bool(context.get("latest_review"))

    # Mock模式：返回结合预计算指标的高保真结构化诊断
    if active_mode == "mock":
        iter_tag = "【结合上轮复盘迭代】" if has_last_review else "【首轮冷启动诊断】"
        return DiagnosisAIOutput(
            positioning=f"{iter_tag}{product_name}定位为高质价比功能型核心单品，主打实用场景痛点解决。",
            price_band=f"当前毛利率为 {margin_pct}%，较竞品均价偏离 {comp_diff}%，处于主流黄金转化价格带，具备投放竞价空间。",
            audience_insights="核心人群为22-38岁注重品质与效率的都市白领及年轻家庭，对决策时长敏感，偏好直观对比展示。",
            pain_points="竞品评论高频反馈：材质耐用度不足、售后响应慢、使用说明不直观。",
            selling_point_analysis="本品核心卖点突出耐用材质与即开即用体验，与同质化竞品拉开差异，但首图视觉冲击力待强化。",
            risks="若仅靠泛流量投放易导致CTR偏低；部分主推规格需关注库存周转防止断货。",
            recommendations="1. 主图突出核心痛点前后对比；2. 短视频前3秒直击竞品差评痛点；3. 针对高毛利SKU倾斜70%测试预算。",
        )

    # Real模式：使用LangGraph单节点状态机包装LangChain结构化调用
    async def _diag_node(state: dict[str, Any]) -> dict[str, Any]:
        """职责:LangGraph商品诊断执行节点"""
        res = await invoke_langchain_structured(
            DiagnosisAIOutput,
            "你是资深电商运营专家。请根据商品、SKU毛利预计算、竞品对标与历史复盘数据，输出7维结构化商品诊断。",
            state["context"],
        )
        return {"output": res}

    graph_builder = StateGraph(dict)
    graph_builder.add_node("diagnosis_node", _diag_node)
    graph_builder.add_edge(START, "diagnosis_node")
    graph_builder.add_edge("diagnosis_node", END)
    compiled = graph_builder.compile()
    result_state = await compiled.ainvoke({"context": context})
    return result_state["output"]


async def run_main_image_ai(
    context: dict[str, Any],
    mode: str | None = None,
) -> MainImageAIOutput:
    """职责:生成至少3个主图策划方向(支持Mock与Real双模式)"""
    active_mode = (mode or get_settings().ai_mode).lower()
    product_name = context.get("product_name", "主推商品")

    # Mock模式：快速返回3个差异化主图方案
    if active_mode == "mock":
        return MainImageAIOutput(
            directions=[
                MainImageDirectionItem(
                    title=f"{product_name}-方向A：痛点视觉暴击版",
                    visual_structure="左旧右新分屏对比构图，左侧暗色调展示传统痛点，右侧高光微距展示本品核心细节",
                    core_copy="告别繁琐低效｜一秒升级体验",
                    selling_point="核心差异化结构设计",
                    rationale="利用强烈视觉反差在信息流前1秒抓停滑动手指，提升首图点击率(CTR)。",
                ),
                MainImageDirectionItem(
                    title=f"{product_name}-方向B：真实高频场景代入版",
                    visual_structure="目标人群在真实居家/办公场景中手持使用特写，角标展示权威检测或销量背书",
                    core_copy="万千用户实测好物｜闭眼入不踩雷",
                    selling_point="高颜值与多场景适配性",
                    rationale="增强目标受众代入感与信任背书，降低新客加购心理门槛。",
                ),
                MainImageDirectionItem(
                    title=f"{product_name}-方向C：高性价比规格全家福版",
                    visual_structure="居中立体陈列商品主体与赠品配件，底部清晰罗列3大核心参数指标",
                    core_copy="旗舰品质｜限时高性价比礼遇",
                    selling_point="越级配置与高质价比",
                    rationale="针对比价型搜索流量，直观展示到手价值感，直接拉升详情页转化率(CVR)。",
                ),
            ]
        )

    # Real模式：调用真实大模型结构化生成
    return await invoke_langchain_structured(
        MainImageAIOutput,
        "你是电商视觉营销总监。请结合商品信息与最新诊断结论，输出至少3个不同切入点的主图策划方案。",
        context,
    )


async def run_video_script_ai(
    context: dict[str, Any],
    mode: str | None = None,
) -> VideoScriptAIOutput:
    """职责:生成至少3条短视频脚本方案(支持Mock与Real双模式)"""
    active_mode = (mode or get_settings().ai_mode).lower()
    product_name = context.get("product_name", "主推商品")

    # Mock模式：返回3条含黄金前3秒钩子的短视频脚本
    if active_mode == "mock":
        return VideoScriptAIOutput(
            scripts=[
                VideoScriptItem(
                    title=f"{product_name}-脚本1：痛点反问测评流",
                    hook="为什么你之前买的同类产品总是用不久？看这组暴力实测！",
                    storyboard="镜头1：展示普通产品翻车瞬间；镜头2：切入本品微距核心部件测试；镜头3：展示丝滑使用效果。",
                    voiceover=f"市面上很多产品只做表面功夫，而这款{product_name}直接把核心材质拉满，实测耐用度提升3倍！",
                    cta="点击左下方链接查看专属福利价，库存有限先到先得！",
                ),
                VideoScriptItem(
                    title=f"{product_name}-脚本2：沉浸式开箱场景流",
                    hook="花小钱办大事！这绝对是我今年挖到最值的宝藏单品！",
                    storyboard="镜头1：ASMR沉浸式拆箱；镜头2：多角度展示颜值与细节；镜头3：真实生活场景3秒快速上手演示。",
                    voiceover=f"颜值质感双在线，不管是自用还是送人都超有面子，关键是价格还这么实在！",
                    cta="趁现在活动还没结束，赶紧点左下角小黄车带回家！",
                ),
                VideoScriptItem(
                    title=f"{product_name}-脚本3：竞品差评解答流",
                    hook="买前必看！30秒教你避开90%的选购大坑！",
                    storyboard="镜头1：主播手持白板列出3大常见差评坑；镜头2：逐一展示本品如何针对性解决；镜头3：价格锚点对比。",
                    voiceover=f"很多朋友担心不好用、难打理，今天这款升级版{product_name}一次性帮你解决所有顾虑。",
                    cta="评论区置顶链接已开启限时内购通道，点击立即抢购！",
                ),
            ]
        )

    # Real模式：调用真实大模型结构化生成
    return await invoke_langchain_structured(
        VideoScriptAIOutput,
        "你是金牌短视频带货编导。请基于商品诊断与卖点，创作至少3条高转化短视频脚本（含开头钩子、分镜、口播、转化引导）。",
        context,
    )


async def run_ad_recommendation_ai(
    context: dict[str, Any],
    mode: str | None = None,
) -> AdRecommendationAIOutput:
    """职责:生成8维结构化投放建议并进入人工确认HITL环节(支持Mock与Real双模式)"""
    active_mode = (mode or get_settings().ai_mode).lower()
    product_name = context.get("product_name", "主推商品")

    # Mock模式
    if active_mode == "mock":
        return AdRecommendationAIOutput(
            summary_text=f"针对【{product_name}】采取“搜索精准收割 + 短视频信息流赛马测款”双轮驱动策略，仅输出策略建议供人工确认，不自动执行扣费。",
            objective_text="首周测试目标：筛选CTR > 3.8%的优质图文/视频素材，稳定整体投放ROI >= 2.5。",
            audience_segments_json=[
                {"segment_name": "核心痛点精准词包人群", "age_range": "23-35", "priority": "P0"},
                {"segment_name": "竞品浏览未购潜客人群", "age_range": "25-40", "priority": "P1"},
            ],
            budget_plan_json={
                "daily_budget_cny": 600.0,
                "testing_ratio": "30%用于新素材冷启动赛马",
                "scaling_ratio": "70%集中投向高转化主推SKU与胜出素材",
            },
            creative_tests_json=[
                {"test_group": "A组-痛点对比主图", "metric_focus": "首屏点击率(CTR)"},
                {"test_group": "B组-沉浸式测评视频", "metric_focus": "3秒完播率与加购率"},
            ],
            bid_strategy_json={
                "bid_mode": "控成本投放 (oCPM / 目标ROI)",
                "target_roi": 2.5,
                "cold_start_boost": "前24小时允许出价上浮10%加速建模",
            },
            risk_controls_json=[
                "单计划消耗满150元且0转化时，提醒运营人员手动关停止损",
                "关联SKU预计可售天数(DOS)低于3天时，严禁放量防止超卖",
            ],
            next_steps_json=[
                "1. 请运营人员或管理员在下方执行【人工确认】或【驳回】",
                "2. 确认通过后，一键生成A/B投放实验计划并绑定追踪短链",
            ],
        )

    # Real模式
    return await invoke_langchain_structured(
        AdRecommendationAIOutput,
        "你是电商效果广告投手专家。请根据商品利润空间、已选素材方案与库存状态，生成8维结构化投放策略建议（严禁直接触发扣费）。",
        context,
    )


async def run_review_report_ai(
    context: dict[str, Any],
    mode: str | None = None,
) -> ReviewReportAIOutput:
    """职责:汇总周期经营数据生成复盘报告并反哺下一轮商品诊断(支持Mock与Real双模式)"""
    active_mode = (mode or get_settings().ai_mode).lower()
    metrics = context.get("aggregated_metrics", {})
    avg_ctr = metrics.get("avg_ctr", 3.6)
    avg_roi = metrics.get("avg_roi", 2.68)

    # Mock模式
    if active_mode == "mock":
        return ReviewReportAIOutput(
            summary_text=f"本周期累计实现综合CTR {avg_ctr:.2f}%，综合ROI {avg_roi:.2f}。痛点对比类素材表现显著优于泛场景素材，但部分流量在详情页首屏存在流失。",
            insights_json=[
                {
                    "dimension": "素材点击表现",
                    "finding": "痛点视觉暴击主图与测评视频CTR高出均值28%，验证用户对耐用度痛点高度敏感。",
                },
                {
                    "dimension": "转化漏斗归因",
                    "finding": "点击到加购率良好，但高客单规格转化偏慢，需补充规格对比导购图。",
                },
            ],
            next_actions_json=[
                {
                    "action": "回流商品诊断：将‘规格导购不够直观’纳入下一轮诊断风险点，迭代主图C方案",
                    "target_tab": "诊断",
                },
                {
                    "action": "关停ROI低于1.5的尾部测试计划，将预算集中至胜出素材实验组",
                    "target_tab": "投放",
                },
            ],
        )

    # Real模式
    return await invoke_langchain_structured(
        ReviewReportAIOutput,
        "你是电商数据分析与复盘专家。请基于周期经营统计数据（曝光、点击、CTR、转化、花费、GMV、ROI），生成结构化复盘报告及驱动下一轮诊断的行动项。",
        context,
    )


async def run_inventory_advice_ai(
    context: dict[str, Any],
    mode: str | None = None,
) -> InventoryAdviceAIOutput:
    """职责:基于本地5表只读预计算指标生成店铺AI库存建议(支持Mock与Real双模式)"""
    active_mode = (mode or get_settings().ai_mode).lower()
    sku_metrics: list[dict[str, Any]] = context.get("sku_metrics", [])

    # Mock模式：直接基于确定性预计算指标生成精准补货与联动建议
    if active_mode == "mock":
        restock_list: list[RestockItemSchema] = []
        synergy_actions: list[str] = []
        low_count = 0

        for item in sku_metrics:
            status_code = item.get("stock_status", "HEALTHY")
            if status_code in ("OUT_OF_STOCK", "LOW_STOCK"):
                low_count += 1
                restock_list.append(
                    RestockItemSchema(
                        sku_code=item["sku_code"],
                        sku_name=item["sku_name"],
                        available_qty=item["available_qty"],
                        days_of_supply=item["days_of_supply"],
                        suggested_restock_qty=item["suggested_restock_qty"],
                        priority="urgent" if status_code == "OUT_OF_STOCK" or item["days_of_supply"] < 3 else "high",
                        reason=f"当前可用库存{item['available_qty']}件，日均消耗{item['daily_burn_rate']}件，预计仅够售卖{item['days_of_supply']}天，建议按15天安全水位补货。",
                    )
                )
            if item.get("ad_oversell_risk"):
                synergy_actions.append(
                    f"【防超卖预警】SKU [{item['sku_code']}] 预计可售天数仅 {item['days_of_supply']} 天，且关联商品存在运行中(running)的投放实验，请立即调低预算或暂停实验！"
                )
            if status_code == "OVERSTOCK":
                synergy_actions.append(
                    f"【清仓促动销】SKU [{item['sku_code']}] 近7天动销缓慢且库存积压（占用资金 ¥{item['tied_up_capital']:.2f}），建议在链接页生成专属清仓短链并搭配组合促销。"
                )

        if not synergy_actions:
            synergy_actions.append("当前主力SKU库存与广告投放节奏匹配良好，建议保持日常动销监控。")

        return InventoryAdviceAIOutput(
            store_health_summary=(
                f"店铺共监控 {len(sku_metrics)} 个SKU，其中 {low_count} 个触发低库存/断货预警，"
                f"总计占用库存成本资金 ¥{context.get('total_tied_up_capital', 0.0):.2f}。"
            ),
            restock_recommendations=restock_list,
            operation_synergy_actions=synergy_actions,
        )

    # Real模式：将规则引擎预计算结果交给真实大模型生成结构化库存建议
    return await invoke_langchain_structured(
        InventoryAdviceAIOutput,
        "你是电商供应链与库存协同专家。请严格依据给定的本地数据库只读预计算指标（可用库存、日均消耗、DOS可售天数、广告超卖风险标记），输出结构化库存补货与运营联动建议。",
        context,
    )
