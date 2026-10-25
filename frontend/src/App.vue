<template>
  <div style="min-height: 100vh; background: #f5f7fa">
    <!-- 顶部导航栏 (仅在登录后显示) -->
    <el-header
      v-if="currentUser"
      style="
        background: #0f172a;
        color: #fff;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 24px;
        height: 60px;
      "
    >
      <div style="display: flex; align-items: center; gap: 12px">
        <span style="font-size: 18px; font-weight: 700; letter-spacing: 0.5px">
          电商运营助手 (2.6 单品全链路工作台)
        </span>
        <el-tag type="success" size="small" effect="dark">LangChain + LangGraph + Langfuse</el-tag>
      </div>

      <div style="display: flex; align-items: center; gap: 16px">
        <div style="display: flex; align-items: center; gap: 8px">
          <span style="font-size: 13px; color: #cbd5e1">AI 引擎模式:</span>
          <el-radio-group v-model="aiMode" size="small">
            <el-radio-button value="mock">Mock 极速模式</el-radio-button>
            <el-radio-button value="real">Real (.env 真实大模型)</el-radio-button>
          </el-radio-group>
        </div>
        <el-tag type="warning" size="small">
          {{ currentUser.display_name }} ({{ currentUser.role }})
        </el-tag>
        <el-button size="small" type="primary" plain @click="seedDemoData" :loading="loadingDemo">
          一键重置/加载演示数据
        </el-button>
        <el-button size="small" type="danger" plain @click="handleLogout">退出登录</el-button>
      </div>
    </el-header>

    <!-- 未登录：01_login.pen 像素级极简高端银白色科技风格登录页 -->
    <div v-if="!currentUser" class="login-view-container">
      <!-- 顶部品牌区 (Top Brand Header) -->
      <header class="brand-hero-section">
        <div class="brand-logo-container">
          <div class="brand-icon-box">
            <svg class="brand-logo-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/>
              <path d="M5 3v4"/>
              <path d="M19 17v4"/>
              <path d="M3 5h4"/>
              <path d="M17 19h4"/>
            </svg>
          </div>
          <h1 class="brand-title">电商运营助手</h1>
          <div class="brand-version-badge">企业级 3.0</div>
        </div>
        <p class="brand-slogan">电商运营助手 - 单品全生命周期 AI 运营平台</p>
      </header>

      <!-- 居中核心卡片包装 (Center Login Card Wrapper) -->
      <main class="login-card-wrapper">
        <div class="silver-login-card">
          <!-- 卡片头部标题 -->
          <div class="card-header-block">
            <h2 class="card-title">欢迎登录</h2>
            <p class="card-subtitle">请输入您的运营账户与密码以进入工作台</p>
          </div>

          <!-- 本地快捷角色调试栏 -->
          <div class="role-selector-block">
            <div class="role-selector-label">快捷角色切换 (联调免输密码)</div>
            <div class="role-pill-group">
              <button
                type="button"
                class="role-pill-btn"
                :class="{ active: loginForm.username === 'admin' }"
                @click="switchRole('admin')"
              >
                <span class="role-tag-dot dot-admin"></span>
                <span>admin (管理员)</span>
              </button>
              <button
                type="button"
                class="role-pill-btn"
                :class="{ active: loginForm.username === 'operator' }"
                @click="switchRole('operator')"
              >
                <span class="role-tag-dot dot-operator"></span>
                <span>operator (运营)</span>
              </button>
              <button
                type="button"
                class="role-pill-btn"
                :class="{ active: loginForm.username === 'viewer' }"
                @click="switchRole('viewer')"
              >
                <span class="role-tag-dot dot-viewer"></span>
                <span>viewer (只读查看)</span>
              </button>
            </div>
          </div>

          <!-- 安全认证横幅 (Security Notice Banner) -->
          <div class="security-notice-banner">
            <svg class="shield-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>
              <path d="m9 12 2 2 4-4"/>
            </svg>
            <div class="security-banner-text">
              <span class="security-banner-title">服务端 Session Cookie 认证 (HttpOnly + Lax + Secure)</span>
              <span class="security-banner-desc">防 CSRF/XSS 拦截说明：凭据通过浏览器安全上下文隔离保护</span>
            </div>
          </div>

          <!-- 登录表单主体 -->
          <form class="login-form" @submit.prevent="handleLogin">
            <!-- 账号输入 -->
            <div class="form-field-group">
              <label class="form-field-label">账号 / 手机号 / 邮箱</label>
              <div class="form-input-container">
                <svg class="input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/>
                  <circle cx="12" cy="7" r="4"/>
                </svg>
                <input
                  v-model="loginForm.username"
                  type="text"
                  placeholder="请输入您的账号"
                  class="custom-text-input"
                  autocomplete="username"
                  required
                />
              </div>
            </div>

            <!-- 密码输入 -->
            <div class="form-field-group">
              <label class="form-field-label">登录密码</label>
              <div class="form-input-container">
                <svg class="input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <rect width="18" height="11" x="3" y="11" rx="2" ry="2"/>
                  <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                </svg>
                <input
                  v-model="loginForm.password"
                  :type="showPassword ? 'text' : 'password'"
                  placeholder="请输入密码"
                  class="custom-text-input"
                  autocomplete="current-password"
                  required
                />
                <button
                  type="button"
                  class="password-toggle-btn"
                  @click="showPassword = !showPassword"
                  title="切换显示密码"
                >
                  <svg v-if="!showPassword" class="eye-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/>
                    <circle cx="12" cy="12" r="3"/>
                    <line x1="2" x2="22" y1="2" y2="22"/>
                  </svg>
                  <svg v-else class="eye-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/>
                    <circle cx="12" cy="12" r="3"/>
                  </svg>
                </button>
              </div>
            </div>

            <!-- 记住密码与忘记密码 -->
            <div class="form-options-row">
              <label class="checkbox-label">
                <input v-model="rememberMe" type="checkbox" class="custom-checkbox" />
                <span class="checkbox-text">记住登录状态 (7天免密)</span>
              </label>
              <a href="javascript:void(0)" class="forgot-password-link" @click="handleForgotPassword">
                忘记密码?
              </a>
            </div>

            <!-- 提交按钮 -->
            <button
              type="submit"
              class="primary-submit-btn"
              :disabled="loadingLogin"
            >
              <span v-if="!loadingLogin">立即登录</span>
              <span v-else>正在验证安全凭据...</span>
              <svg v-if="!loadingLogin" class="btn-arrow-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M5 12h14"/>
                <path d="m12 5 7 7-7 7"/>
              </svg>
              <svg v-else class="btn-spinner-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10" stroke-opacity="0.25"/>
                <path d="M12 2a10 10 0 0 1 10 10" stroke-linecap="round"/>
              </svg>
            </button>
          </form>

          <!-- 分隔线 -->
          <div class="divider-section">
            <div class="divider-line"></div>
            <span class="divider-text">企业多因子快捷验证</span>
            <div class="divider-line"></div>
          </div>

          <!-- SSO 与动态口令按钮行 -->
          <div class="sso-buttons-row">
            <button type="button" class="sso-pill-btn" @click="handleSSO('企业 SSO')">
              <svg class="sso-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="7.5" cy="15.5" r="5.5"/>
                <path d="m21 2-9.6 9.6"/>
                <path d="m15.5 7.5 3 3L22 7l-3-3"/>
              </svg>
              <span>企业 SSO 登录</span>
            </button>
            <button type="button" class="sso-pill-btn" @click="handleSSO('动态口令')">
              <svg class="sso-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect width="14" height="20" x="5" y="2" rx="2" ry="2"/>
                <path d="M12 18h.01"/>
              </svg>
              <span>动态口令认证</span>
            </button>
          </div>
        </div>
      </main>

      <!-- 底部版权 (Page Footer) -->
      <footer class="login-footer">
        <div class="footer-meta-row">
          <span class="footer-brand-title">电商运营助手 · 单品全生命周期 AI 运营平台</span>
          <span class="footer-dot"></span>
          <span class="footer-version-tag">V3.0 定稿版</span>
        </div>
        <div class="footer-copyright">
          © 2026 Ecommerce AI Operation Assistant. All Rights Reserved.
        </div>
      </footer>
    </div>

    <!-- 已登录：主工作台 -->
    <div v-else style="padding: 20px 24px; max-width: 1440px; margin: 0 auto">
      <!-- 顶部：店铺与库存监控概览卡片 + 导入模板入口 -->
      <el-row :gutter="16" style="margin-bottom: 18px">
        <el-col :span="16">
          <el-card shadow="never">
            <template #header>
              <div style="display: flex; justify-content: space-between; align-items: center">
                <span style="font-weight: 700">
                  店铺库存监控与 AI 协同建议（本地 5 表只读预计算 + LLM 归因）
                </span>
                <el-button
                  type="primary"
                  size="small"
                  :loading="loadingInvAdvice"
                  @click="generateStoreInventoryAdvice"
                >
                  生成 AI 库存建议 ({{ aiMode.toUpperCase() }})
                </el-button>
              </div>
            </template>

            <div v-if="storeDetail">
              <div style="margin-bottom: 10px; font-size: 14px">
                <strong>当前店铺：</strong>{{ storeDetail.store.store_name }}（{{
                  storeDetail.store.platform
                }}）｜<strong>库存占用资金：</strong>¥{{
                  storeDetail.inventory_overview.total_tied_up_capital
                }}
              </div>
              <el-table
                :data="storeDetail.inventory_overview.sku_metrics"
                size="small"
                border
                style="width: 100%"
              >
                <el-table-column prop="sku_code" label="SKU编码" width="140" />
                <el-table-column prop="sku_name" label="规格名称" />
                <el-table-column prop="available_qty" label="可用库存" width="90" />
                <el-table-column prop="daily_burn_rate" label="日均消耗" width="90" />
                <el-table-column prop="days_of_supply" label="预计可售(DOS)" width="120">
                  <template #default="{ row }">
                    <span :style="{ color: row.days_of_supply < 3 ? '#dc2626' : '#16a34a', fontWeight: 600 }">
                      {{ row.days_of_supply }} 天
                    </span>
                  </template>
                </el-table-column>
                <el-table-column prop="stock_status" label="库存状态" width="110">
                  <template #default="{ row }">
                    <el-tag
                      :type="
                        row.stock_status === 'HEALTHY'
                          ? 'success'
                          : row.stock_status === 'OVERSTOCK'
                            ? 'warning'
                            : 'danger'
                      "
                      size="small"
                    >
                      {{ row.stock_status }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="广告防超卖风险" width="130">
                  <template #default="{ row }">
                    <el-tag v-if="row.ad_oversell_risk" type="danger" size="small" effect="dark">
                      高危：投流超卖风险
                    </el-tag>
                    <el-tag v-else type="info" size="small">正常</el-tag>
                  </template>
                </el-table-column>
              </el-table>

              <!-- AI 库存建议输出框 -->
              <el-alert
                v-if="inventoryAdvice"
                style="margin-top: 12px"
                type="warning"
                :closable="false"
                show-icon
              >
                <template #title>
                  <strong>AI 库存健康总评：</strong>{{ inventoryAdvice.store_health_summary }}
                </template>
                <div style="margin-top: 6px">
                  <div
                    v-for="(item, idx) in inventoryAdvice.restock_recommendations"
                    :key="idx"
                    style="margin-bottom: 4px"
                  >
                    - <strong>[{{ item.priority.toUpperCase() }} 补货]</strong> {{ item.sku_name }} ({{
                      item.sku_code
                    }}): 建议补货 <strong>{{ item.suggested_restock_qty }}</strong> 件 —
                    {{ item.reason }}
                  </div>
                  <div
                    v-for="(act, idx) in inventoryAdvice.operation_synergy_actions"
                    :key="'act-' + idx"
                    style="color: #b91c1c; font-weight: 600"
                  >
                    * {{ act }}
                  </div>
                </div>
              </el-alert>
            </div>
          </el-card>
        </el-col>

        <!-- 右侧：导入中心与标准模板下载 -->
        <el-col :span="8">
          <el-card shadow="never">
            <template #header>
              <span style="font-weight: 700">导入中心 & 模板下载（支持错误行提示与部分导入）</span>
            </template>
            <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px">
              <el-button size="small" @click="downloadTemplate('products')">下载商品模板</el-button>
              <el-button size="small" @click="downloadTemplate('sku-inventory')">
                下载SKU库存模板
              </el-button>
              <el-button size="small" @click="downloadTemplate('performance-records')">
                下载经营数据模板
              </el-button>
            </div>
            <el-input
              v-model="csvImportText"
              type="textarea"
              :rows="4"
              placeholder="粘贴经营数据CSV内容进行批量导入测试"
            />
            <el-button
              type="success"
              size="small"
              style="margin-top: 8px; width: 100%"
              @click="submitCsvImport"
            >
              执行经营数据批量导入（验证部分成功 & 错误行捕获）
            </el-button>
            <div v-if="importResult" style="margin-top: 8px; font-size: 12px">
              成功入库: <strong style="color: #16a34a">{{ importResult.success_count }}</strong> 行 ｜
              失败拦截: <strong style="color: #dc2626">{{ importResult.failed_count }}</strong> 行
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 核心区域：商品详情页 9 大标签页工作台 -->
      <el-card v-if="workbench" shadow="never">
        <template #header>
          <div style="display: flex; justify-content: space-between; align-items: center">
            <div>
              <el-tag type="primary" style="margin-right: 8px">{{
                workbench.product.platform
              }}</el-tag>
              <span style="font-size: 17px; font-weight: 700">{{ workbench.product.name }}</span>
              <span style="margin-left: 16px; color: #dc2626; font-weight: 600">
                售价: ¥{{ workbench.product.price }}
              </span>
              <span style="margin-left: 12px; color: #64748b">
                成本: ¥{{ workbench.product.cost }}
              </span>
            </div>
            <el-tag type="success">单品运营闭环聚合根 ID: {{ workbench.product.id }}</el-tag>
          </div>
        </template>

        <el-tabs v-model="activeTab" type="border-card">
          <!-- Tab 1: 商品&竞品 -->
          <el-tab-pane label="1. 商品 & 竞品" name="tab1">
            <p><strong>核心卖点：</strong>{{ workbench.product.selling_points }}</p>
            <p><strong>目标人群：</strong>{{ workbench.product.target_audience }}</p>
            <el-divider content-position="left">对标竞品列表 (本地只读诊断数据源)</el-divider>
            <el-table :data="workbench.competitors" size="small" border>
              <el-table-column prop="name" label="竞品名称" width="180" />
              <el-table-column prop="platform" label="平台" width="100" />
              <el-table-column prop="price" label="售价(¥)" width="100" />
              <el-table-column prop="sales_hint" label="销量表现" width="120" />
              <el-table-column prop="selling_points" label="竞品卖点" />
              <el-table-column prop="review_keywords" label="差评高频痛点词" />
            </el-table>
          </el-tab-pane>

          <!-- Tab 2: 诊断 -->
          <el-tab-pane label="2. 诊断 (7维结构化)" name="tab2">
            <div style="margin-bottom: 12px; display: flex; justify-content: space-between">
              <span style="color: #475569; font-size: 13px">
                基于本品毛利、竞品差评关键词与上轮复盘报告只读聚合生成，支持人工微调保存。
              </span>
              <el-button
                type="primary"
                size="small"
                :loading="loadingDiag"
                @click="generateDiagnosis"
              >
                AI 生成商品诊断 ({{ aiMode.toUpperCase() }})
              </el-button>
            </div>
            <div v-if="latestDiagnosis">
              <el-form label-width="130px" size="small">
                <el-form-item label="1. 商品定位">
                  <el-input v-model="latestDiagnosis.positioning" type="textarea" :rows="2" />
                </el-form-item>
                <el-form-item label="2. 价格带分析">
                  <el-input v-model="latestDiagnosis.price_band" type="textarea" :rows="2" />
                </el-form-item>
                <el-form-item label="3. 目标人群洞察">
                  <el-input v-model="latestDiagnosis.audience_insights" type="textarea" :rows="2" />
                </el-form-item>
                <el-form-item label="4. 用户痛点">
                  <el-input v-model="latestDiagnosis.pain_points" type="textarea" :rows="2" />
                </el-form-item>
                <el-form-item label="5. 卖点分析">
                  <el-input
                    v-model="latestDiagnosis.selling_point_analysis"
                    type="textarea"
                    :rows="2"
                  />
                </el-form-item>
                <el-form-item label="6. 风险点">
                  <el-input v-model="latestDiagnosis.risks" type="textarea" :rows="2" />
                </el-form-item>
                <el-form-item label="7. 优化建议">
                  <el-input v-model="latestDiagnosis.recommendations" type="textarea" :rows="2" />
                </el-form-item>
                <el-form-item>
                  <el-button type="success" @click="saveDiagnosisEdit">
                    保存人工修改后的诊断
                  </el-button>
                </el-form-item>
              </el-form>
            </div>
          </el-tab-pane>

          <!-- Tab 3: 主图 -->
          <el-tab-pane label="3. 主图方案" name="tab3">
            <div style="margin-bottom: 12px">
              <el-button type="primary" size="small" :loading="loadingImgPlan" @click="generateMainImagePlans">
                AI 生成 3 个主图策划方向 ({{ aiMode.toUpperCase() }})
              </el-button>
            </div>
            <el-table :data="mainImagePlans" size="small" border>
              <el-table-column prop="title" label="方案标题" width="220" />
              <el-table-column label="画面结构 & 核心文案">
                <template #default="{ row }">
                  <div><strong>构图：</strong>{{ row.content_json.visual_structure }}</div>
                  <div><strong>文案：</strong>{{ row.content_json.core_copy }}</div>
                </template>
              </el-table-column>
              <el-table-column prop="rationale_text" label="方案理由" width="240" />
              <el-table-column prop="status" label="状态" width="100" />
              <el-table-column label="异步任务操作" width="180">
                <template #default="{ row }">
                  <el-button size="small" type="success" @click="triggerMediaJob(row.id, 'images')">
                    提交图片生成任务
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <!-- Tab 4: 视频 -->
          <el-tab-pane label="4. 视频脚本" name="tab4">
            <div style="margin-bottom: 12px">
              <el-button type="primary" size="small" :loading="loadingVidPlan" @click="generateVideoScripts">
                AI 生成 3 条短视频脚本 ({{ aiMode.toUpperCase() }})
              </el-button>
            </div>
            <el-table :data="videoScriptPlans" size="small" border>
              <el-table-column prop="title" label="脚本标题" width="200" />
              <el-table-column label="黄金前3秒钩子 & 分镜口播">
                <template #default="{ row }">
                  <div><strong>钩子：</strong>{{ row.content_json.hook }}</div>
                  <div><strong>分镜：</strong>{{ row.content_json.storyboard }}</div>
                  <div><strong>口播：</strong>{{ row.content_json.voiceover }}</div>
                </template>
              </el-table-column>
              <el-table-column label="异步任务操作" width="180">
                <template #default="{ row }">
                  <el-button size="small" type="warning" @click="triggerMediaJob(row.id, 'videos')">
                    提交视频合成任务
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <!-- Tab 5: 任务 -->
          <el-tab-pane label="5. 异步任务队列" name="tab5">
            <div style="margin-bottom: 10px">
              <el-button size="small" @click="loadWorkbench">刷新任务状态</el-button>
            </div>
            <el-table :data="workbench.generation_jobs" size="small" border>
              <el-table-column prop="id" label="任务ID" width="80" />
              <el-table-column prop="job_kind" label="类型" width="90" />
              <el-table-column prop="job_status" label="状态" width="110">
                <template #default="{ row }">
                  <el-tag :type="row.job_status === 'succeeded' ? 'success' : 'warning'" size="small">
                    {{ row.job_status }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="attempts" label="尝试次数" width="90" />
              <el-table-column label="事件时间线 (generation_job_events)">
                <template #default="{ row }">
                  <div v-for="(ev, idx) in row.events" :key="idx" style="font-size: 12px">
                    [{{ ev.event_type }}] {{ ev.event_message }}
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="队列控制" width="160">
                <template #default="{ row }">
                  <el-button size="small" @click="retryJob(row.id)">重试</el-button>
                  <el-button size="small" type="danger" @click="cancelJob(row.id)">取消</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <!-- Tab 6: 素材库 -->
          <el-tab-pane label="6. 素材库" name="tab6">
            <el-table :data="workbench.generated_assets" size="small" border>
              <el-table-column prop="id" label="ID" width="70" />
              <el-table-column prop="asset_type" label="类型" width="80" />
              <el-table-column prop="asset_url" label="素材预览地址" />
              <el-table-column prop="review_status" label="审核状态" width="110" />
              <el-table-column prop="score" label="评分" width="80" />
              <el-table-column label="人工审核操作" width="180">
                <template #default="{ row }">
                  <el-button size="small" type="success" @click="approveAsset(row)">
                    标记审核通过
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <!-- Tab 7: 链接 -->
          <el-tab-pane label="7. 推广短链" name="tab7">
            <div style="margin-bottom: 12px">
              <el-button type="primary" size="small" @click="createShortLink">
                一键生成并创建推广追踪短链
              </el-button>
            </div>
            <el-table :data="workbench.promotion_links" size="small" border>
              <el-table-column prop="link_name" label="推广链接名称" />
              <el-table-column prop="tracking_code" label="短链追踪码" width="140" />
              <el-table-column prop="click_count" label="累计点击数" width="110" />
              <el-table-column label="模拟点击追踪跳转" width="180">
                <template #default="{ row }">
                  <el-button size="small" type="primary" plain @click="simulateLinkClick(row.tracking_code)">
                    访问短链 (+1点击)
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <!-- Tab 8: 投放 (含 HITL 人工确认) -->
          <el-tab-pane label="8. 投放建议 & 实验 (HITL)" name="tab8">
            <div style="margin-bottom: 12px; display: flex; gap: 10px">
              <el-button type="primary" size="small" :loading="loadingAdRec" @click="generateAdRec">
                AI 生成投放策略建议 ({{ aiMode.toUpperCase() }})
              </el-button>
              <el-button type="success" size="small" @click="createAdExperiment">
                生成 A/B 投放实验计划
              </el-button>
            </div>

            <div v-for="rec in workbench.ad_recommendations" :key="rec.id" style="margin-bottom: 16px">
              <el-descriptions :title="'投放建议 #' + rec.id" :column="2" border size="small">
                <el-descriptions-item label="确认状态 (HITL)">
                  <el-tag :type="rec.confirm_status === 'confirmed' ? 'success' : 'warning'">
                    {{ rec.confirm_status }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="本轮目标">{{ rec.objective_text }}</el-descriptions-item>
                <el-descriptions-item label="策略摘要" :span="2">
                  {{ rec.summary_text }}
                </el-descriptions-item>
                <el-descriptions-item label="人工确认操作" :span="2">
                  <el-button size="small" type="success" @click="confirmAdRec(rec.id, 'confirmed')">
                    人工确认批准 (Confirm)
                  </el-button>
                  <el-button size="small" type="danger" @click="confirmAdRec(rec.id, 'rejected')">
                    人工驳回 (Reject)
                  </el-button>
                </el-descriptions-item>
              </el-descriptions>
            </div>
          </el-tab-pane>

          <!-- Tab 9: 复盘 -->
          <el-tab-pane label="9. 经营复盘 & 闭环回流" name="tab9">
            <div style="margin-bottom: 12px; display: flex; justify-content: space-between">
              <el-button type="primary" size="small" :loading="loadingReview" @click="generateReview">
                基于经营数据生成 AI 复盘报告 ({{ aiMode.toUpperCase() }})
              </el-button>
              <el-button type="warning" size="small" @click="activeTab = 'tab2'">
                携带复盘结论回到【2. 诊断】开启下一轮优化闭环 ->
              </el-button>
            </div>

            <el-table :data="workbench.performance_records" size="small" border style="margin-bottom: 16px">
              <el-table-column prop="period_start" label="开始日期" width="110" />
              <el-table-column prop="period_end" label="结束日期" width="110" />
              <el-table-column prop="impressions" label="曝光量" />
              <el-table-column prop="clicks" label="点击量" />
              <el-table-column prop="ctr" label="CTR(%)" />
              <el-table-column prop="conversions" label="转化单数" />
              <el-table-column prop="spend" label="花费(¥)" />
              <el-table-column prop="revenue" label="GMV(¥)" />
              <el-table-column prop="roi" label="ROI" />
            </el-table>

            <el-card v-for="rev in workbench.review_reports" :key="rev.id" shadow="never" style="margin-bottom: 10px">
              <div><strong>周期复盘摘要：</strong>{{ rev.summary_text }}</div>
              <div style="margin-top: 6px">
                <strong>下一步行动建议：</strong>
                <span v-for="(act, i) in rev.next_actions_json" :key="i" style="margin-right: 12px">
                  • {{ act.action }}
                </span>
              </div>
            </el-card>
          </el-tab-pane>
        </el-tabs>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { http } from './api'

const currentUser = ref<any>(null)
const aiMode = ref<'mock' | 'real'>('mock')
const activeTab = ref('tab1')

const loginForm = ref({ username: 'admin', password: '123456' })
const showPassword = ref(false)
const rememberMe = ref(true)

/**
 * 职责: 快捷切换本地联调测试角色并同步账号密码
 */
function switchRole(role: 'admin' | 'operator' | 'viewer'): void {
  loginForm.value.username = role
  loginForm.value.password = '123456'
  ElMessage.info(`已切换至 ${role} 预设账号，密码已就绪 (123456)`)
}

/**
 * 职责: 响应企业多因子快捷入口与 SSO 点击
 */
function handleSSO(type: string): void {
  ElMessage.info(`${type} 认证网关已对接，当前环境请使用标准 Session 认证登录`)
}

/**
 * 职责: 响应忘记密码操作并提供默认演示指引
 */
function handleForgotPassword(): void {
  ElMessage.info('本地演示环境预设用户密码均为 123456。如需重置请联系系统管理员')
}

const loadingLogin = ref(false)
const loadingDemo = ref(false)
const loadingInvAdvice = ref(false)
const loadingDiag = ref(false)
const loadingImgPlan = ref(false)
const loadingVidPlan = ref(false)
const loadingAdRec = ref(false)
const loadingReview = ref(false)

const storeDetail = ref<any>(null)
const inventoryAdvice = ref<any>(null)
const workbench = ref<any>(null)
const currentProductId = ref<number>(1)
const currentStoreId = ref<number>(1)

const csvImportText = ref(
  'period_start,period_end,impressions,clicks,conversions,spend,revenue,notes\n2026-10-25,2026-10-26,15000,630,28,2200.0,9800.0,前端批量导入正常行\n2026-10-25,2026-10-26,-100,10,1,100.0,200.0,异常负数测试行'
)
const importResult = ref<any>(null)

const latestDiagnosis = computed(() => workbench.value?.diagnoses?.[0] || null)
const mainImagePlans = computed(() =>
  (workbench.value?.creative_plans || []).filter((p: any) => p.plan_type === 'main_image')
)
const videoScriptPlans = computed(() =>
  (workbench.value?.creative_plans || []).filter((p: any) => p.plan_type === 'video_script')
)

async function handleLogin() {
  loadingLogin.value = true
  try {
    const res = await http.post('/auth/login', loginForm.value)
    currentUser.value = res.data.user
    ElMessage.success('Session Cookie 登录成功')
    await seedDemoData()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '登录失败')
  } finally {
    loadingLogin.value = false
  }
}

async function handleLogout() {
  await http.post('/auth/logout')
  currentUser.value = null
  workbench.value = null
}

async function seedDemoData() {
  loadingDemo.value = true
  try {
    const res = await http.post('/workspace/demo-data')
    currentStoreId.value = res.data.store_id
    currentProductId.value = res.data.product_id
    await loadWorkbench()
    ElMessage.success(res.data.message)
  } finally {
    loadingDemo.value = false
  }
}

async function loadWorkbench() {
  const [stRes, wbRes] = await Promise.all([
    http.get(`/stores/${currentStoreId.value}`),
    http.get(`/products/${currentProductId.value}`),
  ])
  storeDetail.value = stRes.data
  workbench.value = wbRes.data
}

async function generateStoreInventoryAdvice() {
  loadingInvAdvice.value = true
  try {
    const res = await http.post(
      `/stores/${currentStoreId.value}/inventory-advice/generate?mode=${aiMode.value}`
    )
    inventoryAdvice.value = res.data.ai_advice
    ElMessage.success(`已生成店铺 AI 库存建议 (${aiMode.value.toUpperCase()})`)
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '生成库存建议失败')
  } finally {
    loadingInvAdvice.value = false
  }
}

async function generateDiagnosis() {
  loadingDiag.value = true
  try {
    await http.post(`/products/${currentProductId.value}/diagnoses/generate?mode=${aiMode.value}`)
    await loadWorkbench()
    ElMessage.success(`商品 7 维结构化诊断已生成 (${aiMode.value.toUpperCase()})`)
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '生成诊断失败')
  } finally {
    loadingDiag.value = false
  }
}

