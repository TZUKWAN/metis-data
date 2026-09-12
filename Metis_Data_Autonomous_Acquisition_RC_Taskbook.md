# Metis Data 1.0 RC 最终收口 + 自主数据采集能力工程任务书

> 目标仓库：`https://github.com/TZUKWAN/metis-data`  
> 编制日期：2026-09-13  
> 审计基线：`d956c2de5756611469a5911589cbbc3965470530`（执行时如 HEAD 已变化，先重新建立基线）  
> 用途：直接交给能力有限的 Coding Agent，严格按 Task ID 顺序执行。  
> 最终目标：**Metis Data 不是“装了一堆爬虫”，而是一套统一、可观察、可授权、可恢复、可追溯、可复现的数据发现与自主采集系统。**

---

# 0. 给 Coding Agent 的总提示词

你现在负责继续推进 `TZUKWAN/metis-data`。不要重新设计整个产品，也不要推倒现有 Provider、Browser、Access、Download、Build 和 Provenance 系统。

本轮有两个不可分割的目标。

第一，修完当前 RC 剩余的真实主链缺口：

1. 后端 PlanningBundle 已经接入 SearchRun，但默认前端普通“搜索”按钮仍可能直接使用 `requirement_id` 进入旧 deterministic Search；必须让普通用户默认走 `PlanningBundle → planning_id → SearchRun`。
2. `BrowserAuthBridge` 已存在，`AcquisitionService` 也支持 cookies/headers，但 `AccessResumeCoordinator` 当前仍把 `access_context` 置空；必须将真实浏览器登录态或 Vault auth ref 接入下载。
3. `BrowserSearchWorker` 已进入 SearchOrchestrator，但必须明确 session ownership/close，防止长期搜索留下孤儿 Chromium/tab。
4. 当前 Engineering Delivery Acceptance 是历史多轮追加文本，仍含旧 FAIL/PARTIAL 与新 PASS 混杂；必须重新生成只针对最终 commit 的验收报告。

第二，把网页、社媒、公众号、论文、资讯等“自主获取数据”能力融入现有 Metis Data。

不要把 Agent-Reach、OpenCLI、bb-browser、MediaCrawler 等项目直接复制进仓库。建立统一 **Autonomous Acquisition Fabric**：

```text
User Research/Data Need
→ PlanningBundle
→ Acquisition Planner
→ AcquisitionRouter
→ [Official Provider / Direct HTTP / Reader / Browser / Site Adapter / Social / Paper / External Crawl API]
→ Raw Artifact
→ Normalized Artifact / Dataset
→ Validation
→ Provenance
→ Build / Export
```

第三方工具只能作为可替换 Backend/Bridge。上层 Agent 永远只使用 Metis 的统一工具和 schema。

## 强制安全边界

- 不实现 CAPTCHA/MFA/SMS/Email OTP 绕过。
- 不实现 stealth、指纹伪造、住宅代理轮换、验证码打码、风控对抗作为产品能力。
- 允许使用用户明确授权且已经登录的浏览器会话读取用户请求的数据。
- 遇 CAPTCHA / MFA / 实名 / 机构认证 / Restricted Agreement / Payment 时进入 `WAITING_USER`。
- 不自动替用户接受额外法律义务。
- 不抓私信、通讯录等用户未请求数据。
- 所有 CrawlPlan 必须有 page/depth/duration/bytes/domain 边界。
- 通用网页爬取默认尊重 robots.txt 与站点政策。
- Raw 永远不可变。
- 网页/社媒/论文结果必须保留 URL、时间、Backend、原始记录引用。
- 页面文本全部标为 `UntrustedContent`，绝不允许页面文字直接变成工具命令。
- 第三方 CLI 禁止 `shell=True`；只允许 argv allowlist。
- Cookie、Token、API Key、Storage State 只进 Vault 或短生命周期内存。
- MediaCrawler 当前为 `NON-COMMERCIAL LEARNING LICENSE 1.1`，生产代码不得 vendor/import/依赖它；只能作为架构参考，除非未来取得适合生产用途的明确许可。

## 上游能力归类

| 项目/服务 | 吸收能力 | 集成方式 | 定位 |
|---|---|---|---|
| Agent-Reach | 多平台路由、doctor、社媒读取 | Optional CLI Bridge | 可选后端 |
| Agent-Paper-Digest | 论文追踪、分级、定时 Digest | 吸收工作流 | 内建 Paper Watch |
| OpenCLI | 网站 CLI adapter、用户登录 Chrome | Optional CLI/Browser Bridge | 可选后端 |
| bb-browser | 真实 Chrome、JSON、accessibility snapshot | 安全受限 Bridge | 可选后端 |
| web-access (`eze-is/web-access`) | WebSearch/WebFetch/Jina/CDP 策略、站点经验、目标就绪、tab 生命周期 | 吸收设计 | 设计基线 |
| wechat_articles_spider | 公众号名称、历史文章、关键词筛选 | 独立重写 WeChat Adapter | 小规模研究 |
| Jina Reader | 公开网页 → Markdown | External Reader Backend | 可选后端 |
| 6551 opennews/opentwitter | 资讯/X 结构化 API | External API Backend | 可选后端 |
| MediaCrawler | 国内自媒体架构参考 | REFERENCE_ONLY | 不进生产依赖 |
| XCrawl | scrape/map/crawl/SERP | External Crawl Backend | 可选后端 |
| Obsidian Web Clipper | 模板化捕获、metadata、Markdown | 吸收模板思想 | Clip + Export |

## 每个任务执行循环

```text
READ TASK
→ CHECK DEPENDENCY
→ INSPECT EXISTING CODE
→ IMPLEMENT
→ WRITE/UPDATE TEST
→ RUN TEST
→ FIX UNTIL PASS
→ SAVE EVIDENCE
→ UPDATE ENGINEERING_PROGRESS.md
→ NEXT TASK
```

`ENGINEERING_PROGRESS.md` 每项使用：

```markdown
## Task Pxx-xxx
Status: PASS | FAIL | BLOCKED
Commit:
Files Changed:
Implementation:
Tests:
Evidence:
Acceptance:
Remaining:
```

不得使用“基本完成”“大致可用”“主体完成”。

---

# P00 · 基线、Reality Audit 与工程门禁

**阶段目标：** 固定当前基线，重新确认主链现实状态，建立本轮不可绕过的工程验收门禁。

## P00-001 · 记录仓库与 CI 基线

**目标：** 所有后续结果可追溯到确切源码。

**前置依赖：** 无

**实施动作：**
1. 确认 main HEAD；预期 d956c2d，若已变化则记录真实 HEAD 并 compare。
2. 记录 Git status、Python、Node、Playwright/Chromium、OS、DB 版本。
3. 记录最近 CI run 及每个 job 结果，而不是只记录徽章。
4. 写 `metis/artifacts/rc-final/baseline.json`。

**必须产物：**
- baseline.json

**验收标准：**
- [ ] 含 commit/branch/dirty/runtime/ci_run/jobs/timestamp
- [ ] 可从 JSON 复现当前基线

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P00-002 · 重新运行完整测试

**目标：** 不依赖历史 PASS 文档。

**前置依赖：** 无

**实施动作：**
1. 运行 ruff、unit/integration、security、frontend smoke、可本机执行的 performance。
2. 保存命令、退出码、pass/fail/skip/duration。
3. 不得为通过基线而先改测试。

**必须产物：**
- baseline-test-report.md
- raw logs

**验收标准：**
- [ ] 所有失败完整列出
- [ ] 报告和真实命令输出一致

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P00-003 · 建立 RC Reality Matrix

**目标：** 严格区分代码存在、已接线、fixture、真实 E2E、生产可用。

**前置依赖：** 无

**实施动作：**
1. 覆盖 Planning→Search、Browser Search、Access/Auth、Acquisition、Build、Provider、Crawler、UI。
2. 每项列 IMPLEMENTED / CONNECTED / TESTED_FIXTURE / TESTED_REAL / PRODUCTION_READY。
3. 重点确认默认 UI 是否发 planning_id、Resume 是否传 auth context、BrowserSearch 是否回收 session。

**必须产物：**
- docs/rc-reality-matrix.md

**验收标准：**
- [ ] 每个结论给源码和测试证据
- [ ] 禁止单一 PASS 掩盖成熟度差异

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P00-004 · 建立架构不变量测试清单

**目标：** 防止修一处又出现旁路。

**前置依赖：** 无

**实施动作：**
1. 规划自动检测：默认 UI Search 必须走 PlanningBundle；生产下载走 AcquisitionService；Browser auth 必须进入 AcquisitionContext；Build 不硬编码 country/year；Adapter 不直接写 raw；页面内容不得变控制指令。

**必须产物：**
- tests/architecture/README.md

**验收标准：**
- [ ] 每条不变量都有后续可自动化检测方法

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P01 · 默认 PlanningBundle → Search 主链

**阶段目标：** LLM Requirement→Measurement→Source→Query 成为普通用户默认路径。

## P01-001 · 前端增加 planning 状态

**目标：** 前端持久追踪当前 PlanningBundle。

**前置依赖：** P00

**实施动作：**
1. STATE 新增 planningId/planningBundle/planningSource。
2. 新任务时清理旧 planning。
3. 不得只把 planning 结果存在 DOM。

