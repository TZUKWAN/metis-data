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

## Round 4 · 后续迭代（OECD/Comtrade adapter 修复 + 大文件路径 + 并发上限）

- ISSUE-401 (P1) 基类默认 descriptor 把门户页 source_url 当直链：OECD 下载物实为
  174KB 的 data-explorer HTML 页且已提交进 raw/（无扩展名绕过后缀嗅探）
  Fix 1: DownloadManager 内容优先守卫 — 任何非 .html 文件若内容为 HTML → INVALID_DOWNLOAD_CONTENT，
  永不进 raw/（v2 失败自动落 legacy 正确路径）
  Fix 2: OecdAdapter/UnComtradeAdapter 补 build_acquisition_descriptor 精确化
  （SDMX csvfilewithlabels / comtrade preview API，带安全文件名与扩展名）
- ISSUE-402 (P2) 大文件路径确认：OECD 走新 v2 descriptor → stream_to_file 有界流式；
  legacy 小载荷仍受 32MB SMALL_PAYLOAD_CAP 保护，超限诚实报 DOWNLOAD_TOO_LARGE
- ISSUE-403 (P2) 会话管线并发上限：METIS_CONVERSATION_MAX_CONCURRENCY（默认 3），
  槽满时任务持久化 QUEUED「排队中…」，重启 reconcile 覆盖 QUEUED 幽灵；测试 4 连跑稳定

验证: 全量 205 passed / 0 failed（新增 2 个任务管理器测试 + 1 个无扩展名 HTML 回归测试）

## Round 5 · 全产品模拟用户验收（Computer Use 真实操作 + 侧边浏览器真实 UI）

覆盖模块（清单见 metis/artifacts/final-closure/uat-manual/TESTPLAN.md）：
1. 启动链路（真实 Electron：启动屏→自动拉起后端→UI→连接绿点）
2. 顶栏（连接点/新会话/设置）
3. 输入区：空值禁用、纯空格禁用、Enter 发送+清空、Shift+Enter 换行不发送、
   2500 字超长输入、纯符号输入、快速连续提交
4. 任务生命周期：异步状态条即时出现、阶段文案、进度条、单任务取消、
   多任务并行+批量取消（2×CANCELLED）
5. 结果卡：计数头、状态徽标、预览(FOUND metadata)/返回、下载→READY（同 result_id）、
   READY 真实数据预览(17424 行×10 列)、CSV 2.5MB/XLSX 578KB 导出
6. 刷新恢复（消息+结果+READY 状态全恢复）、新会话隔离（UI 清空+服务端数据保留）
7. 设置弹窗（登录列表/隐私/关闭）、调试抽屉开合（Ctrl+Shift+D）
8. 探索性：运行中发消息、符号/超长/重复输入、连续预览开关、建议按钮
9. 持续观测：591 个请求 0 个 4xx/5xx、0 ERROR 日志、页面 0 JS 错误

发现并修复：
- UAT-BUG-01 (P1) 任务运行中新消息被静默丢弃（sending 锁持有至整条管线结束）
  根因修复：移除跨消息锁；同文本防抖由立即清空输入承担；过载由后端 QUEUED 门承担
  回归：conversation 套件 20 passed；实时 UI 验证 3 并行任务+逐个停止
- （伪影排除）符号消息"双发"系测试脚本重试所致，非产品缺陷

不可自然达路径（由确定性测试覆盖）：
- Auth 弹窗/浏览器监视：需"登录来源候选"，真实搜索当前只返回公开 API 源；
  覆盖于 tests/test_conversation_product.py（intervention 创建/probe 失败保持等待/
  登录后自动续传 READY）+ 架构不变量 + Electron UAT 15/15

环境约束（非产品问题）：
- 桌面被用户活跃使用（同名应用切换/窗口被关闭），Electron 突刺式验收仅完成
  启动链路+真实键鼠输入发送；其余 UI 交互在 ZCode 侧边浏览器对同一真实
  后端+UI 完成（用户此前明确要求的测试通道）
