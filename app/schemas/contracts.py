from typing import Any
from pydantic import BaseModel, Field


# ==================== 1. AI 强结构化输出 Schema (供 LangChain with_structured_output 使用) ====================

class DiagnosisAIOutput(BaseModel):
    """职责:约束商品诊断AI输出的7个强制结构化维度"""
    positioning: str = Field(description="商品定位分析")
    price_band: str = Field(description="价格带竞争力与毛利分析")
    audience_insights: str = Field(description="目标人群画像与场景洞察")
    pain_points: str = Field(description="用户核心痛点提炼")
    selling_point_analysis: str = Field(description="本品与竞品卖点对比分析")
    risks: str = Field(description="潜在经营与转化风险点")
    recommendations: str = Field(description="下一步图文视觉与定价优化建议")


class MainImageDirectionItem(BaseModel):
    """职责:单个主图策划方向结构"""
    title: str = Field(description="方案标题")
    visual_structure: str = Field(description="画面构图与视觉主体结构")
    core_copy: str = Field(description="画面核心大字文案")
    selling_point: str = Field(description="重点突出的单一核心卖点")
    rationale: str = Field(description="方案策划理由")


class MainImageAIOutput(BaseModel):
    """职责:约束主图方案至少输出3个策划方向"""
    directions: list[MainImageDirectionItem] = Field(
        description="至少3个不同切入点的主图方案列表"
    )


class VideoScriptItem(BaseModel):
    """职责:单条短视频脚本四要素结构"""
    title: str = Field(description="脚本名称")
    hook: str = Field(description="黄金前3秒开头钩子")
    storyboard: str = Field(description="镜头分镜画面描述")
    voiceover: str = Field(description="口播台词文案")
    cta: str = Field(description="结尾转化引导动作")


class VideoScriptAIOutput(BaseModel):
    """职责:约束视频脚本至少输出3条独立脚本"""
    scripts: list[VideoScriptItem] = Field(
        description="至少3条不同痛点/场景切入的短视频脚本"
    )


class AdRecommendationAIOutput(BaseModel):
    """职责:约束投放建议输出的8个结构化字段"""
    summary_text: str = Field(description="策略总摘要")
    objective_text: str = Field(description="本轮投放核心目标")
    audience_segments_json: list[dict[str, Any]] = Field(description="定向人群分层建议列表")
    budget_plan_json: dict[str, Any] = Field(description="日预算与阶段分配建议")
    creative_tests_json: list[dict[str, Any]] = Field(description="主图与视频素材赛马测试矩阵")
    bid_strategy_json: dict[str, Any] = Field(description="出价方式与目标ROI设置")
    risk_controls_json: list[str] = Field(description="止损线与库存防超卖风控规则")
    next_steps_json: list[str] = Field(description="人工确认后的执行步骤")


class ReviewReportAIOutput(BaseModel):
    """职责:约束复盘报告输出的4个结构化部分"""
    summary_text: str = Field(description="周期经营核心摘要与问题判断")
    insights_json: list[dict[str, Any]] = Field(description="核心数据洞察与归因分析列表")
    next_actions_json: list[dict[str, Any]] = Field(description="驱动下一轮诊断与优化的行动建议")


class RestockItemSchema(BaseModel):
    """职责:单个SKU紧急补货建议"""
    sku_code: str = Field(description="SKU编码")
    sku_name: str = Field(description="SKU名称")
    available_qty: int = Field(description="当前可用库存")
    days_of_supply: float = Field(description="预计可售天数DOS")
    suggested_restock_qty: int = Field(description="建议补货数量")
    priority: str = Field(description="优先级: urgent / high / medium")
    reason: str = Field(description="补货计算依据")


class InventoryAdviceAIOutput(BaseModel):
    """职责:约束店铺级AI库存建议结构化输出"""
    store_health_summary: str = Field(description="店铺整体库存健康度与资金占用总结")
    restock_recommendations: list[RestockItemSchema] = Field(description="低库存与断货SKU补货清单")
    operation_synergy_actions: list[str] = Field(description="库存与广告投放/清仓短链联动动作建议")


# ==================== 2. RESTful API 请求入参 Schema ====================

class LoginRequest(BaseModel):
    """职责:登录接口请求载荷"""
    username: str
    password: str


