# Architecture Invariants（P00-004 / P29-003 实施清单）

每条不变量对应 tests/architecture/ 下一个自动检测（本轮实现）：

1. `test_default_search_requires_planning` — app.js 默认搜索必须传 planning_id（静态断言）+ 后端 bundle 驱动（integration）
2. `test_resume_no_empty_context` — access/resume.py 禁止 `access_context={}"/"access_context: {}` 字面量
3. `test_production_download_via_acquisition` — api/main.py 生产下载路径禁止直接调 `acquire_dataset`（仅 acquisition/service.py 与 adapters 内部允许）
4. `test_no_raw_write_in_adapters` — adapters 禁 raw_root/raw_dataset_dir/os.replace
5. `test_build_no_country_year_hardcode` — app.js 禁 `keys:["country","year"]`
6. `test_no_shell_true` — 全仓库（非测试）禁 `shell=True`
7. `test_no_mediacrawler` — 生产代码禁 import/vendor MediaCrawler
8. `test_untrusted_content_guard` — 网页文本不得直接进工具参数（guard 函数存在并被 router 使用）