async function saveDiagnosisEdit() {
  if (!latestDiagnosis.value) return
  try {
    await http.patch(
      `/products/${currentProductId.value}/diagnoses/${latestDiagnosis.value.id}`,
      latestDiagnosis.value
    )
    ElMessage.success('人工修改已落库保存')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '保存失败')
  }
}

async function generateMainImagePlans() {
  loadingImgPlan.value = true
  try {
    await http.post(
      `/products/${currentProductId.value}/creative-plans/main-images/generate?mode=${aiMode.value}`
    )
    await loadWorkbench()
    ElMessage.success('已生成 3 个主图方案')
  } finally {
    loadingImgPlan.value = false
  }
}

async function generateVideoScripts() {
  loadingVidPlan.value = true
  try {
    await http.post(
      `/products/${currentProductId.value}/creative-plans/video-scripts/generate?mode=${aiMode.value}`
    )
    await loadWorkbench()
    ElMessage.success('已生成 3 条短视频脚本')
  } finally {
    loadingVidPlan.value = false
  }
}

async function triggerMediaJob(planId: number, kind: 'images' | 'videos') {
  await http.post(`/products/${currentProductId.value}/creative-plans/${planId}/${kind}/generate`)
  ElMessage.success('异步生成任务已入队，正在后台执行...')
  activeTab.value = 'tab5'
  setTimeout(() => loadWorkbench(), 900)
}

