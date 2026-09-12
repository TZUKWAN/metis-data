# Engineering Progress — Metis Data Productization

## Current Phase
全部 Phase 完成 — 全量验证通过，待 CI 确认

## Current Task
无

## Completed

### Task P15-001..006（Browser Search Worker，agent A）
Status: PASS
Files: metis/backend/app/search/browser_worker.py、metis/backend/app/auth/recipes.py（BROWSER_SEARCH_RECIPES）、metis/backend/tests/test_p15_browser_search.py
Tests: `python -m pytest metis/backend/tests/test_p15_browser_search.py metis/backend/tests/test_p02_browser.py -q` — 9 passed
Acceptance: [x] search/extract/next_page/open_result/extract_metadata 合同 [x] 动态页 [x] login-aware（WAITING_USER → USER_INTERVENTION_REQUIRED）[x] 归一化 [x] 事件证据

### Task P24-001 + P25-001..006（agent B）
Status: PASS
Files: db/models.py（ProjectRow/TaskRow）、db/repository.py（7 方法）、api/main.py（5 端点 + /api/agent/chat + requires_confirmation）、frontend（Project/Agent Chat 面板）、tests/test_p24_p25.py
Tests: `python -m pytest metis/backend/tests/test_p24_p25.py metis/backend/tests/test_p00_productization.py -q` — 7 passed；node --check js OK
Acceptance: [x] 项目/任务模型 [x] chat 基于真实状态回答进度/推荐/合成 [x] 高风险操作确认门

### Task P08-002（Provider Verification Record，agent C）
Status: PASS（证据产物）
Files: metis/artifacts/providers/<22 provider>/verification.json + summary.json（只写产物，未改代码）
结果（真实网络）：search 19 PASS / 3 FAIL（eurostat、osf 为 60s 探测超时——此前多次通过，属瞬时；nbs_china 403）；download 8 PASS / 9 FAIL / 5 BLOCKED（均如实记录）
暴露并修复的真实 bug：us_census acquire 误用 r.status（httpx 应为 r.status_code）；ilostat 37.7MB payload 超 32MB cap → 改走 download_to_file 流式（common.py 新增）
Tests: secrets scan 0 findings
Acceptance: [x] 每 provider 有 verification.json（含 blocker）[x] 不虚报

### 集成与全量验证（主 agent）
- 全量 pytest：93 tests，0 failed（test_crash_recovery 单次 kill 时序 flake，重跑通过）
- ruff 0.16：All checks passed；secrets scan 0；node --check js OK
- GS-1+GS-5+GS-6：PASS（WB+Eurostat 双组织 3 源 566 行面板，reproduce PASS）
- GS-3：PASS（Zenodo DOI 获取）；GS-4：PASS（登录→持久化→恢复→探测→真实下载）
- CI 修复：unit-integration 增加 gen_fixtures 步骤 + timeout 30min + 修 pip 行