**必须产物：**
- 前端状态修改

**验收标准：**
- [ ] planning_id 可供 Search 读取
- [ ] 跨任务不串 planning

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P01-002 · 统一 Planning API

**目标：** 普通入口一次构建完整 PlanningBundle。

**前置依赖：** P01-001

**实施动作：**
1. 确认或新增 `POST /api/agent/planning`，内部调用 build_planning_bundle + save_bundle。
2. 返回 planning_id、requirement、measurements、source_plan、query_plans、planning_source、review_points。
3. 旧 requirement-only planner 只保留兼容。

**必须产物：**
- Planning API

**验收标准：**
- [ ] 一次输入得到持久化 bundle
- [ ] planning_source=llm|mixed|fallback

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P01-003 · Planning Review UI

**目标：** 用户能审查研究单位、变量和数据源策略。

**前置依赖：** P01-002

**实施动作：**
1. 展示 unit/geography/time/frequency/concepts/measurement/proxy/provider priorities/assumptions/review points。
2. 修改关键字段后生成新的 revision/planning_id，不能无记录覆盖。
3. 保存 revision history。

**必须产物：**
- Planning Review UI

**验收标准：**
- [ ] 修改时间后 query plan 会变化
- [ ] 历史可审计

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P01-004 · 默认 Search 改用 planning_id

**目标：** 关闭普通 UI 的旧 rule-only 旁路。

**前置依赖：** P01-003

**实施动作：**
1. btn-search 若有 planningId，POST `/api/search/runs` 传 planning_id。
2. 如果没有 planning，先自动 Planning，不直接调用 requirement_id-only 路径。
3. requirement_id-only 保留为明确 fallback/兼容 API。

**必须产物：**
- Search handler

**验收标准：**
- [ ] 浏览器 Network 证明普通搜索请求含 planning_id
- [ ] SearchRun query_plan 来自 bundle

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P01-005 · Planning 主链架构测试

**目标：** 以后不能无意回退。

**前置依赖：** P01-004

**实施动作：**
1. 静态前端测试禁止默认 Search 只传 requirement_id。
2. 后端 integration：planning_id 必须驱动 provider priorities/query plans。
3. 用词典外需求‘中国城市科技创新、土地财政依赖、环境规制、产业升级’验证。

**必须产物：**
- architecture/integration tests

**验收标准：**
- [ ] 非词典需求可真正启动 SearchRun
- [ ] CI 能阻止旁路回归

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P02 · BrowserAuthBridge → Acquisition 真正接线

**阶段目标：** 登录态从 Browser/Vault 真正进入自动续下载。

## P02-001 · 正式 AuthorizedAccessContext schema

**目标：** 统一授权上下文。

**前置依赖：** P00

**实施动作：**
1. 字段至少 provider_id/auth_type/browser_session_id/account_id/cookie_ref/token_ref/api_key_ref/headers_ref/transient_cookies/transient_headers。
2. 持久化只允许 ref/metadata；transient 字段明确禁止 DB 保存。
3. 日志序列化自动剔除 secret values。

**必须产物：**
- AuthorizedAccessContext

**验收标准：**
- [ ] 所有 auth_type 有单测
- [ ] DB/log dump 0 cookie/token 明文

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P02-002 · BrowserSessionResolver

**目标：** 从 AccessJob 找到 live session 或恢复 storage_state。

**前置依赖：** P02-001

**实施动作：**
1. 先按 browser_session_id 取 live BrowserSession。
2. 不存在 live session 时从 Vault storage_state 创建短生命周期 context。
3. 恢复后必须 probe login；过期返回 SESSION_EXPIRED。

**必须产物：**
- BrowserSessionResolver

**验收标准：**
- [ ] live/restored 两条路径通过
- [ ] 过期状态不假授权

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P02-003 · ResumeCoordinator 接 BrowserAuthBridge

**目标：** 删除当前空 access_context。

**前置依赖：** P02-002

**实施动作：**
1. 删除 `access_payload['access_context']={}` 固定路径。
2. 解析 session，调用 BRIDGE.to_http_cookies。
3. 构建 AuthorizedAccessContext 传 ACQUISITION.acquire。
4. Provider 若 browser_download_only，改走 Browser Download，不强转 HTTP。

**必须产物：**
- 修改后的 ResumeCoordinator

**验收标准：**
- [ ] 源码不再固定空 context
- [ ] Cookie 保护下载 fixture 能自动续下

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P02-004 · OAuth/API Key/header 桥接

**目标：** 处理非 Cookie 认证。

**前置依赖：** P02-001

**实施动作：**
1. 从 Vault ref 短暂解引用 token/API key/header。
2. 只在创建 HTTP client 时使用，完成即释放。
3. 检查 token expiry；日志仅记录 auth_type/ref。

**必须产物：**
- AuthContextResolver

**验收标准：**
- [ ] OAuth/API key fixture 可下载
- [ ] secrets scan 0

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P02-005 · 登录→自动续下载 E2E

**目标：** 用户只发起一次下载意图。

**前置依赖：** P02-003

**实施动作：**
1. 建立只有正确 Cookie 才能访问下载端点的 fixture。
2. 第一次点击下载→AccessJob→Login→storage_state→AUTHORIZED→Resume→Acquisition→COMPLETED。
3. 关闭浏览器/重启后再用保存 state 验证。

**必须产物：**
- test_auth_resume_e2e.py
- event timeline

**验收标准：**
- [ ] 0 次二次点击
- [ ] 最终 Artifact 内容真实且受 Cookie 保护

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P03 · Browser Search Session 生命周期

**阶段目标：** BrowserSearchWorker 不留下孤儿 Chromium/tab，同时保留 Live Browser 观察能力。

## P03-001 · BrowserSearchWorker close/ownership

**目标：** 明确 session 所有权。

**前置依赖：** P00

**实施动作：**
1. 实现 async close() 幂等。
2. ownership=`worker|task|user`。
3. worker-owned 搜索结束必须关闭；用户接管后转 user。

**必须产物：**
- 生命周期接口

**验收标准：**
- [ ] 重复 close 无异常
- [ ] 无 orphan session

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P03-002 · SearchOrchestrator try/finally

**目标：** 异常/取消也回收。

**前置依赖：** P03-001

**实施动作：**
1. BrowserSearchWorker 创建后立即进入 try/finally。
2. 需要用户继续浏览时持久化 session_id 并转 ownership。
3. timeout/cancel/error 全清理。

**必须产物：**
- orchestrator 修改

**验收标准：**
- [ ] 超时后 session 数恢复基线
- [ ] cancel 无遗留 tab

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P03-003 · SearchRun 绑定 browser_session_id

**目标：** UI 能定位浏览器任务。

**前置依赖：** P03-001

**实施动作：**
1. ProviderTask 或关联表保存 browser_session_id。
2. 事件流包含 provider/task/session。
3. 点击 Provider 进度可切换 Live Browser。

**必须产物：**
- DB/API/UI binding

**验收标准：**
- [ ] 可从 SearchRun 追到 session

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P03-004 · 并发生命周期压力测试

**目标：** 高并发验证无泄漏。

**前置依赖：** P03-002

**实施动作：**
1. 并发 10 个 browser fixture searches，随机 cancel/timeout 30%。
2. 完成后统计 process/context/page。

**必须产物：**
- stress test

**验收标准：**
- [ ] 非 user-owned session 归零

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P04 · RC 验收报告真实性

## P04-001 · 归档旧验收

**目标：** 当前报告只说当前事实。

**前置依赖：** 无

**实施动作：**
1. 旧报告移 `docs/history/`，文件名含 commit/date。
2. 根目录验收报告重新生成，不追加历史冲突段。

**必须产物：**
- history report
- clean acceptance

**验收标准：**
- [ ] 当前报告不存在前文 FAIL 后文 PASS

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P04-002 · 机器可读 Gate

**目标：** 减少口径漂移。

**前置依赖：** 无

**实施动作：**
1. 生成 `metis/artifacts/rc-final/gates.json`，字段 gate/status/evidence/commit/ci_run/notes。
2. Markdown 与 JSON 逐项一致。

**必须产物：**
- gates.json

**验收标准：**
- [ ] Markdown/JSON 100% 对齐

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P05 · Autonomous Acquisition Fabric 领域模型

**阶段目标：** 数据集、网页、社媒、论文、公众号都进入统一采集层。

## P05-001 · AcquisitionTaskType

**目标：** 明确任务类型。

**前置依赖：** 无

**实施动作：**
1. 新增 DATASET_DISCOVERY/DATASET_ACQUIRE/WEB_READ/WEB_CRAWL/SITE_MAP/SOCIAL_SEARCH/SOCIAL_THREAD/SOCIAL_PROFILE/WECHAT_ACCOUNT/PAPER_SEARCH/PAPER_WATCH/NEWS_SEARCH/USER_CLIP/STRUCTURED_EXTRACT。
2. 进入 schema/DB/UI。

**必须产物：**
- enum + migration

**验收标准：**
- [ ] 旧 DownloadJob 不受破坏

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P05-002 · CrawlPlan schema

**目标：** 自主爬取必须有边界。

**前置依赖：** 无

