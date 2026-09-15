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

## Round 1 · Fix Log (commits 37d41c8 → 8510935)

### ISSUE-101..116 P0 closure
所有 §5 P0-01~P0-16 已关闭：
- Result 主链：ConversationResultLink（稳定 result_id）→ result_view_for_link → /api/conversations/{id}/results → 前端卡片（只吃 ResultView 字段）
- Preview：/api/results/{id}/preview 按 FOUND(metadata)/READY(real data)/FINAL(final csv) 分派
- Download：POST /api/results/{id}/download → Access → (Intervention→probe→auto-resume) → Acquisition → READY
- Build：plan_build → BuildExecutor.from_build_plan → FINAL link；一句话构建 → DISCOVER_ACQUIRE_BUILD 全链
- Task：ConversationTaskManager 兜底异常→FAILED + 友好文案；9 个中间态持久化；重启 reconcile
- WS /ws/conversations/{cid} + 轮询 fallback；取消端点真停管线
- 架构不变量 9 条（§25）+ 18 个确定性产品 E2E（§24）+ CI conversation-product-e2e job

### Round 2 · Live dogfood defects (found in real browser UAT, fixed in 8510935)
- ISSUE-201 (P1) 静态 JS 缓存导致升级后 UI 全挂（ws.onmessage 非 async 的 SyntaxError 被缓存放大）
  Fix: no-cache header + index.html 错误钩子 + cache-bust 参数
- ISSUE-202 (P1) World Bank JSON [pageinfo,[records]] 结构使 preview 500
  Fix: _json_records 解包；preview 解析失败降级为 metadata 视图（不再 500）
- ISSUE-203 (P2) 真实下载验证：SL.UEM.1524.FM.ZS 4.8MB → READY → 预览 17424 行 × 10 列 → CSV 导出 2.5MB 全通

## 当前验证状态
- 全量回归: 202 passed, 0 failed
- 产品 E2E: 18/18 (fixture LLM/provider/access/acquisition, CI 可复现)
- 真实浏览器 UAT: 发送→流式结果→预览→下载→READY→导出 全链 PASS（12 个真实 OECD/WB 候选）
- 真实服务器: http://0.0.0.0:8300 运行中

## Round 3 · Real LLM dogfood（§51）+ NEW ISSUE HUNT（commits e4496ff → b64f5dd）

### §51 Dogfood 全链（真实 Qwen3.6-35B-A3B + 真实网络）
消息：「帮我构建2015—2024年国家层面的青年失业率和人均GDP面板数据，优先使用国际组织官方数据」
- UNDERSTANDING(LLM 分类) → PLANNING(LLM 规划) → SEARCHING(真实 84-provider 检索，22 个候选流式渲染)
- → COLLECTING(真实下载 ILOSTAT 青年失业率 CSV + OECD PPP) → 2 READY
- → BUILDING(BuildPlanner+BuildExecutor) → FINAL「会话数据集」76921 行 × 20 列
- → 预览真实表格 → 导出 CSV 16.3MB (HTTP 200)

### Round 3 发现并修复
- ISSUE-301 (P0) goal 分类 LLM 把「国际组织」当作 provider 名注入 only_providers，
  直接覆盖检索优先级 → 只搜了一个不存在的源，0 候选
  Fix: PROVIDER_ALIASES 中文别名映射 + 注册表验证，无法解析的名字一律丢弃
- ISSUE-302 (P1) OECD 下载物为非表格文件(ORG)，profile/parse 抛 "No tables found" 使整个 Build 崩溃
  Fix: 构建前过滤无法解析出列的资产；回复中如实报告跳过数量
- ISSUE-303 (P2) status_mapper 孤儿模块（§27）→ 整合为唯一文案来源（RESULT_STATE_MAP/ERROR_MAP）
- ISSUE-304 (P1) runtime workspace（SQLite DB + 真实下载数据）被 git 跟踪
  Fix: .gitignore 补新布局路径 + git rm --cached（b64f5dd）

### NEW ISSUE HUNT 扫描结果（§55）
- stub scan: 无 TODO/NotImplemented/纯文本承诺（grep 证据空）
- orphan scan: projection/status_mapper/auth-modal/browser-monitor 均已接线
- button scan: 全部按钮有真实 handler（预览/下载/CSV/XLSX/停止/新会话/设置/我已完成/跳过）
- console/network: Electron UAT unexpected error = 0, unexpected 4xx/5xx = 0
- restart recovery: 真实证据 — 旧 workspace 任务被 reconcile 标为 FAILED_INTERRUPTED
- 视觉: 6 组截图（empty/working/results/preview/ready/3 分辨率）逐张人工审查通过

## 审计轮次（§56）
- Round A 功能链: 产品 E2E 18/18 + Electron UAT 15/15 + 真实 dogfood 全链 ✓
- Round B 故障/恢复: 失败收敛测试、probe 失败保持等待、取消、重启 reconcile、会话隔离 ✓
- Round C UX/视觉: 多分辨率截图 + 人工审查 + 无 alert/无内部 ID/毛玻璃克制 ✓