class UserCreateRequest(BaseModel):
    """职责:创建系统用户请求载荷"""
    username: str
    display_name: str
    password: str
    role: str = "operator"


class UserUpdateRequest(BaseModel):
    """职责:更新用户角色或状态请求载荷"""
    display_name: str | None = None
    role: str | None = None
    status: str | None = None


class StoreCreateRequest(BaseModel):
    """职责:创建店铺请求载荷"""
    store_name: str
    platform: str
    external_store_id: str | None = None
    owner_name: str
    remark: str | None = None


class StoreUpdateRequest(BaseModel):
    """职责:更新店铺请求载荷"""
    store_name: str | None = None
    platform: str | None = None
    owner_name: str | None = None
    remark: str | None = None


class PlatformAccountCreateRequest(BaseModel):
    """职责:创建平台账号安全占位请求载荷"""
    platform: str
    account_name: str
    remark: str | None = None


class ProductCreateRequest(BaseModel):
    """职责:创建商品请求载荷"""
    store_id: int
    name: str
    platform: str
    category: str
    price: float
    cost: float
    target_audience: str = ""
    selling_points: str = ""
    product_url: str | None = None
    status: str = "active"


class ProductUpdateRequest(BaseModel):
    """职责:更新商品基础信息请求载荷"""
    name: str | None = None
    category: str | None = None
    price: float | None = None
    cost: float | None = None
    target_audience: str | None = None
    selling_points: str | None = None
    status: str | None = None


class SKUCreateRequest(BaseModel):
    """职责:新增商品SKU与初始库存请求载荷"""
    sku_code: str
    sku_name: str
    spec_json: dict[str, Any] = Field(default_factory=dict)
    price: float
    cost: float
    initial_stock: int = 100
    warning_threshold: int = 20


class InventoryAdjustRequest(BaseModel):
    """职责:调整SKU库存并生成流水请求载荷"""
    sku_id: int
    movement_type: str = "adjust"  # inbound, outbound, adjust
    change_qty: int
    reason_text: str = "人工盘点调整"


class CompetitorCreateRequest(BaseModel):
    """职责:录入竞品请求载荷"""
    name: str
    platform: str
    url: str = ""
    price: float = 0.0
    sales_hint: str = ""
    title: str = ""
    selling_points: str = ""
    review_keywords: str = ""


class LinkParseCreateRequest(BaseModel):
    """职责:创建公开链接解析任务请求载荷"""
    source_url: str


class DiagnosisUpdateRequest(BaseModel):
    """职责:人工编辑保存商品诊断请求载荷"""
    positioning: str | None = None
    price_band: str | None = None
    audience_insights: str | None = None
    pain_points: str | None = None
    selling_point_analysis: str | None = None
    risks: str | None = None
    recommendations: str | None = None


class CreativePlanUpdateRequest(BaseModel):
    """职责:人工编辑方案内容或切换状态(draft/selected/archived)请求载荷"""
    title: str | None = None
    content_json: dict[str, Any] | None = None
    rationale_text: str | None = None
    status: str | None = None


class AssetUpdateRequest(BaseModel):
    """职责:更新素材库审核状态、评分、标签与备注请求载荷"""
    asset_id: int
    review_status: str | None = None
    usage_scene: str | None = None
    score: int | None = None
    tags_json: list[str] | None = None
    remark: str | None = None


class PromotionLinkCreateRequest(BaseModel):
    """职责:创建推广追踪短链请求载荷"""
    link_name: str
    target_url: str
    scene_text: str = "短视频评论区置顶"
    utm_source: str = "douyin"
    utm_medium: str = "short_video"
    utm_campaign: str = "single_product_boost"


class AdConfirmationRequest(BaseModel):
    """职责:人工确认或驳回投放建议(HITL)请求载荷"""
    confirm_status: str  # confirmed, rejected
    confirm_remark: str = ""


class AdExperimentUpdateRequest(BaseModel):
    """职责:更新投放实验状态请求载荷"""
    experiment_status: str  # draft, confirmed, running, finished, cancelled
    budget_amount: float | None = None


class PerformanceRecordCreateRequest(BaseModel):
    """职责:录入单周期经营数据请求载荷"""
    period_start: str
    period_end: str
    impressions: int
    clicks: int
    conversions: int
    spend: float
    revenue: float
    experiment_id: int | None = None
    notes: str = ""