async function retryJob(jobId: number) {
  await http.post(`/products/${currentProductId.value}/generation-jobs/${jobId}/retry`)
  setTimeout(() => loadWorkbench(), 900)
}

async function cancelJob(jobId: number) {
  await http.post(`/products/${currentProductId.value}/generation-jobs/${jobId}/cancel`)
  await loadWorkbench()
}

async function approveAsset(asset: any) {
  await http.patch(
    `/products/${currentProductId.value}/creative-plans/${asset.creative_plan_id}/assets`,
    { asset_id: asset.id, review_status: 'approved', score: 5 }
  )
  await loadWorkbench()
  ElMessage.success('素材审核已通过')
}

async function createShortLink() {
  const sug = await http.post(`/products/${currentProductId.value}/promotion-links/generate`)
  await http.post(`/products/${currentProductId.value}/promotion-links`, {
    link_name: sug.data.suggested_link_name,
    target_url: sug.data.target_url,
  })
  await loadWorkbench()
  ElMessage.success('推广追踪短链已创建')
}

async function simulateLinkClick(code: string) {
  window.open(`/api/v1/r/${code}`, '_blank')
  setTimeout(() => loadWorkbench(), 500)
}

async function generateAdRec() {
  loadingAdRec.value = true
  try {
    await http.post(
      `/products/${currentProductId.value}/ad-recommendations/generate?mode=${aiMode.value}`
    )
    await loadWorkbench()
    ElMessage.success('已生成投放建议，请执行人工确认 (HITL)')
  } finally {
    loadingAdRec.value = false
  }
}

