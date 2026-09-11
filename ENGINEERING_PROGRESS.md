# Engineering Progress — Metis Data Productization

## Current Phase
Phase 3（真实 Session / Vault）

## Current Task
P03-004 storage_state schema

## Completed

### Task P02-002..014（P02-001/009 已在 Phase 0 完成）
Status: PASS
Goal: Browser 从截图轮询升级为可观察 Computer Use
Files Changed: metis/backend/app/browser/runtime.py、metis/backend/app/api/main.py、metis/frontend/static/{index.html,app.js}、metis/backend/tests/test_p02_browser.py
Implementation:
- P02-002 WS 直播流 `/ws/browser/{id}`：JPEG 帧目标 15FPS + cursor/click/typing 元数据
- P02-003 背压：发送耗时超帧预算自动降频，无无界队列
- P02-004/006 光标轨迹 + 点击环（canvas overlay，前端绘制）
- P02-005 语义定位→元素盒→插值移动→可视点击（默认路径，不再瞬移）
- P02-007/008 真实 keyboard.type(delay=30) 默认逐字可见；secret 用 fill 且不显示明文
- P02-010 Tab 模型 API（index/title/url/active）+ 幂等页面跟踪（popup 事件与手动 new_tab 竞态去重）
- P02-011/012 Takeover/Return 已有（fixture E2E 覆盖）
- P02-013 check_crashed()：连接断开标记 CRASHED，WS 推送 crashed 事件，不假装 IDLE
- P02-014 sanitize_url：事件/UI 层 URL 敏感 query 参数掩码
Tests: `python -m pytest metis/backend/tests/test_p02_browser.py metis/backend/tests/test_p08_browser_e2e.py` — 16 passed
Evidence: tests/test_p02_browser.py（帧率≥8fps 断言、JPEG magic、光标位移、typed_by=keyboard、CRASHED、URL 掩码）
Acceptance:
- [x] 连续观看无 2.5s 跳帧（15FPS WS 流替代轮询）
- [x] 鼠标/键盘/点击可视
- [x] Tab 切换真实
- [x] Takeover/Return 同 session
- [x] 崩溃标 CRASHED
- [x] 敏感信息不泄露（typed secret + URL query）


### Task P01-001..011
Status: PASS
Goal: LLM Data Agent Core（模型规划 + 确定性守卫 + 规则兜底）
Files Changed: metis/backend/app/agent/{__init__,client,schemas,policy,requirement_planner,measurement_planner,source_planner,search_planner,candidate_analyzer,build_planner,critic}.py；metis/backend/app/api/main.py（3 个 agent API）；.env.example
Implementation:
- LLMClient：OpenAI-compatible（env 配置），CONFIG_MISSING 明确报错，429/timeout/5xx 指数退避重试，401/403 AUTH_ERROR 分类，API key 注册全局脱敏（adapter 级 + handler 级双重）
- 严格 Pydantic schema（extra=forbid）：DataRequirementPlan/VariableConcept/VariableMeasurementPlan/SourcePlan/SearchQueryPlan/CandidateAnalysis/BuildPlan/ReviewPoint/CriticReview——非法输出不能进下游
- RequirementPlanner：LLM 主路径 + 规则 fallback + 规则校验器；词典外需求（中国城市科技创新/土地财政依赖/环境规制/产业升级）经 LLM 识别 ≥4 概念
- MeasurementPlanner：LLM 主路径 + 确定性概念字典兜底（digital_economy/innovation/aging/environmental_regulation/fiscal_pressure/industrial_upgrading），未识别概念标记 unresolved 不冒充
- SourcePlanner：LLM 主路径 + 规则基线；policy 硬约束（官方需求社区平台不得领先、中国地理建议中国官方源）
- SearchQueryPlanner：中英双语 + 指标代码提示（SL.UEM.1524.ZS 等）
- Critic：确定性冲突检查（时间倒置/无变量/单 Provider/m:m join/未知聚合）+ LLM 第二轮概念评审
- API：POST /api/agent/{requirements,measurements,sources}/plan
Tests: `python -m pytest metis/backend/tests/test_p01_agent.py -q` — 14 passed（stub OpenAI-compatible server 验证客户端重试/分类/schema 拒收/fallback；真实 LLM 需用户 env，未伪造）
Evidence: tests/test_p01_agent.py；.env.example LLM 配置段
Acceptance:
- [x] P01-002 未配置明确报错；key 不写日志
- [x] P01-003 429/timeout/5xx 测试通过
- [x] P01-004 非法输出不能进下游（extra=forbid + 校验器）
- [x] P01-005 词典外需求识别 ≥4 概念（stub LLM 管道验证）
- [x] P01-006 规则 fallback 保留
- [x] P01-007 每概念输出 preferred/alternatives/proxies/unit/aggregation/confidence
- [x] P01-008 中国省级财政不推荐 Kaggle
- [x] P01-009 双语 query + indicator hints
- [x] P01-010 critic 指出矛盾
- [x] P01-011 三个 API 前端可调

