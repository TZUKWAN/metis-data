# Metis Data 1.0 RC — Engineering Delivery Acceptance（最终收口轮）

> 生成：2026-09-13 · 基准任务书：`Metis_Data_Autonomous_Acquisition_RC_Taskbook.md`
> 本报告只针对**当前 HEAD** 的一次完整验证。历史报告已归档 `docs/history/`（P04-001）。

## 1. Version

- branch: main
- HEAD: 见 `git log -1`（本轮收口 commit）
- CI: GitHub Actions `CI (P28)` — lint / unit-integration / security / frontend-smoke / performance / architecture-tests 全绿（run 记录见 GitHub Actions）

## 2. 测试

- 全量：**174 tests，0 failed，0 errors**（`metis/artifacts/rc-final/junit-final.xml`）
- ruff 0.16：All checks passed
- secrets scan：0 findings（`scripts/secrets_scan.py`）
- node --check app.js：通过
- architecture invariants（P29-003）：8 条全部通过（tests/architecture/）

## 3. RC 遗留主链缺口（P01–P03）— 全部关闭

| 缺口 | 修复 | 证据 |
|---|---|---|
| 前端默认搜索走旧 rule-only 路径 | btn-search 无 planningId 时自动 Planning；请求体含 planning_id（P01-004） | app.js；tests/architecture::test_default_search_requires_planning |
| Planning 审查/修订 | Planning Review UI（unit/geo/time/frequency/variables 可编辑）；修改生成**新 planning_id**，历史保留（P01-003） | app.js runPlanning/replanFromEdits；STATE.planningHistory |
| ResumeCoordinator 空 access_context | P02-003：BrowserSessionResolver（live→Vault restore→probe）+ BrowserAuthBridge cookies + oauth/api_key refs；browser_download_only 走 Browser Download | access/resolver.py、access/resume.py |
| BrowserSearchWorker 孤儿会话 | ownership（worker/task/user）+ 幂等 close + orchestrator try/finally + takeover 转移所有权（P03-001/002） | search/browser_worker.py；tests/test_p03_lifecycle.py |
| SearchRun 绑定 browser_session_id | provider_tasks.browser_session_id 列 + upsert 透传 + 事件流（P03-003） | db/models.py、orchestrator.py |
| 并发泄漏 | 10 并发搜索 + 30% 取消压测：非 user-owned 会话归零（P03-004） | tests/test_p03_lifecycle.py |

## 4. Autonomous Acquisition Fabric（P05–P07，P12–P26）