async function confirmAdRec(recId: number, status: 'confirmed' | 'rejected') {
  try {
    await http.patch(
      `/products/${currentProductId.value}/ad-recommendations/${recId}/confirmation`,
      { confirm_status: status, confirm_remark: `前端工作台人工操作: ${status}` }
    )
    await loadWorkbench()
    ElMessage.success(`投放建议状态已更新为: ${status}`)
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '权限校验未通过')
  }
}

async function createAdExperiment() {
  await http.post(`/products/${currentProductId.value}/ad-experiments/generate`)
  await loadWorkbench()
  ElMessage.success('已生成 A/B 投放实验计划')
}

async function generateReview() {
  loadingReview.value = true
  try {
    await http.post(
      `/products/${currentProductId.value}/review-reports/generate?mode=${aiMode.value}`
    )
    await loadWorkbench()
    ElMessage.success('已生成周期经营复盘报告')
  } finally {
    loadingReview.value = false
  }
}

function downloadTemplate(type: string) {
  window.open(`/api/v1/workspace/templates/${type}`, '_blank')
}

async function submitCsvImport() {
  const blob = new Blob([csvImportText.value], { type: 'text/csv' })
  const formData = new FormData()
  formData.append('file', blob, 'import.csv')
  const res = await http.post(
    `/products/${currentProductId.value}/performance-records/import`,
    formData
  )
  importResult.value = res.data
  await loadWorkbench()
  ElMessage.success('批量导入完成')
}

