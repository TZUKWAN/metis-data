# Engineering Progress — Metis Data RC Taskbook

## Current Phase
完成 — RC Taskbook P00–P31 全部执行；最终验收 PASS

## Current Task
无

## Completed
- P00 基线/Reality Matrix/架构不变量清单（baseline.json、baseline-test-report、rc-reality-matrix.md、tests/architecture/README.md）
- P01 默认 PlanningBundle→Search 主链（前端 planning 状态+Review+修订；btn-search 走 planning_id；架构测试防回归）
- P02 AuthorizedAccessContext（transient 隔离+safe_dump）、BrowserSessionResolver、ResumeCoordinator 接 BrowserAuthBridge（删除空 context）、oauth/api_key resolver、cookie-gated E2E（0 二次点击）
- P03 BrowserSearchWorker ownership/幂等 close/orchestrator try/finally/takeover 转移/provider_tasks.browser_session_id/10 并发压测 0 孤儿
- P04 旧验收归档 docs/history/；gates.json 机器可读
- P05–P07 Fabric：领域 schema（CrawlPlan 边界校验、WebDocument/Social/Paper/Backend）、PolicyEngine/robots/rate limiter/injection guard、BackendAdapter/Registry/SafeCommandRunner/AcquisitionRouter
- P08–P10/P13/P15–P17 后端桥与策略（AgentReach/OpenCLI/bb health；Jina 公开 Markdown；XCrawl Vault token 未配置即拒；微信 plan/Vault/扫描边界；微博/知乎/B站 recipe；6551 双后端+fallback）
- P12 DirectWebReader+本地抽取+质量评估 fallback；P20 Crawl 引擎（状态机/canonicalizer/frontier/links/sitemap/incremental/checkpoint；本地站点 ≤25 页、0 robots 违规）
- P19 Clip/Obsidian；P21 metadata/table/JSON-LD 抽取；P22 fetch/extraction/backend provenance；P23 experience store（PROPOSED→VERIFIED→STALE）
- P24 UI：Acquisition Tasks/Backend Health/Provider Matrix/Build Plan 确认流
- P25 agent 工具严格 schema + 确认门；P26 WatchJob+ChangeDetector；P27 CDP/SSRF/附件/数据最小化；P28 quota/circuit breaker/1GB
- P29 CI + architecture tests（8 条不变量）
- P30 Goldens：GS-A/B/C/E/F/G/H PASS，GS-D BLOCKED（需用户扫码）
- P31 本报告 + THIRD_PARTY_ACQUISITION.md + docs 五篇

## Tests Executed
- 全量：174 tests，0 failed（junit-final.xml）
- ruff clean；secrets scan 0 findings；node --check app.js OK
- Golden：metis/artifacts/rc-final/golden/rc-report.json（7 场景）

## Real Verification
- books.toscrape.com 真实爬取 25 页（robots 尊重）
- arXiv API 真实论文搜索与增量 Digest
- HackerNews 真实 SocialRecord（+fixture 平台归一 Parquet）
- Zenodo 真实 DOI 数据获取
- cookie-gated 登录→恢复→采集 E2E

## Open Problems
- GS-D 微信真实采集需用户扫码（BLOCKED，链路代码完整）
- 部分外部后端真实计费 smoke 未执行（无账号），按 NOT_CONFIGURED/NOT_INSTALLED 诊断呈现

## Next Task
无 — 1.0 RC 收口完成