**实施动作：**
1. 字段 seeds/allowed_domains/denied_domains/max_pages/max_depth/max_duration_s/max_bytes/rate_limit_per_domain/concurrency/rendering_policy/auth_scope/robots_policy/link_policy/content_types/extractors/incremental/schedule。
2. 默认必须有 max_pages/max_depth/max_duration。

**必须产物：**
- CrawlPlan

**验收标准：**
- [ ] 无限计划被拒绝
- [ ] 默认不会跨域无限爬

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P05-003 · WebDocumentArtifact

**目标：** 网页也有 Raw/Provenance。

**前置依赖：** 无

**实施动作：**
1. 字段 url/final_url/title/fetched_at/status_code/content_type/html_raw_path/markdown_path/text_hash/http_headers_ref/screenshot_ref/canonical_url/backend/license_hint/auth_mode。
2. Raw HTML immutable。

**必须产物：**
- WebDocumentArtifact

**验收标准：**
- [ ] 一页网页可保存 raw+markdown+hash+source

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P05-004 · SocialRecord 模型

**目标：** 跨平台统一。

**前置依赖：** 无

**实施动作：**
1. SocialPost platform/post_id/url/author/published/text/media/metrics/reply/repost/hashtags/raw_ref。
2. 独立 SocialComment/SocialProfile。
3. metrics 带 collected_at。

**必须产物：**
- social schemas

**验收标准：**
- [ ] X/Reddit/微博/小红书 fixture 可归一

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P05-005 · PaperRecord

**目标：** 论文成为一等数据对象。

**前置依赖：** 无

**实施动作：**
1. title/authors/abstract/date/venue/doi/arxiv_id/url/pdf/code/datasets/topics/source/raw_ref/version。

**必须产物：**
- PaperRecord

**验收标准：**
- [ ] arXiv/仓储 fixture 可映射

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P05-006 · AcquisitionBackend 能力模型

**目标：** 第三方技能只作为后端。

**前置依赖：** 无

**实施动作：**
1. capabilities SEARCH/READ/CRAWL/MAP/BROWSER/AUTH/SOCIAL/PAPER/NEWS/MARKDOWN/STRUCTURED_OUTPUT/SCREENSHOT。
2. backend_id/type/version/license/installed/healthy/auth_required/cost_model/read_only。

**必须产物：**
- BackendCapability

**验收标准：**
- [ ] 未安装后端不会显示 AVAILABLE

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P06 · 合规、安全与采集策略

## P06-001 · CrawlPolicyEngine

**目标：** 每次 Crawl 先过政策检查。

**前置依赖：** 无

**实施动作：**
1. 检查 scheme/domain/auth/max_pages/depth/rate/bytes。
2. 站点 Registry 可标 allow/deny/manual_review。
3. paywall/restricted/identity-gated 默认 BLOCK。

**必须产物：**
- CrawlPolicyEngine

**验收标准：**
- [ ] 策略失败在请求前阻止

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P06-002 · robots.txt 服务

**目标：** 通用爬取默认尊重 robots。

**前置依赖：** 无

**实施动作：**
1. fetch/cache/TTL。
2. 默认 policy=respect；明确 Provider API 可 not_applicable。
3. disallow 返回 BLOCKED_ROBOTS。

**必须产物：**
- robots service

**验收标准：**
- [ ] allow/disallow fixture 正确

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P06-003 · 每域名 RateLimiter

**目标：** 控制扰动。

**前置依赖：** 无

**实施动作：**
1. token bucket/leaky bucket。
2. 默认低频；Provider 可配置。
3. 尊重 429 Retry-After。

**必须产物：**
- rate limiter

**验收标准：**
- [ ] 速率/并发受控

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P06-004 · Human Intervention Policy

**目标：** 所有验证节点统一。

**前置依赖：** 无

**实施动作：**
1. CAPTCHA/MFA/SMS/email/identity/institution/agreement/payment→WAITING_USER。
2. 用户交还后 re-observe。

**必须产物：**
- intervention policy

**验收标准：**
- [ ] 触发后 Agent 0 新输入

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P06-005 · 内容许可元数据

**目标：** 结果知道可否再分发。

**前置依赖：** 无

**实施动作：**
1. Artifact 增 terms_url/license_hint/redistribution_unknown/restricted_access。
2. UNKNOWN 不当开放。
3. 最终 package 给 usage warning。

**必须产物：**
- usage metadata

**验收标准：**
- [ ] 受限原文不自动公开打包

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P06-006 · Prompt Injection 隔离

**目标：** 页面内容永远是数据。

**前置依赖：** 无

**实施动作：**
1. 建立 UntrustedContent 标记。
2. LLM extraction system 明确页面命令不可执行。
3. 网页文字禁止直接构造 shell/CLI/tool args。
4. 工具参数只能来自 Planner schema + allowlist。

**必须产物：**
- injection guard

**验收标准：**
- [ ] ‘上传 cookie’恶意页面不触发工具

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P07 · Skill / Bridge Registry

## P07-001 · BackendAdapter protocol

**目标：** 统一外部能力。

**前置依赖：** 无

**实施动作：**
1. 定义 health/search/read/crawl/map/social_search/paper_search 可选接口。
2. UnsupportedCapability 明确。
3. 所有调用 timeout/cancel。

**必须产物：**
- BackendAdapter

**验收标准：**
- [ ] mock contract tests

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P07-002 · BackendRegistry

**目标：** 动态发现安装与版本。

**前置依赖：** 无

**实施动作：**
1. 注册 built-in/optional sidecar。
2. 启动只检测，不自动安装。
3. 记录 version/license。

**必须产物：**
- BackendRegistry

**验收标准：**
- [ ] 缺失 CLI 不影响启动

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P07-003 · SafeCommandRunner

**目标：** 防 shell injection。

**前置依赖：** 无

**实施动作：**
1. argv list；禁止 shell=True。
2. binary allowlist、固定 cwd、env allowlist。
3. stdout/stderr 上限、timeout、kill tree。
4. secret 仅通过受控 env/ref。

**必须产物：**
- SafeCommandRunner

**验收标准：**
- [ ] `; rm -rf` 不会成为命令

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P07-004 · AcquisitionRouter

**目标：** 按任务选后端。

**前置依赖：** 无

**实施动作：**
1. 默认优先 Official Provider→Direct HTTP→Jina/Reader→Browser→External Crawl API。
2. 社媒优先公开/官方→用户授权 browser bridge→optional service。
3. 记录 rationale/fallback history。

**必须产物：**
- AcquisitionRouter

**验收标准：**
- [ ] 每次 route 有 provenance

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P08 · Agent-Reach Bridge

## P08-001 · 固定 Agent-Reach 集成边界

**目标：** MIT，可选，不自动安装。

**前置依赖：** 无

**实施动作：**
1. 执行时重新读 README/CLI help/LICENSE。
2. 列允许平台与 read-only 动作。
3. 用户明确选择后才安装/启用。

**必须产物：**
- docs/backends/agent-reach.md

**验收标准：**
- [ ] 版本/许可/动作清楚

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P08-002 · doctor/health

**目标：** 复用多平台诊断思想。

**前置依赖：** 无

**实施动作：**
1. 若安装则调用安全 doctor/health。
2. 解析 available/config-required/unavailable。
3. 部分平台失败不影响其他平台。

**必须产物：**
- AgentReachBackend.health

**验收标准：**
- [ ] 未安装→NOT_INSTALLED

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P08-003 · 只读 search/read bridge

**目标：** 用于 Metis 未原生覆盖的平台。

**前置依赖：** 无

**实施动作：**
1. 根据当前上游实际 CLI 实现，不猜命令。
2. 只开放 search/read/transcript/feed。
3. 结果转 WebDocument/SocialRecord。
4. 不读取未授权 Cookie。

**必须产物：**
- AgentReachBackend

**验收标准：**
- [ ] 至少 2 个平台 smoke/fixture

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P08-004 · fallback 策略

**目标：** 它不能成为单点依赖。

**前置依赖：** 无

**实施动作：**
1. 原生 Provider 更可靠时优先原生。
2. Agent-Reach 失败可 fallback Browser/OpenCLI/Jina。
3. 记录 backend chain。

**必须产物：**
- routing rules

**验收标准：**
- [ ] 禁用 Agent-Reach 核心仍可用

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P09 · OpenCLI Bridge

## P09-001 · OpenCLI 环境探测

**目标：** 不假设 npm 包已安装。

**前置依赖：** 无

**实施动作：**
1. 检测 opencli --version/doctor。
2. 记录版本、Node 环境、Browser Bridge 状态。
3. 不自动安装扩展。

**必须产物：**
- OpenCLIBackend.health

**验收标准：**
- [ ] 缺包/未连接分别诊断

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P09-002 · OpenCLI read/search

**目标：** 复用已验证 adapter。

**前置依赖：** 无

**实施动作：**
1. 动态读取 opencli list/site info。
2. 优先 JSON/结构化输出。
3. 统一映射 record。

**必须产物：**
- OpenCLIBackend

**验收标准：**
- [ ] 至少 2 个当前 adapter smoke

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P09-003 · External Browser Backend

**目标：** 用户明确选‘Use my Chrome/OpenCLI’才启用。

**前置依赖：** 无