onMounted(async () => {
  try {
    const me = await http.get('/auth/me')
    currentUser.value = me.data
    await seedDemoData()
  } catch {
    // 尚未登录
  }
})
</script>

<style scoped>
/* 登录页全屏容器：高质感浅灰白科技渐变与柔和微光环境氛围 */
.login-view-container {
  min-height: 100vh;
  background-color: #f8fafc;
  background-image:
    radial-gradient(at 50% 0%, rgba(255, 255, 255, 0.95) 0%, rgba(248, 250, 252, 0.9) 45%, #f1f5f9 100%),
    radial-gradient(circle at 80% 20%, rgba(56, 189, 248, 0.06) 0%, transparent 40%),
    radial-gradient(circle at 20% 80%, rgba(37, 99, 235, 0.05) 0%, transparent 40%);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 32px;
  padding: 40px 24px;
  box-sizing: border-box;
  font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  position: relative;
}

/* 顶部品牌 Hero 区 */
.brand-hero-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.brand-logo-container {
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand-icon-box {
  width: 56px;
  height: 56px;
  background: #0f172a;
  border-radius: 14px;
  border: 1px solid #334155;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.16);
  display: flex;
  justify-content: center;
  align-items: center;
  transition: transform 0.25s ease, box-shadow 0.25s ease;
}

.brand-icon-box:hover {
  transform: translateY(-2px) scale(1.02);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.22);
}

.brand-logo-svg {
  width: 28px;
  height: 28px;
  color: #38bdf8;
}

.brand-title {
  color: #0f172a;
  font-size: 26px;
  font-weight: 700;
  margin: 0;
  letter-spacing: -0.5px;
}

.brand-version-badge {
  background: #edf2f7;
  border-radius: 6px;
  border: 1px solid #cbd5e1;
  padding: 4px 10px;
  color: #475569;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.2px;
}

.brand-slogan {
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
  letter-spacing: 0.5px;
  margin: 0;
}

/* 核心登录卡片 */
.login-card-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
}

