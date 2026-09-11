# Engineering Progress — Metis Data Productization

## Current Phase
Phase 1（LLM Data Agent Core）

## Current Task
P01-001..005

## Completed

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
- `python -m pytest metis/backend/tests --tb=no -q` → 55 passed（baseline）
- `python -m pytest metis/backend/tests/test_p00_productization.py -q` → 2 passed

## Evidence
- metis/artifacts/productization/*

## Blockers
- 无

## Next Task
P01-001 agent 模块目录