**实施动作：**
1. Metis Native Browser 仍默认。
2. 统一 navigate/read/click/type 接口。
3. 网页内容不能调用任意 JS/shell。

**必须产物：**
- ExternalBrowserBackend

**验收标准：**
- [ ] 切换 backend 不影响上层 schema

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P09-004 · SiteRecipe 经验沉淀

**目标：** adapter authoring 结果进入 Metis。

**前置依赖：** 无

**实施动作：**
1. SiteRecipe domain/search_entry/search_locator/result_locator/pagination/content_ready/login_markers/notes/version。
2. Agent 生成候选 recipe，verify 通过才 VERIFIED。

**必须产物：**
- SiteRecipe

**验收标准：**
- [ ] 未验证 recipe 不生产启用

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P10 · bb-browser 安全受限 Bridge

## P10-001 · bb 环境与安全检查

**目标：** 只在 loopback 使用。

**前置依赖：** 无

**实施动作：**
1. 检测 CLI/daemon/version。
2. 若 daemon 绑定 0.0.0.0，默认 SECURITY_WARNING/拒绝。
3. 记录 MIT license。

**必须产物：**
- BBBrowserBackend.health

**验收标准：**
- [ ] 远程暴露不会静默连接

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P10-002 · bb 命令白名单

**目标：** 只开放可审计读取动作。

**前置依赖：** 无

**实施动作：**
1. 允许 open/snapshot/click/type/screenshot/经过审计的 site adapters。
2. 默认禁止 network body capture、任意 eval、webpack/private API 注入进入 Agent 工具面。
3. developer mode 才可手工调试高风险命令。

**必须产物：**
- bb command policy

**验收标准：**
- [ ] LLM 无法调用禁用命令

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P10-003 · bb 结构化输出归一

**目标：** 保留 Raw JSON。

**前置依赖：** 无

**实施动作：**
1. 优先 --json 等稳定模式。
2. 映射 social/search/paper/news。
3. 原始输出作为 immutable sidecar。

**必须产物：**
- BBBrowserBackend

**验收标准：**
- [ ] 至少 3 类 record 可归一

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P11 · Web-Access 设计能力吸收

**阶段目标：** 吸收联网策略、目标内容就绪、站点经验和 tab 生命周期，不新增冲突的第二套 Browser 核心。

## P11-001 · Web Access Strategy Policy

**目标：** 把 WebSearch/WebFetch/Direct/Jina/CDP 的选择变成 Metis Router 策略。

**前置依赖：** 无

**实施动作：**
1. 建立任务特征：static/dynamic/authenticated/structured/large/site-wide。
2. 根据特征选择首选和 fallback。
3. 每次 fallback 记录 failure reason。

**必须产物：**
- web access routing policy

**验收标准：**
- [ ] 静态公开页不默认开 Browser
- [ ] 动态登录页会选 Browser

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P11-002 · 目标内容就绪契约

**目标：** navigation success 不等于数据就绪。

**前置依赖：** 无

**实施动作：**
1. 定义 ContentReadyCondition：selector/text/schema/network-idle/custom recipe。
2. 识别登录跳转、验证页、空壳 SPA。
3. timeout 返回 CONTENT_NOT_READY，不返回空成功。

**必须产物：**
- ContentReadyCondition

**验收标准：**
- [ ] 延迟 SPA fixture 能等待真正正文

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P11-003 · SiteExperienceStore

**目标：** 积累域名级成功经验。

**前置依赖：** 无

**实施动作：**
1. 字段 domain/url patterns/preferred backend/login markers/content ready/selectors/pagination/last_verified/failures。
2. 经验过期降低置信。
3. 严禁存 Cookie/Token。

**必须产物：**
- SiteExperienceStore

**验收标准：**
- [ ] 跨任务可复用
- [ ] secret scan 0

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P11-004 · tab idle cleanup

**目标：** 异常任务不留孤儿 tab。

**前置依赖：** 无

**实施动作：**
1. user-owned 和 agent-owned 分开。
2. agent-owned idle 自动关闭。
3. 下载中/Takeover 不误关。

**必须产物：**
- tab lifecycle manager

**验收标准：**
- [ ] 异常退出后 orphan tabs 可回收

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P12 · 通用网页读取：Direct + Markdown + Jina

## P12-001 · DirectWebReader

**目标：** 实现公开网页普通 HTTP 读取。

**前置依赖：** 无

**实施动作：**
1. 遵守 redirect/content length/timeout。
2. 保存 raw headers/body。
3. HTML→content extraction；JSON/XML→相应 parser。

**必须产物：**
- DirectWebReader

**验收标准：**
- [ ] 公开 fixture 输出 WebDocumentArtifact

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P12-002 · 本地主内容提取

**目标：** 网页正文转 Markdown。

**前置依赖：** 无

**实施动作：**
1. 使用成熟主内容抽取库或现有实现。
2. 保留 title/meta/schema.org/json-ld/links。
3. script/style 清理。
4. 输出 markdown + plain text。

**必须产物：**
- HtmlExtractor

**验收标准：**
- [ ] 导航噪声明显减少
- [ ] Raw HTML 保留

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P12-003 · JinaReaderBackend

**目标：** 公开 URL 可选 Reader。

**前置依赖：** 无

**实施动作：**
1. 仅用于公开 URL；不尝试登录后页面。
2. 无 key 基础模式 + Vault key 高速率模式。
3. 访问拒绝按拒绝处理。
4. 保存 source_url/backend/fetch_time。

**必须产物：**
- JinaReaderBackend

**验收标准：**
- [ ] 公开 URL 可返回 Markdown
- [ ] 登录/拒绝页不伪造成正文

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P12-004 · Reader 质量评估与 fallback

**目标：** 自动判断 direct 是否足够。

**前置依赖：** 无

**实施动作：**
1. 使用 content length/boilerplate ratio/title consistency/JS-shell 检查。
2. direct 不足→Jina 或 Browser。
3. 禁止只用 LLM 主观说‘完整’。

**必须产物：**
- quality evaluator

**验收标准：**
- [ ] 动态页能 fallback
- [ ] 静态页不浪费 Browser

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P13 · XCrawl 可选 SaaS Backend

## P13-001 · XCrawl 配置和 Vault

**目标：** 安全配置外部服务。

**前置依赖：** 无

**实施动作：**
1. base URL/token ref/timeout/credit ceiling。
2. API key 只进 Vault。
3. 未配置→NOT_CONFIGURED。

**必须产物：**
- XCrawl config

**验收标准：**
- [ ] secret scan 0

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P13-002 · XCrawl scrape

**目标：** 封装单页抓取。

**前置依赖：** 无

**实施动作：**
1. 按当前官方 API 实现 Markdown/HTML/links/screenshot/JSON。
2. 异步轮询有 timeout/cancel。
3. 归一 WebDocumentArtifact。

**必须产物：**
- XCrawlBackend.scrape

**验收标准：**
- [ ] 官方 example smoke
- [ ] 失败状态准确

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P13-003 · XCrawl map/crawl

**目标：** 支持受控全站发现和抓取。

**前置依赖：** 无

**实施动作：**
1. CrawlPlan 必须先过本地 PolicyEngine。
2. 服务端即使允许大范围，本地上限仍生效。
3. 逐页写 Artifact store，不在内存积全部结果。

**必须产物：**
- XCrawlBackend.map/crawl

**验收标准：**
- [ ] 本地 max_pages 生效
- [ ] 取消能停止

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P13-004 · XCrawl SERP

**目标：** 作为搜索后端。

**前置依赖：** 无

**实施动作：**
1. keyword→结果→按需正文。
2. 记录 engine/localization/page metadata。

**必须产物：**
- XCrawlBackend.search

**验收标准：**
- [ ] Search result 和 fetched page provenance 分开

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P14 · 社媒统一采集层

## P14-001 · SocialSourceAdapter contract

**目标：** 统一 search/post/thread/profile/comments。

**前置依赖：** 无

**实施动作：**
1. read-only。
2. 支持 cursor/max_records/since/until。
3. 全部返回统一 SocialRecord。

**必须产物：**
- SocialSourceAdapter

**验收标准：**
- [ ] contract tests

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P14-002 · Social Query Planner

**目标：** 研究问题转受控平台查询。

**前置依赖：** 无

**实施动作：**
1. 输出 platforms/keywords/hashtags/accounts/date range/max records/comment depth。
2. 默认 bounded。
3. 用户可审查计划。

**必须产物：**
- SocialQueryPlan

**验收标准：**
- [ ] ‘分析近30天口碑’产生明确时间窗和上限

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P14-003 · Raw + normalized 双层存储

**目标：** 保留平台原字段。

**前置依赖：** 无

**实施动作：**
1. 原始 JSON/HTML immutable。
2. normalized JSONL/Parquet 生成 DatasetArtifact。
3. metrics 带 collected_at。

**必须产物：**
- social pipeline

**验收标准：**
- [ ] 原始记录可追溯

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P14-004 · 跨平台去重与关系

**目标：** 避免错误合并。

**前置依赖：** 无

**实施动作：**
1. 平台内 post_id 主键。
2. 跨平台相似内容只标 probable_duplicate。
3. 保留 reply/repost/quote。

**必须产物：**
- dedupe service

**验收标准：**
- [ ] 不同平台同文本不静默删除

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P15 · 微信公众号采集