.silver-login-card {
  width: 460px;
  background: #ffffff;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  box-shadow:
    0 20px 40px rgba(15, 23, 42, 0.05),
    0 4px 12px rgba(15, 23, 42, 0.03);
  padding: 36px 36px 32px 36px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  box-sizing: border-box;
}

.card-header-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.card-title {
  color: #0f172a;
  font-size: 22px;
  font-weight: 700;
  margin: 0;
}

.card-subtitle {
  color: #64748b;
  font-size: 13px;
  font-weight: normal;
  margin: 0;
}

/* 快捷角色切换 */
.role-selector-block {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 10px 12px;
}

.role-selector-label {
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 8px;
  letter-spacing: 0.3px;
}

.role-pill-group {
  display: flex;
  gap: 8px;
}

.role-pill-btn {
  flex: 1;
  padding: 7px 6px;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
  color: #475569;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.role-pill-btn:hover {
  background: #f1f5f9;
  border-color: #cbd5e1;
  color: #0f172a;
}

.role-pill-btn.active {
  background: #0f172a;
  color: #ffffff;
  border-color: #0f172a;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.16);
}

.role-tag-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-admin {
  background-color: #3b82f6;
}

.dot-operator {
  background-color: #10b981;
}

.dot-viewer {
  background-color: #f59e0b;
}