### Task P06-001..005 + P07-001..014
Status: PASS
Files Changed: metis/backend/app/providers/{download_helper,base}.py、adapters/*.py（有界写入重构）、metis/backend/app/providers/download_helper.py、tests/test_p06_p07_download.py
Implementation:
- P06-001 AcquisitionDescriptor（url/method/headers/filename/expected_type/expected_size/auth_context/license/metadata）
- P06-002 v2 接口 build_acquisition_descriptor/validate_download（默认桥接 legacy metadata→descriptor）
- P06-003 兼容层：legacy acquire_dataset 保留，v2 默认实现包装
- P06-004/005 静态扫描测试：adapter 禁触 raw/、禁无界 write_bytes（统一 32MB 上限 write_small_payload；大文件必须 DownloadManager）
- P07-001/002/004/005/006/007/010 已有流式/chunk/partial/原子提交/SHA256/嗅探/取消（Phase 11 遗产）
- P07-003 进度含 percent/speed/eta
- P07-008 期望大小校验（声明+实际 vs descriptor.expected_size，不符 CHECKSUM_MISMATCH）
- P07-009 Range 断点续传（.partial + Accept-Ranges，服务器忽略 Range 则重下）
- P07-011 browser download 已统一 verify/commit；P07-012 多文件 job.files 列表；P07-013 防护保留
- P07-014 1GB 合成流测试：2.2s 完成，sha256 校验，流式 1MB chunk 内存有界
Tests: `python -m pytest metis/backend/tests/test_p06_p07_download.py` — 4 passed
Acceptance:
- [x] Adapter 不直接写 Raw（静态扫描）
- [x] 下载路径无 response.content 整读（静态扫描 + 有界 helper）
- [x] Range 续传 + 进度 + 期望大小
- [x] 1GB RSS 有界


### Task P05-001..012（Account Center + APIs）
Status: PASS（UI + API + 测试）
Files Changed: metis/backend/app/api/main.py（login/register API + MetisError 全局 handler + 202 access 流）、metis/backend/app/auth/{accounts,recipes}.py（多凭据有界登录、recipe 驱动、P05-012 重试上限 3 次）、metis/frontend/static/{index.html,app.js}（Account Center 面板）、metis/backend/tests/test_p05_accounts.py
Implementation:
- P05-001 Account Center 面板：Provider 选择/账号状态/auto-register 开关/绑定/登录/删除
- P05-002 绑定已有账号（密码不回显，入 Vault）
- P05-003 POST /api/accounts/{provider}/login：recipe 驱动真实浏览器登录 + storage_state 保存 + P04-010 恢复挂起 AccessJob
- P05-004 recipes.py：fixture_site + kaggle 定位器/成功失败检测/password policy
- P05-005/006 POST /api/accounts/{provider}/register：RegistrationExecutor + recipe 字段映射
- P05-007 password_policy per provider（recipe 覆盖默认 16 位强密码）
- P05-008/009 Data Identity + 字段禁用（既有 IdentityService）
- P05-010 协议/实名/CAPTCHA → WAITING_USER（注册分类已有）
- P05-011 VERIFY_EMAIL_REQUIRED 不标 FULLY_ACTIVE（已有，回归验证）
- P05-012 同 Provider 注册尝试 ≥3 次 → REGISTRATION_BLOCKED
Tests: `python -m pytest metis/backend/tests/test_p05_accounts.py` — 3 passed；login E2E（P08）1 passed
Evidence: tests/test_p05_accounts.py
Acceptance:
- [x] 登录/注册 API 前端可调（Account Center 按钮）
- [x] 敏感信息不回显
- [x] 重试上限
- [x] MetisError 全局 → 4xx JSON（原 500 修复）

### 附带修复
- 全量回归 88 tests 0 failed；测试强制 headless（用户桌面不再弹窗，commit 935616c）


### Task P04-001..012
Status: PASS
Goal: Access State Machine 与下载主链路闭环
Files Changed: metis/backend/app/access/{machine,executor,__init__}.py、metis/backend/app/db/{models,repository}.py（access_jobs 表）、metis/backend/app/api/main.py（/api/downloads 接入）、metis/backend/tests/test_p04_access.py
Implementation:
- P04-001/002 AccessJob 模型 + 21 态 AccessState（含 WAITING_CAPTCHA/MFA/AGREEMENT/USER）
- P04-003 FLOW 转换守卫（非法跳转 STATE_INVALID）
- P04-004 inspect_access_requirements 归一化 public/login_required/registration_possible/agreement/restricted/paid/unknown
- P04-005 公共分支 → AUTHORIZED；UNKNOWN 模式允许匿名尝试（失败在 acquire 暴露，不静默）
- P04-006 真实 session 探测（复用 Phase 3 ensure_valid_session）
- P04-007 有存储账号 → LOGIN_REQUIRED/LOGGING_IN（Account Center API 驱动，P04-010 resume 继续）
- P04-008 自动注册仅用户开启才进 REGISTER_REQUIRED
- P04-009 CAPTCHA/MFA/协议 → WAITING_* → WAITING_USER
- P04-010 resume_after_user(success/captcha/mfa/agreement/failure)
- P04-011 失败码复用 ERROR_CODES（INVALID_CREDENTIALS/SESSION_EXPIRED/USER_INTERVENTION_REQUIRED 等）
- P04-012 POST /api/downloads 不再直接 acquire：Download Request → AccessJob → Authorized → Acquisition；未授权返回 202 + access job 状态
Tests: `python -m pytest metis/backend/tests/test_p04_access.py` — 7 passed（public/无账号等待/账号登录派发/会话有效授权/非法转换/恢复/不存在 job 报错）
Evidence: tests/test_p04_access.py；access_jobs 表持久化 history
Acceptance:
- [x] 状态机与下载闭环
- [x] 每次 transition 持久化 + event + reason + timestamp
- [x] 下载主链路经 AccessJob


### Task P03-001..010
Status: PASS
Goal: 真实 Session / Vault（替换占位字符串 session）
Files Changed: metis/backend/app/auth/{secret_store,vault,browser_state,recipes,accounts}.py、metis/backend/tests/fixtures/pages/{login,login_success}.html、metis/backend/tests/test_p03_session.py
Implementation:
- P03-001 SecretStore ABC（set/get/delete/exists/list_keys）；get_secret_store() 平台路由
- P03-002 保留 DPAPI 实现；调用改走平台符号（64 位安全原型仅 Windows 声明）
- P03-003 非 Windows import 安全；调用时 VAULT_UNAVAILABLE（无明文 fallback）
- P03-004 BrowserStateRecord schema（provider/account/created/verified/expires/vault_key）
- P03-005 登录成功后 context.storage_state() 序列化入 Vault（LoginExecutor 集成，storage_state_saved 返回）
- P03-006 restore_browser_storage：新 Context 注入 cookies + localStorage init scripts
- P03-007 probe_session_valid：按 recipe logged_in/logged_out selector 真实探测，不信任 DB status
- P03-008 失效 → SESSION_EXPIRED（DB session+account 同步标记）
- P03-009 OAuthCredential（access/refresh/expires/scope）Vault 存取
- P03-010 delete_browser_state + 账户删除联动（REVOKED）
Tests: `python -m pytest metis/backend/tests/test_p03_session.py` — 4 passed
  （含真实 E2E：登录→真实 storage_state 保存→关闭浏览器→新 session 恢复→probe 仍登录；无登录态探测→SESSION_EXPIRED）
Evidence: tests/test_p03_session.py；recipes.py（fixture_site + kaggle 真实定位器）
Acceptance:
- [x] Vault 存真实 state（含 metis_logged_in localStorage 标记），非占位字符串
- [x] 登录→保存→重启→恢复→仍登录（本地 fixture）
- [x] 探测不只信 DB status
- [x] 过期进 SESSION_EXPIRED
- [x] 删除后需重新认证


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
