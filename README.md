# Metis Data

**数据智能体**：把自然语言数据需求转化为**可验证、可追溯、可复现的数据资产**。

面向科研、政策研究、数据分析与 AI/ML 场景。核心链路：

```
自然语言需求
→ DataRequirement 结构化
→ Provider 选择（84 个平台统一 Registry）
→ 多平台并行搜索 → 候选归一化 / 去重 / 可解释推荐
→ 访问判断（匿名 API / 已有账号 / 自动注册 / 用户接管）
→ 真实下载（DownloadJob 门禁 + 流式 + SHA256）
→ Raw 不可变归档 → 16+ 格式解析 → Dataset Profile
→ 变量语义对齐 → 实体解析（ISO/中国行政区）→ 时间对齐
→ 安全 Join（cardinality 检查，m:m 默认阻止）→ 缺失/派生
→ 质量审计 → Provenance / 字段级 Lineage
→ Final Data Package（CSV/Parquet/XLSX + methodology + reproduce.py）
```

内置 **真实 headed 浏览器 Agent**（Playwright Chromium）：页面导航、点击、输入、下载捕获可实时观察；支持 Pause / 我来操作 / 交还 Agent；遇 CAPTCHA/MFA/受限协议/付费自动暂停交还用户（**无任何绕过代码**）。秘密全部存于 OS 级 Vault（Windows DPAPI），日志/事件流全局脱敏。

## 快速开始

```bash
# 1) 依赖（Python 3.11+）
pip install fastapi uvicorn sqlalchemy pandas pyarrow httpx pydantic openpyxl
pip install pyreadstat netCDF4 pyshp pycountry playwright pytest
python -m playwright install chromium

# 2) 配置
cp .env.example .env   # 按需填写，.env 不会入库

# 3) 生成测试 fixture（E2E 页面 + 多格式数据）
python scripts/gen_fixtures.py

# 4) 启动
cd metis/backend && uvicorn app.api.main:app --port 8300
# 打开 http://127.0.0.1:8300
```

> 大体积 fixture（112MB/108MB）不入库，由 `scripts/gen_fixtures.py` 现场生成。

## 测试

```bash
python -m pytest metis/backend/tests -q     # 55 个测试：单元/集成/E2E/安全/恢复/性能
python scripts/secrets_scan.py              # 秘密扫描（exit 0 = 干净）
python scripts/provider_smoke.py            # 真实 Provider 冒烟（需外网）
python scripts/golden_scenario.py           # 全链路 Golden Scenario（需外网）
```

## Provider 覆盖

PRD 中全部 **84 个数据平台**进入统一 Registry（`metis/backend/app/providers/providers.catalog.yaml`）：
每个平台声明 capabilities / auth / integration_level（P0–P7）/ last_verified_at / blocking_reason——**等级必须与真实验证一致，不虚报**。

已实现真实 HTTP adapter 并经外网冒烟验证搜索的平台包括：World Bank、Eurostat、ILOSTAT、OECD、UN Comtrade、US Census、Zenodo、Harvard Dataverse、Dryad、OSF、Figshare、data.gouv.fr、data.gov.uk、opendata.swiss、Hugging Face、Kaggle（匿名搜索）等 16+；匿名下载已验证：World Bank / Eurostat / ILOSTAT / UN Comtrade。

## 安全边界（明确不做）

CAPTCHA/MFA 绕过、指纹伪造、stealth 反检测、访问控制/付费规避、明文凭据、未标记插补、未核语义合并、无 cardinality 检查的 m:m join、Raw 覆盖——一律不实现。详见 `Metis_Data_PRD.md` §2.2 与验收报告。

## 文档

| 文件 | 说明 |
|---|---|
| `Metis_Data_PRD.md` | 产品需求文档 |
| `Metis_Data_Build_Task_List.md` | 263 个细粒度构建任务 |
| `Metis_Data_Acceptance_and_Agent_Prompt.md` | 总体验收要求 + Agent 提示词 |
| [`Metis_Data_v1_Final_Acceptance_Report.md`](Metis_Data_v1_Final_Acceptance_Report.md) | v1.0 最终验收报告（Verdict: PASS） |
| [`IMPLEMENTATION_PROGRESS.md`](IMPLEMENTATION_PROGRESS.md) | 实施进度记录 |
| `metis/artifacts/` | Golden Scenario / Provider 冒烟 / 性能基准 / UI 截图证据 |

## 架构

```
metis/backend/app/
  core/        配置 · 结构化日志(全局脱敏) · 错误码 · Workspace 规范
  domain/      Pydantic schema · 三大状态机(Search/Access/Build)
  db/          SQLAlchemy 模型 · Repository · 崩溃恢复
  providers/   Registry(84 平台) · Adapter 合同+能力守卫 · 20 个真实 adapter
  search/      需求解析 · Provider 选择 · 并行编排 · 去重 · 可解释推荐
  downloads/   DownloadJob 门禁 · 流式下载 · 内容识别 · 安全解压 · Raw 保护
  datasets/    16+ 格式 parser · Profile(chunked) · Variable Semantics
  builds/      实体/时间解析 · 安全 Join · 缺失/派生 · 分阶段检查点执行器
  provenance/  字段级 Lineage · 质量报告 · Methodology · reproduce.py · 交付包
  browser/     Playwright 运行时 · 6 级定位链 · Pause/TakeOver/Return · 介入检测
  auth/        DPAPI Vault · 独立密码生成 · 登录/注册执行器
  api/         FastAPI REST + WebSocket 事件流
metis/frontend/static/   三栏工作区 UI（原生 JS，无构建链）
```