/* 安全认证横幅 */
.security-notice-banner {
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  padding: 10px 12px;
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.shield-icon {
  width: 17px;
  height: 17px;
  color: #10b981;
  flex-shrink: 0;
  margin-top: 1px;
}

.security-banner-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.security-banner-title {
  color: #334155;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.4;
}

.security-banner-desc {
  color: #64748b;
  font-size: 11px;
  line-height: 1.4;
}

/* 登录表单 */
.login-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-field-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-field-label {
  color: #334155;
  font-size: 13px;
  font-weight: 600;
}

.form-input-container {
  height: 44px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  padding: 0 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  transition: all 0.2s ease;
}

.form-input-container:focus-within {
  background: #ffffff;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.input-icon {
  width: 18px;
  height: 18px;
  color: #94a3b8;
  flex-shrink: 0;
}

.custom-text-input {
  flex: 1;
  height: 100%;
  border: none;
  background: transparent;
  outline: none;
  color: #1e293b;
  font-size: 14px;
  padding: 0;
}

.custom-text-input::placeholder {
  color: #94a3b8;
}

.password-toggle-btn {
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  transition: color 0.15s ease;
}

.password-toggle-btn:hover {
  color: #475569;
}

.eye-icon {
  width: 18px;
  height: 18px;
}

/* 选项行 */
.form-options-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}

