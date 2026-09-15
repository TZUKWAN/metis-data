# Metis Data — Continuous Closure Engineering Progress

> Taskbook: `Metis_Data_Continuous_Closure_Autonomous_Agent_Master_Prompt.md`
> Baseline HEAD: `c7f99a99620dc7d133237c1a1962829b731c09ca`
> Rule: P0/P1 OPEN = 0 才允许生成最终验收。HOLD 不是停止命令。

## Round 1 · Independent re-audit of P0-01 ~ P0-16 (against real source @ c7f99a9)

| P0 | 审计结论（真实源码证据） | Status |
|---|---|---|
| P0-01 Results Pane 未接上 | `main.py` conversation POST pipeline 只把 candidates 塞进 message.data_json；前端 `conversation.js` 收到 COMPLETE 后只取 assistant 文本，`onResults({searchDone})` 不传数据；无 `conversation_result_links` 写入，无 GET /results | OPEN |
| P0-02 前端吃 Candidate raw schema | `results.js` 直接读 `c.candidate_id/time_coverage/reason/provider_id/license`；projection.py 存在但 production 零调用（孤儿模块） | OPEN |
| P0-03 Preview ID 类型错误 | `results.js` → `window._preview(candidate_id)` → `/api/artifacts/{candidate_id}/preview` → 必 404 | OPEN |
| P0-04 Download 主链不统一 | `results.js` 调 `window._download` — **该函数从未定义，下载按钮是无 handler 的假按钮** | OPEN |
| P0-05 FIND_AND_DOWNLOAD 假执行 | `conversation_orchestrator.py:_discover_and_download` = `_discover()` + 文本"正在获取排名靠前的数据"，无任何 acquisition 调用 | OPEN |
| P0-06 BUILD_DATASET stub | `_build()` 返回固定文本"请先告诉我要查找什么数据"，从不调用 BuildPlanner/BuildExecutor | OPEN |
| P0-07 一句话目标误判 | `_classify` 关键词表："面板"→BUILD_DATASET，无 READY artifact 时落入 stub；无 UserGoal/DISCOVER_ACQUIRE_BUILD | OPEN |
| P0-08 REFINE 丢上下文 | `_refine()` 直接 `_discover(cid, text)`，不加载 previous planning | OPEN |
| P0-09 Explain 全局串数据 | `_explain()` 用 `REPO.list_search_runs(1)` 全局最近 run，非 conversation scoped | OPEN |
| P0-10 ResultLink 非生产关系 | `ConversationResultLinkRow` 建表但全仓库无一处 INSERT；candidate→artifact 换 ID | OPEN |
| P0-11 后台异常不收敛 | `_pipeline()` 无 try/except，LLM/搜索异常 → task 永远 UNDERSTANDING | OPEN |
| P0-12 中间态不落库 | task 只写 UNDERSTANDING（创建时）→ COMPLETE（结束时），无 PLANNING/SEARCHING/COLLECTING/WAITING_USER | OPEN |
| P0-13 Auth Modal 无 Intervention | 无 conversation_interventions 表；auth-modal.js 是纯静态 HTML，onDone 无后端动作 | OPEN |
| P0-14 我已完成不 probe | auth-modal.js `#auth-done.onclick = () => root.innerHTML=""` — 直接关闭，无 probe | OPEN |
| P0-15 登录后不自动续 | 无 resume 逻辑存在 | OPEN |
| P0-16 UAT 不覆盖主链 | 现有 UI 测试只验证 two-pane 可见 | OPEN |

## ISSUE Log

### ISSUE-101 (P0) Download 按钮无 handler（假按钮）
Files: `frontend/static/js/results.js`
Fix: Result API 主链 + requestResultDownload(result_id)

### ISSUE-102 (P0) projection.py / status_mapper.py 孤儿模块
production 零 import。接线到 Result API。

（后续轮次持续追加）