## P15-001 · 微信上游许可与安全隔离

**目标：** 吸收能力但替换不安全凭据方式。

**前置依赖：** 无

**实施动作：**
1. 记录当前重定向仓库 ghh1251/wechat_articles_spider、MIT，以及其引用 Apache-2.0 上游。
2. 优先独立重写 adapter。
3. 禁止使用明文 `weixin_credentials.py`。
4. 不采用‘封号后换账号继续’策略。

**必须产物：**
- docs/backends/wechat.md

**验收标准：**
- [ ] 来源/许可清楚
- [ ] 无明文 cookie

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P15-002 · WeChatOfficialAccountPlan

**目标：** 定义小规模研究边界。

**前置依赖：** 无

**实施动作：**
1. accounts/keywords/since/until/max_per_account/include_body。
2. 默认 max_per_account 较低。
3. 无限历史计划被阻止或需用户显式扩大。

**必须产物：**
- WeChat plan

**验收标准：**
- [ ] validator 生效

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P15-003 · 微信登录 + Vault

**目标：** 扫码验证由用户完成。

**前置依赖：** 无

**实施动作：**
1. Browser 打开登录。
2. 用户手工扫码/安全验证。
3. 成功后 storage_state→Vault。
4. 验证码/安全检查→WAITING_USER。

**必须产物：**
- wechat auth recipe

**验收标准：**
- [ ] 凭据不落明文文件

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P15-004 · 按公众号名发现文章

**目标：** 获取 title/url/time/account。

**前置依赖：** 无

**实施动作：**
1. 通过当前可合法访问的界面或公开路径搜索。
2. 严格 rate limit。
3. 验证页立即停止。

**必须产物：**
- WeChat adapter

**验收标准：**
- [ ] fixture + 用户授权真实 smoke 可返回列表

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P15-005 · 公众号正文获取

**目标：** 列表→正文。

**前置依赖：** 无

**实施动作：**
1. 公开文章优先 direct/Jina，必要时 Browser。
2. 每篇生成 WebDocumentArtifact。
3. 记录 account/title/time/url/hash。

**必须产物：**
- article artifacts

**验收标准：**
- [ ] 正文与列表 provenance 完整

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P15-006 · 文章研究数据集

**目标：** 输出可分析表。

**前置依赖：** 无

**实施动作：**
1. CSV/Parquet：account,title,url,publish_time,text,keywords,word_count,source_hash。
2. 关键词评分若有，标 derived 并记录公式。

**必须产物：**
- wechat dataset

**验收标准：**
- [ ] Raw/derived 可追溯

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P16 · 国内自媒体能力与 MediaCrawler 许可边界

## P16-001 · MediaCrawler License Gate

**目标：** 防止非商业许可证代码误进入生产。

**前置依赖：** 无

**实施动作：**
1. third-party inventory 标 REFERENCE_ONLY。
2. CI 扫描禁止 vendor/import MediaCrawler。
3. 生产 dependency tree 禁止出现其包/源码。
4. 仅 docs 允许参考。

**必须产物：**
- license policy
- CI scan

**验收标准：**
- [ ] 生产依赖 0 MediaCrawler

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P16-002 · 自有 ChineseSocialRecipe

**目标：** 用 Metis/OpenCLI/AgentReach 等实现国内平台。

**前置依赖：** 无

**实施动作：**
1. 首批微博、知乎、B站；小红书/抖音仅用户已有授权会话且政策允许。
2. 每个平台描述 search/result/detail/comments/login markers。
3. 不复制签名、反检测、代理池逻辑。

**必须产物：**
- ChineseSocialRecipe

**验收标准：**
- [ ] 每个平台 fixture 通过

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P16-003 · 国内平台读取优先级

**目标：** 避免重型/高风险路径。

**前置依赖：** 无

**实施动作：**
1. 公开 direct/Jina 可读则优先。
2. 官方/公开 adapter 或用户授权 browser 次之。
3. 遇风控/验证码停止。

**必须产物：**
- routing rules

**验收标准：**
- [ ] CAPTCHA 不 fallback 绕过

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P17 · 6551 opennews / opentwitter

## P17-001 · OpenNews Backend

**目标：** 接入资讯 API。

**前置依赖：** 无

**实施动作：**
1. 执行时重新读取当前 Skill/API 说明。
2. Vault token。
3. 支持上游真实 keyword/source/date 等参数。
4. AI rating/trading signal 标 provider_supplied_derived，不能当事实。

**必须产物：**
- OpenNewsBackend

**验收标准：**
- [ ] 无 token→NOT_CONFIGURED
- [ ] 来源字段完整

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P17-002 · OpenTwitter Backend

**目标：** 接入只读 X 数据。

**前置依赖：** 无

**实施动作：**
1. 支持当前真实 profile/search/user tweets 等接口。
2. 默认不采 deleted/follower-event 等扩展，除非用户明确研究需要且服务允许。
3. 映射 SocialRecord。

**必须产物：**
- OpenTwitterBackend

**验收标准：**
- [ ] 搜索 smoke/fixture
- [ ] token 脱敏

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P17-003 · 6551 服务降级

**目标：** 外部服务不能成为单点。

**前置依赖：** 无

**实施动作：**
1. opentwitter→AgentReach/OpenCLI/user browser。
2. opennews→普通 web/news search。
3. 5xx/timeout 自动进入 fallback。

**必须产物：**
- fallback policy

**验收标准：**
- [ ] 模拟 5xx 可继续

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P18 · 论文发现、追踪与 Digest

## P18-001 · PaperWatchPlan

**目标：** 泛化 Agent-Paper-Digest 的追踪模式。

**前置依赖：** 无

**实施动作：**
1. topics/keywords/negative keywords/sources/since/cadence/max_results/ranking rubric。
2. 可从当前 Project research question 生成建议。

**必须产物：**
- PaperWatchPlan

**验收标准：**
- [ ] 非 Agent 主题可配置

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P18-002 · Paper search service

**目标：** 统一论文来源。

**前置依赖：** 无

**实施动作：**
1. 优先结构化学术来源/仓储；web search 补充。
2. DOI/arXiv ID 去重。
3. 记录 full-text/data access。

**必须产物：**
- paper search

**验收标准：**
- [ ] 重复 DOI 合并且来源保留

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P18-003 · Paper relevance classifier

**目标：** 必读/选读/速览有依据。

**前置依赖：** 无

**实施动作：**
1. 按 relevance/method similarity/data relevance/novelty hint 分维度。
2. 推荐等级标为 recommendation，不是事实。

**必须产物：**
- paper ranker

**验收标准：**
- [ ] 每个等级有理由

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P18-004 · Digest 输出

**目标：** 生成新增论文简报。

**前置依赖：** 无

**实施动作：**
1. 包含新增、相关原因、方法、数据链接、DOI。
2. 保存每次 query/result set。
3. 输出 Markdown + Paper Dataset。

**必须产物：**
- digest.md
- paper dataset

**验收标准：**
- [ ] 第二次运行不把旧论文当新增

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P18-005 · Paper Watch 调度

**目标：** 支持日/周增量。

**前置依赖：** 无

**实施动作：**
1. 接现有 scheduler。
2. 只有新结果才通知。
3. 失败可观察。

**必须产物：**
- watch job

**验收标准：**
- [ ] 连续两次增量正确

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P19 · Web Clip / Markdown Archive / Obsidian Export

## P19-001 · WebClipTemplate

**目标：** 模板化抓 metadata/正文。

**前置依赖：** 无

**实施动作：**
1. match domains/path/title template/properties/content selector/extractor/output path。
2. 支持 schema.org/meta/json-ld variables。
3. 模板版本化。

**必须产物：**
- WebClipTemplate

**验收标准：**
- [ ] 站点可自动匹配模板

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P19-002 · Clip Artifact

**目标：** 当前页一键保存。

**前置依赖：** 无

**实施动作：**
1. 保存 URL/title/selection 或 main content/metadata/raw ref/markdown。
2. 用户 selection 优先。
3. 图片默认保留远程 URL，不批量下载。

**必须产物：**
- clip service

**验收标准：**
- [ ] 当前页可保存 Markdown

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P19-003 · Obsidian Exporter

**目标：** 可选输出用户 vault。

**前置依赖：** 无

**实施动作：**
1. 用户显式配置 vault path。
2. 路径 allowlist。
3. frontmatter+Markdown。
4. 不安装 Obsidian 也可生成文件。

**必须产物：**
- ObsidianExporter

**验收标准：**
- [ ] 测试 vault 有可读 md
- [ ] 路径穿越被拒绝

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P20 · 自主 Crawl Engine

## P20-001 · CrawlJob 状态机

**目标：** 管理长任务。

**前置依赖：** 无

**实施动作：**
1. CREATED→POLICY_CHECK→DISCOVERING→FETCHING→EXTRACTING→VALIDATING→COMPLETE。
2. 包含 WAITING_USER/PAUSED/FAILED/CANCELLED。
3. 状态持久化 history。

**必须产物：**
- CrawlJob

**验收标准：**
- [ ] 非法迁移失败
- [ ] 可恢复

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P20-002 · URL Canonicalizer

**目标：** 稳定去重 URL。

**前置依赖：** 无