.custom-checkbox {
  width: 16px;
  height: 16px;
  accent-color: #2563eb;
  cursor: pointer;
  border-radius: 4px;
}

.checkbox-text {
  color: #475569;
  font-size: 13px;
  font-weight: normal;
}

.forgot-password-link {
  color: #2563eb;
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
  transition: color 0.15s ease;
}

.forgot-password-link:hover {
  color: #1d4ed8;
  text-decoration: underline;
}

/* 主提交按钮 */
.primary-submit-btn {
  height: 46px;
  background: #0f172a;
  border-radius: 8px;
  border: 1px solid #1e293b;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.18);
  color: #ffffff;
  font-size: 15px;
  font-weight: 600;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.primary-submit-btn:hover:not(:disabled) {
  background: #1e293b;
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.24);
}

.primary-submit-btn:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.16);
}

.primary-submit-btn:disabled {
  opacity: 0.75;
  cursor: not-allowed;
}

.btn-arrow-icon {
  width: 16px;
  height: 16px;
  color: #ffffff;
}

.btn-spinner-icon {
  width: 16px;
  height: 16px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* 分隔线 */
.divider-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.divider-line {
  flex: 1;
  height: 1px;
  background: #e2e8f0;
}

.divider-text {
  color: #94a3b8;
  font-size: 12px;
  font-weight: normal;
  white-space: nowrap;
}

/* SSO 按钮 */
.sso-buttons-row {
  display: flex;
  gap: 12px;
}

.sso-pill-btn {
  flex: 1;
  height: 38px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: #334155;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.sso-pill-btn:hover {
  background: #f1f5f9;
  border-color: #cbd5e1;
  color: #0f172a;
}

.sso-icon {
  width: 15px;
  height: 15px;
  color: #475569;
}

/* 底部 Footer */
.login-footer {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.footer-meta-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.footer-brand-title {
  color: #64748b;
  font-size: 13px;
  font-weight: 500;
}

.footer-dot {
  width: 4px;
  height: 4px;
  background: #cbd5e1;
  border-radius: 2px;
}

.footer-version-tag {
  background: #e2e8f0;
  border-radius: 4px;
  border: 1px solid #cbd5e1;
  padding: 3px 8px;
  color: #334155;
  font-size: 11px;
  font-weight: 600;
}

.footer-copyright {
  color: #94a3b8;
  font-size: 12px;
  font-weight: normal;
}
</style>