### Task P01-012
Status: PASS
Goal: 前端 Requirement Review
Files Changed: metis/frontend/static/{index.html,app.js}
Implementation: Agent 深度解析按钮 → plan 卡（研究单位/频率/时间/地理/变量可编辑、假设/待确认展示）→ 重新计算搜索计划（调 sources/plan，展示 Provider 优先级/查询/代码提示/policy 警告）
Tests: 全套 agent 测试回归 16 passed（含 P00）
Evidence: UI 组件代码；测试
Acceptance: [x] 显示全部要素 [x] 可编辑 [x] 修改后搜索计划重算


### Task P00-001
Status: PASS
Goal: 记录当前 commit 基线
Files Changed: metis/artifacts/productization/baseline.json
Implementation: branch/commit/dirty/os/python/node/playwright/timestamp
Tests: `git rev-parse HEAD` → a45a14f…
Evidence: metis/artifacts/productization/baseline.json
Acceptance: [x] JSON 含全部必需字段 [x] 对应当前代码

### Task P00-002
Status: PASS
Goal: 重新运行现有全部 pytest
Files Changed: metis/artifacts/productization/baseline_tests.txt
Implementation: `python -m pytest metis/backend/tests --tb=no -q`
Tests: 55 passed, 0 failed, 0 skipped（Playwright loop 关闭噪声为 teardown 伪异常，不影响结果）
Evidence: baseline_tests.txt
Acceptance: [x] 真实命令输出已保存

### Task P00-003
Status: PASS
Goal: 能力真实性矩阵（区分 implemented/unit/fixture/real/ui/production_ready）
Files Changed: metis/artifacts/productization/capability_reality_matrix.json
Implementation: 12 项能力诚实分级；Session/Registration/Auth/UI/Build/Provider/Browser production_ready=false 并注明缺口
Evidence: capability_reality_matrix.json
Acceptance: [x] 覆盖 12 项必需能力 [x] 不再用单一 PASS/FAIL 掩盖成熟度差异

### Task P00-004
Status: PASS
Goal: 修复 Browser Session 创建 API schema bug
Files Changed: metis/backend/app/api/main.py（BrowserCreateSessionRequest 拆分，即 P02-001 同步完成）、metis/backend/app/browser/runtime.py（bind_task，即 P02-009 基础）、metis/frontend/static/app.js（去除重复/错误调用）
Implementation: create 不再要求 session_id；action 请求用 BrowserActionRequest
Tests: `python -m pytest metis/backend/tests/test_p00_productization.py` — 2 passed（前端真实调用体 {task_label} → 200 + session 创建 + task_binding）
Evidence: test_p00_productization.py
Acceptance: [x] 真实前端点击"新会话"返回 200 [x] 不依赖手工修改请求

## Files Changed
- metis/artifacts/productization/{baseline.json,baseline_tests.txt,capability_reality_matrix.json}
- metis/backend/app/api/main.py, metis/backend/app/browser/runtime.py, metis/frontend/static/app.js
- metis/backend/tests/test_p00_productization.py

## Tests Executed
- `python -m pytest metis/backend/tests/test_p01_agent.py -q` — 14 passed
- `python -m pytest metis/backend/tests/test_p00_productization.py -q` — 2 passed
- `python -m pytest metis/backend/tests --tb=no -q` → 55 passed（baseline）
- `python -m pytest metis/backend/tests/test_p00_productization.py -q` → 2 passed

## Evidence
- metis/artifacts/productization/*

## Blockers
- 无

## Next Task
P01-001 agent 模块目录
