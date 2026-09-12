# RC Reality Matrix（Phase A/P00-003）

判定维度：IMPLEMENTED（代码存在）/ CONNECTED（已接主链）/ TESTED_FIXTURE / TESTED_REAL / PRODUCTION_READY。
证据以源码路径 + 测试名为准（基线 d956c2d）。

| 能力 | IMP | CONN | FIXTURE | REAL | PROD | 证据/缺口 |
|---|---|---|---|---|---|---|
| Planning→Search 主链 | ✅ agent/orchestrator.py | ⚠️ 仅 planning_id 路径；前端默认按钮仍 requirement_id | ✅ test_planning_chain | ❌ | ❌ | P01-004 关闭 |
| Browser Search | ✅ browser_worker.py | ⚠️ orchestrator 有策略分发但 BROWSER recipe 平台=0 | ✅ test_p15_browser_search | ❌ | ❌ | P03 生命周期 + 真实 recipe |
| Access/Auth 状态机 | ✅ access/machine.py | ✅ /api/downloads→resolve_access | ✅ test_p04_access | 部分（fixture 登录） | ⚠️ | P02 接 auth context |
| Resume 闭环 | ⚠️ resume_after_user 只改状态 | ❌ access_context={} 空 | ❌ | ❌ | ❌ | P02-003/005 |
| Acquisition 路径 | ✅ acquisition/service.py | ⚠️ /api/downloads 已接；resume 未接 | ✅ test_acquisition_service | ❌ | ⚠️ | Phase F |
| DownloadManager | ✅ downloads/service.py | ✅ | ✅ test_p11 | ✅ 112MB/1GB | ✅ | sniff 需流式（P-G） |
| Build 链 | ✅ from_build_plan | ⚠️ /api/builds/plan 已加；前端仍 keys 硬编码 | ✅ test_build_planning_chain | ✅ GS-1 | ⚠️ | P24 前端 |
| Provider Registry | ✅ 22 adapter | ✅ | ✅ smoke | ✅ 20 搜索/8 下载验证 | ✅(20 平台 P1+) | Tier1 扩展 |
| Crawler | ❌ | ❌ | ❌ | ❌ | ❌ | P20 全新 |
| 社媒/论文/公众号 | ❌ | ❌ | ❌ | ❌ | ❌ | P14/15/18 |
| UI 状态 | ⚠️ | ⚠️ | — | — | ❌ | P01-003/024 |