**实施动作：**
1. normalize scheme/host/fragment/default ports。
2. 去常见 tracking 参数。
3. canonical link 仅在合理同域时采信。
4. 保留业务 query/pagination 参数。

**必须产物：**
- canonicalizer

**验收标准：**
- [ ] utm 去重
- [ ] page 参数不误删

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P20-003 · Frontier Priority Queue

**目标：** 调度待抓 URL。

**前置依赖：** 无

**实施动作：**
1. 按 seed relevance/depth/domain/path 排序。
2. canonical URL 去重。
3. 支持 pause/cancel/checkpoint。

**必须产物：**
- crawl frontier

**验收标准：**
- [ ] 10k URL 不丢状态

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P20-004 · Link Discovery

**目标：** 页面自动发现链接。

**前置依赖：** 无

**实施动作：**
1. HTML/Markdown/JSON-LD 抽链接。
2. 过滤 mailto/javascript/data。
3. 遵守 allowed_domains/max_depth。
4. 记录 parent-child edge。

**必须产物：**
- link discovery

**验收标准：**
- [ ] 跨域非 allowlist 不入队

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P20-005 · Sitemap/RSS/Atom Discovery

**目标：** 优先结构化发现。

**前置依赖：** 无

**实施动作：**
1. 解析 sitemap/index/feed。
2. 利用 lastmod/published 做增量优先。

**必须产物：**
- sitemap/feed parser

**验收标准：**
- [ ] fixture 正确

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P20-006 · Fetcher Router

**目标：** 每 URL 自动选 backend。

**前置依赖：** 无

**实施动作：**
1. 先过 PolicyEngine。
2. 按 site experience/content ready/auth/dynamic 选择 Direct/Jina/Browser/XCrawl。
3. 有限 fallback。

**必须产物：**
- crawl fetch router

**验收标准：**
- [ ] 每 URL 记录 backend_used/fallbacks

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P20-007 · Incremental Crawl

**目标：** 避免重复抓。

**前置依赖：** 无

**实施动作：**
1. 利用 ETag/Last-Modified/hash。
2. 304 不产生新 raw。
3. 正文变化生成新 artifact version。

**必须产物：**
- incremental service

**验收标准：**
- [ ] 不变页面二次运行不重复

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P20-008 · Checkpoint/Resume

**目标：** 崩溃后继续。

**前置依赖：** 无

**实施动作：**
1. 持久化 frontier/visited/stats。
2. 不可安全重放的 Browser 表单进入 NEEDS_REVIEW。
3. 过期 session WAITING_USER。

**必须产物：**
- recovery

**验收标准：**
- [ ] 强杀后 resume

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P20-009 · Bounded Crawl E2E

**目标：** 验证真正自主爬取。

**前置依赖：** 无

**实施动作：**
1. 本地 50 页站点：循环链接/sitemap/SPA/robots。
2. 计划 max_pages=25,max_depth=3。
3. 执行后检查访问集合。

**必须产物：**
- crawl E2E

**验收标准：**
- [ ] ≤25 页
- [ ] robots 禁止 URL 0 请求
- [ ] 无重复 canonical

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P21 · 网页内容抽取与结构化数据生成

## P21-001 · Metadata Extractor

**目标：** 统一抽取网页元数据。

**前置依赖：** 无

**实施动作：**
1. title/author/published/modified/site_name/language/description/canonical/og/schema.org。
2. 每个字段记录 extraction source。

**必须产物：**
- metadata extractor

**验收标准：**
- [ ] 字段可追溯

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P21-002 · Table Extractor

**目标：** HTML 表直接变 DatasetArtifact。

**前置依赖：** 无

**实施动作：**
1. 识别 header/rowspan/colspan。
2. 原始 table HTML 保存。
3. 输出 CSV/Parquet + source URL。

**必须产物：**
- table extractor

**验收标准：**
- [ ] 复杂表 fixture 行列正确

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P21-003 · JSON-LD/embedded data

**目标：** 优先利用站点结构化数据。

**前置依赖：** 无

**实施动作：**
1. 解析 application/ld+json。
2. 限制大小/递归。
3. Raw JSON-LD 保存。

**必须产物：**
- structured extractor

**验收标准：**
- [ ] Article/Dataset schema fixture

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P21-004 · LLM Structured Extract

**目标：** 按用户 schema 抽记录。

**前置依赖：** 无

**实施动作：**
1. 输入 WebDocument + JSON Schema。
2. 严格 structured output。
3. 每个字段附 evidence text/span/locator。
4. 无法证实时 null + confidence。

**必须产物：**
- structured extraction service

**验收标准：**
- [ ] 模型不能无证据填字段

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P21-005 · 多页记录合并

**目标：** 多个网页生成研究数据集。

**前置依赖：** 无

**实施动作：**
1. schema union 先检查。
2. 每行强制 source_url/source_artifact_id/fetched_at。
3. 类型冲突进入 validation。

**必须产物：**
- web-to-dataset builder

**验收标准：**
- [ ] 100 页→一份 dataset 且逐行可追溯

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P22 · 采集 Provenance 与可复现性

## P22-001 · Fetch provenance

**目标：** 记录每次请求。

**前置依赖：** 无

**实施动作：**
1. url/final_url/backend/status/time/headers hash/auth mode/parent url/crawl job。
2. 敏感 headers 只记录名称/哈希。

**必须产物：**
- fetch provenance

**验收标准：**
- [ ] 随机页面可追到具体 backend

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P22-002 · Extraction provenance

**目标：** 字段级提取来源。

**前置依赖：** 无

**实施动作：**
1. extractor/version/source artifact/selector/json path/evidence/LLM model（若使用）。

**必须产物：**
- extraction lineage

**验收标准：**
- [ ] 随机字段可回溯

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P22-003 · Backend provenance

**目标：** 外部工具身份明确。

**前置依赖：** 无

**实施动作：**
1. backend id/version/upstream URL/license/cost units（可得时）。
2. 外部服务返回不得伪装成原站官方 API。

**必须产物：**
- backend metadata

**验收标准：**
- [ ] Jina/XCrawl/AgentReach 等来源可区分

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P22-004 · Crawl Methodology 自动生成

**目标：** 用户可复查采集方法。

**前置依赖：** 无

**实施动作：**
1. 记录 CrawlPlan/domains/rate/backend fallbacks/auth/blocked pages/counts/timestamps/extraction。
2. 只写真实发生步骤。

**必须产物：**
- crawl_methodology.md

**验收标准：**
- [ ] 与 event/DB 一致

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P23 · 站点经验积累与自修复

## P23-001 · Experience Candidate

**目标：** 从成功/失败生成经验候选。

**前置依赖：** 无

**实施动作：**
1. 记录 URL pattern/locator/content ready/pagination/login markers/backend result。
2. 不记录 cookie/token/个人正文。

**必须产物：**
- experience candidates

**验收标准：**
- [ ] secret scan 0

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P23-002 · Experience 验证

**目标：** 单次 LLM 猜测不能升可信。

**前置依赖：** 无

**实施动作：**
1. 至少两次成功或显式 verify 才 VERIFIED。
2. 单次候选=PROPOSED。
3. 结构变更失败后标 STALE。

**必须产物：**
- experience validator

**验收标准：**
- [ ] 错误 selector 不无限复用

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P23-003 · Recipe 自动修复流程

**目标：** 失败后可生成并验证新版本。

**前置依赖：** 无

**实施动作：**
1. 旧 recipe fail→browser inspect→candidate→fixture/real smoke→version bump。
2. 未验证不可覆盖 production。

**必须产物：**
- recipe versioning

**验收标准：**
- [ ] 修复有 diff+test

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P24 · 采集工作台 UI

## P24-001 · Acquisition Task 面板

**目标：** 展示爬取/社媒/论文任务。

**前置依赖：** 无

**实施动作：**
1. 类型/状态/source/backend/progress/pages/records/bytes/errors。
2. pause/resume/cancel。

**必须产物：**
- UI task panel

**验收标准：**
- [ ] 长任务状态实时

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P24-002 · Crawl Plan Review

**目标：** 抓站前用户看得懂范围。

**前置依赖：** 无

**实施动作：**
1. seed/domains/max pages/depth/rate/auth/backend preference。
2. 登录或高风险需要确认。

**必须产物：**
- plan review

**验收标准：**
- [ ] 用户可改 max_pages

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P24-003 · Live Browser 复用

**目标：** Browser backend 统一可观察。

**前置依赖：** 无

**实施动作：**
1. Native Browser 进入现有 Live view。
2. OpenCLI/bb external-session 无法内嵌时明确标 External Browser，不伪装。
3. 显示 owner/provider/task。

**必须产物：**
- browser UI integration

**验收标准：**
- [ ] 用户知道当前哪个浏览器在操作

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P24-004 · Collected Content Preview

**目标：** 支持多内容类型。

**前置依赖：** 无

**实施动作：**
1. Markdown 页面、social timeline、paper list、dataset table。
2. 来源 URL 始终可见。

**必须产物：**
- preview UI

**验收标准：**
- [ ] 原始来源一键打开

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P24-005 · Backend Health 页面

**目标：** 外部技能可诊断。

**前置依赖：** 无

**实施动作：**
1. 显示 installed/configured/healthy/version/license/cost/auth。
2. 只提供诊断与设置入口，不静默安装。

