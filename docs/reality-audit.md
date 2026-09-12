# Reality Audit — 1.0 RC 推进前基线（Phase A）

> 日期：2026-09-12 · 基准 commit fe90209 后（含 P15/P24/P25/Provider 证据轮）
> 判定词汇：WORKING / PARTIAL / DISCONNECTED / BROKEN / NOT_IMPLEMENTED。以源码为准，不引用旧报告。

| # | 能力 | 判定 | 源码依据 |
|---|---|---|---|
| 1 | LLM Planner 参与默认 SearchRun | **DISCONNECTED** | `api/main.py::start_search` 直接走 `select_providers/plan_queries` 规则链；`agent/requirement_planner.py` 只挂在 `/api/agent/*` 端点，不进 SearchRun |
| 2 | BrowserSearchWorker 进入 SearchOrchestrator | **DISCONNECTED** | `search/browser_worker.py` 存在且有测试；`search/orchestrator.py` worker 只调 `adapter.search_datasets`，无 strategy 分发 |
| 3 | AccessJob 登录后自动继续原 DownloadJob | **PARTIAL** | `account_login` API 会把最近 pending access job 转 AUTHORIZED，但不触发 acquisition；`access/executor.resume_after_user` 同样只改状态 |
| 4 | Browser 登录态传递给 acquisition | **NOT_IMPLEMENTED** | `/api/downloads` 的 `_run()` 调 `adapter.acquire_dataset(..., {})` 空上下文 |
| 5 | Provider v2 descriptor 进生产下载 | **DISCONNECTED** | `build_acquisition_descriptor` 仅有桥接+测试；生产路径仍 `acquire_dataset` |
| 6 | DownloadManager 负责所有字节 | **PARTIAL** | HTTP 流式走 MANAGER；但 adapters 内部仍各自 httpx 下载 + `write_small_payload`（有 32MB 上限），content sniff 在 `downloads/service.py` 用 `read_bytes()` 读整个文件再切片（大文件路径违规） |
| 7 | Build Planner 驱动 Build Executor | **DISCONNECTED** | `agent/build_planner.plan_build` 存在；`/api/builds` 仍由前端传 `keys=["country","year"]` 硬编码 |
| 8 | 前端写死 country/year | **BROKEN** | `app.js` btn-build-create 固定 `keys:["country","year"]` |
| 9 | legacy 双轨 | **PARTIAL** | `acquire_dataset`（legacy）与 `build_acquisition_descriptor`（v2）并存，主 API 走 legacy |
| 10 | Registry 分层 | **WORKING（有证据）** | 22 adapter；20 平台 registry last_verified_at+P1+；download 真实 PASS 8 个（artifacts/providers/summary.json） |
| 11 | Access 状态机自循环 | **BROKEN（边界）** | `executor.resolve_access` 对 UNKNOWN 调 `transition(INSPECTING→PUBLIC)` 合法，但存在 INSPECTING→INSPECTING 语义调用点（unknown 分支注释路径），FLOW 需审计 + 每迁移测试 |
| 12 | 重启恢复 | **WORKING** | `db/recovery.py` reconcile（search/download/build/browser NEEDS_REVIEW） |
| 13 | Agent Chat 状态问答 | **WORKING** | `/api/agent/chat` 确定性回答基于真实 DB |
| 14 | Entity Resolution 泛化 | **PARTIAL** | Country/China resolver WORKING；无 EntityResolver 协议、无通用串值 resolver（firm/university → NEEDS_REVIEW 缺失） |

## 本轮 P0 收口顺序（Phase B–H）
B PlanningBundle 主链（agent/orchestrator.py + SearchRun 接 planning_id）
C BrowserSearchExecutor 三策略进 orchestrator
D/E Access resume 闭环 + AuthorizedAccessContext + BrowserAuthBridge
F/G AcquisitionService 唯一下载路径 + 流式 sniff（禁 read_bytes 于大文件路径）
H Build Planner 接 /api/builds（前端去 country/year 硬编码）