| 层 | 内容 | 状态 |
|---|---|---|
| 领域模型 | AcquisitionTaskType(14)、CrawlPlan（强制 max_pages/depth/duration/bytes）、WebDocumentArtifact、SocialPost/Comment/Profile、PaperRecord、BackendCapability/Descriptor | **PASS** |
| 合规 | CrawlPolicyEngine（域名 allow/deny/review）、robots.txt 服务（TTL 缓存、BLOCKED_ROBOTS）、DomainRateLimiter（429 Retry-After）、Human Intervention Policy（复用 runtime WAITING_USER）、license/redistribution 元数据、Prompt Injection guard（UntrustedContent + 参数 allowlist） | **PASS** |
| Backend 层 | BackendAdapter 协议（UnsupportedCapability、timeout/cancel）、BackendRegistry（detect-only，不自动安装）、SafeCommandRunner（argv allowlist、无 shell、输出上限）、AcquisitionRouter（官方→HTTP→Reader→Browser→Crawl，fallback 链记录） | **PASS** |
| 后端桥 | AgentReach/OpenCLI/bb（health + 只读 read/search；未安装→NOT_INSTALLED）、Jina（公开 URL Markdown；无 key 基础模式）、XCrawl（token 在 Vault；未配置→NOT_CONFIGURED）、OpenNews/OpenTwitter（同） | **PASS**（未安装/未配置为按设计；真实 smoke 见 golden_rc GS-C） |
| 网页读取 | DirectWebReader（raw immutable + markdown + hash）、本地主内容抽取、质量评估（thin/JS-shell → fallback）、Jina fallback | **PASS** |
| 微信 | WeChatOfficialAccountPlan（上限 50/账号）、扫码由用户完成、storage_state→Vault、正文→WebDocument→数据集 | **代码完整；真实采集 BLOCKED（需用户扫码授权）** |
| 自主爬取 | CrawlJob 状态机、URL canonicalizer、Frontier checkpoint、link discovery、sitemap/RSS、fetch router、incremental（ETag/hash）、CrawlJobRunner | **PASS**（本地 50 页站点 ≤25 页上限、0 robots 违规、0 重复 canonical） |
| 社媒 | SocialSourceAdapter 合同、SocialQueryPlan（时间窗+上限）、原始+normalized 双层、跨平台 probable_duplicate 标记 | **PASS** |
| 论文 | PaperWatchPlan、arXiv 真实搜索、ranker（tiers+reasons）、Digest 增量（第二次 0 重复）、watch 调度 | **PASS** |
| 结构化抽取 | Metadata/Table/JSON-LD/LLM structured（evidence 必带） | **PASS** |
| 采集 provenance | FetchProvenance / ExtractionProvenance / BackendProvenance / crawl methodology | **PASS** |
| Clip/Export | WebClipTemplate、ClipService、Obsidian exporter（路径 allowlist、穿越拒绝） | **PASS** |
| Watch | WatchJob + ChangeDetector（无变化不通知） | **PASS** |
| Agent 工具 | 10 个严格 schema 工具（web.search…crawl.resume）；run_shell 策略性拒绝；逐变量聚合；QuotaManager | **PASS** |
| UI | Acquisition Tasks / Backend Health / Live Browser 复用面板 | **PASS** |

## 5. Golden Scenarios（P30）

| 场景 | 状态 | 证据 |
|---|---|---|
| GS-A 默认 Planning→Search（词典外城市需求） | PASS | planning_id → SearchRun COMPLETED，bundle 被 query_plan 携带 |
| GS-B 登录→自动续下载（0 二次点击） | PASS | tests/test_p02_auth_resume_e2e.py + golden_rc |
| GS-C 公开网站自主 Crawl | PASS | books.toscrape.com 25 页，robots 尊重 |
| GS-D 微信小规模 | BLOCKED | 需用户扫码授权；链路代码+测试完整，人工接管路径存在 |
| GS-E 双平台社媒 → Parquet | PASS | HN 真实 + fixture，SocialRecord 统一 |
| GS-F 论文 Watch 增量 | PASS | arXiv 两次运行，第二次 0 新增重复 |
| GS-G Web→结构化数据集（20 页，字段 evidence） | PASS | |
| GS-H 后端 fallback 链 | PASS | direct 失败 → reader 成功，链路记录 |

## 6. Gate 对照（G01–G20）

全部 **PASS**（G11 中国核心平台 = BLOCKED，仅 GS-D 类用户授权场景受扫码限制；本轮 GS-C/GS-E/GS-G 已覆盖自主采集主体能力）。逐项 evidence 见 `metis/artifacts/rc-final/gates.json` 与上文分 Phase 表格。

## 7. Final Verdict

# **PASS — Metis Data 1.0 RC**

主链唯一、可观察、可授权、可恢复、可追溯、可复现。已知限制（如实）：
- GS-D 微信真实采集与 GS-2 中国官方面板需用户扫码授权或非本网络环境（403 反爬，audit 有据）；
- Jina/XCrawl/6551 外部服务按"未安装/未配置"诊断呈现，真实计费 smoke 未执行（无账号）；
- 部分 Tier 1 平台 integration level 仍为 P1/P2（registry 如实标注，audit 含 last_verified_at）。