**必须产物：**
- health UI

**验收标准：**
- [ ] 不可用原因清楚

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P25 · Agent 自主采集工具与编排

## P25-001 · 高层 Agent tools

**目标：** 禁止万能 shell。

**前置依赖：** 无

**实施动作：**
1. 新增 web.search/web.read/web.crawl/social.search/social.thread/wechat.collect/papers.search/papers.watch/content.extract/crawl.status/crawl.pause/crawl.resume。
2. 所有参数严格 schema。

**必须产物：**
- agent tool schemas

**验收标准：**
- [ ] 无任意 run_shell(command:str)

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P25-002 · Acquisition Planner

**目标：** 自然语言→具体受控采集计划。

**前置依赖：** 无

**实施动作：**
1. 判断一次搜索/单页/站点 crawl/社媒/持续 watch。
2. 估算范围并保守默认。
3. 需要登录显式标记。

**必须产物：**
- Acquisition Planner

**验收标准：**
- [ ] ‘抓整个网站’不会直接无限执行

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P25-003 · 多后端执行规则

**目标：** 失败后按策略降级。

**前置依赖：** 无

**实施动作：**
1. Router 选择 backend。
2. 错误码决定 fallback。
3. 不同 backend 尝试次数有限。
4. CAPTCHA 等立即 WAITING_USER。

**必须产物：**
- orchestration

**验收标准：**
- [ ] fallback chain 可解释

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P25-004 · 采集后自动转数据

**目标：** 根据目标决定输出。

**前置依赖：** 无

**实施动作：**
1. 单页→Markdown；同类页面→Dataset；社媒→Parquet；论文→Paper dataset/digest。
2. 用户只要求保存原文时不额外改写。

**必须产物：**
- post-processing policy

**验收标准：**
- [ ] 输出符合用户明确目标

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P26 · 持续监测与增量获取

## P26-001 · WatchJob

**目标：** 统一定时监测。

**前置依赖：** 无

**实施动作：**
1. plan_id/cadence/last_run/next_run/checkpoint/notify_on_change/status。
2. 默认 read-only。

**必须产物：**
- WatchJob

**验收标准：**
- [ ] 状态可恢复

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P26-002 · Change Detector

**目标：** 只识别真正变化。

**前置依赖：** 无

**实施动作：**
1. content hash/ETag/record ID/publish time。
2. 区分正文变化和 metrics 变化。

**必须产物：**
- change detector

**验收标准：**
- [ ] 无变化不重复输出

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P26-003 · 增量通知

**目标：** 有意义变化才通知。

**前置依赖：** 无

**实施动作：**
1. 新增文章/论文/帖子/数据版本。
2. 通知带来源 URL 和变化摘要。

**必须产物：**
- change events

**验收标准：**
- [ ] 重复 run 无噪声

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P27 · 外部 Skill / Browser / Crawler 安全

## P27-001 · CDP 安全策略

**目标：** 本地浏览器控制不得外暴。

**前置依赖：** 无

**实施动作：**
1. native/sidecar CDP 默认只 127.0.0.1。
2. 发现 0.0.0.0 默认拒绝并提示。
3. 支持 session token 时启用。

**必须产物：**
- CDP guard

**验收标准：**
- [ ] 远程暴露被阻止

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P27-002 · 第三方 CLI 输出视为不可信

**目标：** stdout 不能控制 Agent。

**前置依赖：** 无

**实施动作：**
1. JSON schema validate。
2. 文本指令不触发工具。
3. 超大输出截断并落 raw。

**必须产物：**
- bridge output guard

**验收标准：**
- [ ] 恶意 stdout 不执行命令

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P27-003 · SSRF Guard 扩展

**目标：** Crawler 不访问内网/metadata。

**前置依赖：** 无

**实施动作：**
1. 阻止 localhost/private/link-local/cloud metadata。
2. DNS resolve 前后检查。
3. redirect 后再次验证。
4. developer allowlist 独立开关。

**必须产物：**
- SSRF tests

**验收标准：**
- [ ] 典型 metadata IP 全阻止

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P27-004 · 附件安全

**目标：** 所有附件走 DownloadManager。

**前置依赖：** 无

**实施动作：**
1. PDF/CSV/ZIP/media 先 DownloadJob。
2. 大小/MIME/hash/archive safety。
3. Crawler 不直接写 raw。

**必须产物：**
- attachment pipeline

**验收标准：**
- [ ] 无 bypass path

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P27-005 · 数据最小化

**目标：** 登录站点只采请求范围。

**前置依赖：** 无

**实施动作：**
1. 默认不读取私信、联系人、通知。
2. Social adapters 定义允许字段。
3. Browser snapshot 敏感输入脱敏。

**必须产物：**
- privacy policy

**验收标准：**
- [ ] fixture 私信区域默认不采

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P28 · 性能、限额与稳定性

## P28-001 · 1000 页 Crawl 性能

**目标：** 验证内存有界。

**前置依赖：** 无

**实施动作：**
1. 本地 1000 页 synthetic site，含重复和少量 JS。
2. 记录 duration/RSS/DB/frontier。
3. HTML 不全驻内存。

**必须产物：**
- benchmark report

**验收标准：**
- [ ] 峰值内存记录且无 OOM

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P28-002 · 10000 Social Record 流式写入

**目标：** 避免大 list。

**前置依赖：** 无

**实施动作：**
1. 分页→batch write parquet/jsonl/db。
2. checkpoint cursor。

**必须产物：**
- benchmark

**验收标准：**
- [ ] 中断后从 cursor 恢复

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P28-003 · Backend Circuit Breaker

**目标：** 服务故障隔离。

**前置依赖：** 无

**实施动作：**
1. 连续 5xx/timeout 达阈值 OPEN。
2. 冷却后 HALF_OPEN。
3. Router fallback。

**必须产物：**
- circuit breaker

**验收标准：**
- [ ] 模拟故障不拖垮全任务

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P28-004 · 全局配额

**目标：** 保护磁盘/流量/付费 API。

**前置依赖：** 无

**实施动作：**
1. max bytes/day、external service credit ceiling、max crawl pages。
2. 超过配额暂停，不自动购买。

**必须产物：**
- quota manager

**验收标准：**
- [ ] 超额进入 PAUSED_QUOTA

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P29 · 测试矩阵与 CI

## P29-001 · Backend Contract Harness

**目标：** 统一测所有后端。

**前置依赖：** 无

**实施动作：**
1. health/search/read/crawl unsupported semantics/timeout/cancel/schema/security。
2. AgentReach/OpenCLI/bb/Jina/XCrawl/6551 接适用测试。

**必须产物：**
- contract harness

**验收标准：**
- [ ] 新增 backend 必须过合同测试

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P29-002 · Crawler Fixture Site

**目标：** CI 可完全复现。

**前置依赖：** 无

**实施动作：**
1. 静态页、SPA、登录、CAPTCHA marker、robots、sitemap、RSS、循环、附件、表格、prompt injection 文本。

**必须产物：**
- fixture site

**验收标准：**
- [ ] CI 自动启动/停止

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P29-003 · Architecture Tests

**目标：** 锁死关键主链。

**前置依赖：** 无

**实施动作：**
1. 默认前端 Search 必须 planning_id。
2. ResumeCoordinator 禁止固定空 access_context。
3. 生产 API 禁直接 adapter.acquire_dataset。
4. BrowserSearchWorker 必须 close/finally。
5. MediaCrawler 不得进生产依赖。
6. 禁止 shell=True。

**必须产物：**
- architecture tests

**验收标准：**
- [ ] 任一回归 CI 红

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P29-004 · Real Smoke Workflow

**目标：** 外网验证与普通 CI 分离。

**前置依赖：** 无

**实施动作：**
1. workflow_dispatch + scheduled。
2. 只用无需账号或专门测试账号。
3. 上传 provider/backend verification artifacts。

**必须产物：**
- GitHub workflow

**验收标准：**
- [ ] 外网抖动不随机打断普通 PR

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P30 · 真实 Golden Scenarios

## P30-001 · GS-A 默认 Planning→Search

**目标：** 关闭第一个遗留问题。

**前置依赖：** 无

**实施动作：**
1. 从前端输入词典外城市研究请求。
2. 自动 Planning。
3. 捕获 planning_id→SearchRun DB/network 证据。

**必须产物：**
- golden report

**验收标准：**
- [ ] 默认路径不存在 rule-only Search

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P30-002 · GS-B Authenticated Download

**目标：** 关闭 BrowserAuthBridge 遗留问题。

**前置依赖：** 无

**实施动作：**
1. 受控站点：文件必须 Cookie。
2. 一次下载意图→login→state→cookie bridge→auto resume。
3. 重启后再验证 state restore。

**必须产物：**
- golden report

**验收标准：**
- [ ] 无第二次点击
- [ ] Artifact 内容正确

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P30-003 · GS-C 公开网站自主 Crawl

**目标：** 证明通用 Crawl 可用。

**前置依赖：** 无

**实施动作：**
1. 选择允许抓取的公开文档站。
2. 抓 20–50 页。
3. 输出 Markdown archive + metadata dataset + provenance。

**必须产物：**
- crawl package

**验收标准：**
- [ ] 严格不超 CrawlPlan

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P30-004 · GS-D 微信公众号小规模研究

