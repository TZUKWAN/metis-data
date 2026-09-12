# Architecture — Metis Data 1.0 RC

## 生产主链（唯一路径）

```
UserRequest (自然语言)
→ POST /api/agent/planning            # app/agent/orchestrator.py::build_planning_bundle
    requirement → measurements → sources → query plans
    planning_source = llm | fallback | mixed（规则仅 fallback/validator）
→ PlanningRunRow 持久化                # db PlanningRunRow
→ POST /api/search/runs {planning_id}  # search/orchestrator.py 接受 bundle
    provider priorities / queries 来自 bundle
    discovery 策略分发：API adapter → BrowserSearchWorker（无 HTTP adapter 但有 recipe）
→ Candidates → dedup → evaluate        # search/dedup + recommend
→ POST /api/downloads                  # access/executor.resolve_access
    AccessJob 状态机（21 态，guard 持久化）
    PUBLIC → AUTHORIZED
    需登录 → Account Center login → resume_after_user → RESUME_COORDINATOR.resume_access_job
             → ACQUISITION.acquire 自动续原 DownloadJob（用户无需二次点击）
→ app/acquisition/service.py::ACQUISITION.acquire   # 唯一下载路径
    v2 build_acquisition_descriptor → stream_to_file（流式/断点续传/大小校验）
    legacy acquire_dataset 仅作兜底（记录事件）
→ MANAGER._verify_and_commit           # content sniff(64KB head) / SHA256 / raw atomic commit
→ Dataset Profile / Variable Semantics # datasets/
→ POST /api/builds/plan                # agent/build_planner.plan_build(_sync)
    BuildPlan（entity strategy/keys/aggregations 来自真实 Profile；unknown → NEEDS_REVIEW）
    blocking review points → 用户 approve（/api/builds/{id}/approve）
→ BuildExecutor.from_build_plan → run  # builds/executor（checkpoint 可恢复）
→ Validation / Provenance / Package    # builds/validation + provenance/package
```

## 关键模块

| 模块 | 职责 |
|---|---|
| app/agent/orchestrator.py | PlanningBundle 唯一编排入口 |
| app/search/orchestrator.py | 并行搜索（bundle 驱动；API/HTTP/BROWSER 三策略） |
| app/access/machine.py | 21 态 Access 状态机（合法迁移守卫） |
| app/access/resume.py | AccessResumeCoordinator（AUTHORIZED→acquire，幂等） |
| app/acquisition/service.py | 唯一生产获取路径（v2 descriptor → DownloadManager） |
| app/auth/browser_auth_bridge.py | Playwright cookies → httpx（登录态桥接） |
| app/browser/runtime.py | 真实 headed Chromium（locator 六级链、pause/takeover/return、WS 直播） |

## 恢复

进程重启 → db/recovery.reconcile_on_startup：search 重调度、download FAILED(可重试)、
build 从 checkpoint、注册/登录 in-flight → NEEDS_REVIEW。