**目标：** 用户授权下验证公众号链。

**前置依赖：** 无

**实施动作：**
1. 1–2 个公众号，少量近期文章。
2. 列表→正文→Markdown→Dataset。
3. 触发安全验证则 WAITING_USER，不绕过。

**必须产物：**
- golden/wechat

**验收标准：**
- [ ] 0 明文 credential

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P30-005 · GS-E 跨平台社媒只读采集

**目标：** 至少两个平台。

**前置依赖：** 无

**实施动作：**
1. 同主题查询。
2. 一个可公开平台 + 一个用户授权/外部合法后端平台。
3. 统一 SocialRecord→Parquet。

**必须产物：**
- golden/social

**验收标准：**
- [ ] Raw 和平台 provenance 完整

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P30-006 · GS-F Paper Watch

**目标：** 任意研究主题增量。

**前置依赖：** 无

**实施动作：**
1. 首次搜索+digest。
2. 第二次运行增量。
3. DOI 去重。

**必须产物：**
- golden/papers

**验收标准：**
- [ ] 旧论文不重复标新增

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P30-007 · GS-G Web→Structured Dataset

**目标：** 多页抽结构化记录。

**前置依赖：** 无

**实施动作：**
1. 至少 20 页。
2. 用户给 schema。
3. 每字段 evidence/source URL。
4. 无证据为 null/unknown。

**必须产物：**
- golden/structured

**验收标准：**
- [ ] 无模型臆造字段

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P30-008 · GS-H Backend Fallback

**目标：** 证明 Router 有韧性。

**前置依赖：** 无

**实施动作：**
1. Direct 故意失败→Jina/Browser。
2. 一个 external backend 模拟 5xx→下一 backend。
3. 保存完整 fallback chain。

**必须产物：**
- golden/fallback

**验收标准：**
- [ ] 结果 provenance 显示真实后端链

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

# P31 · 最终交付、许可证与 RC Gate

## P31-001 · 第三方能力清单

**目标：** 明确可用/参考/外部服务边界。

**前置依赖：** 无

**实施动作：**
1. Agent-Reach MIT optional bridge。
2. OpenCLI Apache-2.0 optional bridge。
3. bb-browser MIT restricted-safe bridge。
4. web-access MIT design/optional bridge。
5. Agent-Paper-Digest MIT workflow inspiration。
6. WeChat spider MIT + Apache upstream notices。
7. MediaCrawler REFERENCE_ONLY。
8. Jina/XCrawl/6551 external services：记录 terms/cost/auth。

**必须产物：**
- THIRD_PARTY_ACQUISITION.md

**验收标准：**
- [ ] license scan 与文档一致

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P31-002 · 更新架构文档

**目标：** 画唯一生产链。

**前置依赖：** 无

**实施动作：**
1. Planning→Search→AcquisitionRouter→Backend→Artifact→Build。
2. Browser Auth→AuthorizedAccessContext→Acquisition。
3. Crawl frontier→fetch→extract→provenance。

**必须产物：**
- docs/architecture.md

**验收标准：**
- [ ] 无双轨主链

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---

## P31-003 · 重写 Final Acceptance

**目标：** 只针对最终 commit。

**前置依赖：** 无

**实施动作：**
1. 引用最终 commit/CI。
2. 列 Gate PASS/FAIL/BLOCKED。
3. 旧报告归历史。
4. Provider/Backend/Golden 数量真实。

**必须产物：**
- Metis_Data_Engineering_Delivery_Acceptance.md

**验收标准：**
- [ ] 内部无矛盾

**失败判定：** 任一必须产物不存在、任一验收失败、使用 mock/placeholder 冒充生产能力、或绕过安全边界，本任务不得标记 PASS。

---


# Phase Gate（每阶段强制执行）

每完成一个 Phase：

- [ ] 本 Phase 非 BLOCKED 任务全部 PASS；
- [ ] lint/ruff PASS；
- [ ] unit PASS；
- [ ] contract/integration PASS；
- [ ] 相关 E2E PASS；
- [ ] secrets scan PASS；
- [ ] 无新增 `shell=True`；
- [ ] 无 plaintext secret；
- [ ] 无生产代码对 MediaCrawler 的 import/vendor dependency；
- [ ] 无未说明 TODO/placeholder/hardcoded success；
- [ ] ENGINEERING_PROGRESS 与 Git/test 一致；
- [ ] 生成 `metis/artifacts/rc-final/phases/<phase>.json`。

---

# 最终 RC Gate

只有以下全部达到才允许写 `Metis Data 1.0 RC — PASS`。

## 主链

- [ ] 默认前端自然语言需求 → `/api/agent/planning` → planning_id → SearchRun；
- [ ] 普通用户路径不再默认走旧 rule-only Search；
- [ ] BrowserSearchWorker 已接 SearchOrchestrator 且无 session 泄漏；
- [ ] Login/Register/Takeover 后自动恢复原 DownloadJob；
- [ ] Browser cookie/storage_state/OAuth/API-key 能进入 AuthorizedAccessContext；
- [ ] 生产下载从 AcquisitionService 统一入口执行；
- [ ] Build Planner 真正驱动 Build，不硬编码 country/year；
- [ ] 当前验收报告只描述最终 commit，无历史自相矛盾。

## 自主采集

- [ ] Direct Web Reader 可用；
- [ ] Jina Reader 可选后端可用；
- [ ] XCrawl 至少 scrape + map/crawl 中一项真实验证；
- [ ] Agent-Reach/OpenCLI/bb-browser 至少两个 Bridge 完成 health + 实际只读任务；
- [ ] 通用 Crawl Engine 有 bounded frontier、robots、rate limit、checkpoint、incremental；
- [ ] Browser 动态页 fallback 可用；
- [ ] 微信公众号小规模采集链代码完整；若现实安全验证阻塞可 BLOCKED；
- [ ] 至少两个社媒平台归一为 SocialRecord；
- [ ] Paper Watch + Digest 可用；
- [ ] Web Clip → Markdown 可用；
- [ ] Obsidian Export 可选可用；
- [ ] 多网页 → Structured Dataset 且字段带 evidence。

## 安全

- [ ] CAPTCHA/MFA/协议全部 Human Intervention；
- [ ] 无 stealth/fingerprint spoofing/验证码绕过；
- [ ] prompt injection fixture 不触发工具；
- [ ] CDP 默认 loopback；
- [ ] SSRF guard；
- [ ] CLI 无 shell injection；
- [ ] secrets scan 0；
- [ ] Raw immutable；
- [ ] MediaCrawler 仅 REFERENCE_ONLY。

## Golden

- [ ] P30-001 PASS；
- [ ] P30-002 PASS；
- [ ] P30-003 PASS；
- [ ] P30-005 PASS；
- [ ] P30-006 PASS；
- [ ] P30-007 PASS；
- [ ] P30-008 PASS；
- [ ] P30-004 若第三方验证阻塞，可 BLOCKED，但必须有真实证据且 Human Takeover 链完整。

---

# 最终交付文件

至少存在：

```text
ENGINEERING_PROGRESS.md
Metis_Data_Engineering_Delivery_Acceptance.md

docs/
  architecture.md
  rc-reality-matrix.md
  acquisition-fabric.md
  crawl-engine.md
  social-acquisition.md
  access-auth-flow.md
  THIRD_PARTY_ACQUISITION.md
  backends/
    agent-reach.md
    opencli.md
    bb-browser.md
    web-access.md
    wechat.md
    jina.md
    xcrawl.md
    6551.md

metis/artifacts/rc-final/
  baseline.json
  gates.json
  golden/
  phases/
  backend-verification/
```

---

# 上游参考（执行时再次核实）

- Agent Reach: https://github.com/Panniantong/agent-reach
- Agent Paper Digest: https://github.com/momozi1996/Agent-Paper-Digest
- OpenCLI: https://github.com/jackwener/opencli
- bb-browser: https://github.com/epiral/bb-browser
- web-access: https://github.com/eze-is/web-access
- WeChat spider: https://github.com/klin-h/wechat_articles_spider （当前重定向至 `ghh1251/wechat_articles_spider`）
- Jina Reader: https://jina.ai/reader/
- MediaCrawler: https://github.com/NanmiCoder/MediaCrawler
- XCrawl: https://docs.xcrawl.com/
- Obsidian Web Clipper: https://github.com/obsidianmd/obsidian-clipper
- 6551 opennews/opentwitter：执行时按当前官方 Skill/API 文档核实 endpoint、费用和 token。

---

# 最后执行命令

不要先安装一堆第三方工具。

先严格完成：

```text
P00 → P01 → P02 → P03 → P04
```

把当前 RC 四个遗留问题关闭。

再做：

```text
P05 → P07
```

建立 Acquisition Fabric、Policy 和 Backend Registry。

之后才逐个接：

```text
Agent-Reach / OpenCLI / bb-browser / Jina / XCrawl / 6551 / WeChat
```

Metis Data 必须始终掌握：

```text
Plan
Policy
Routing
State
Raw
Provenance
Validation
Export
```

第三方工具只是可替换执行后端。

继续推进到 P31。任何第三方现实阻塞如实标记 BLOCKED，但不能因此停止其他可独立完成的任务。
