# Architecture Baseline (P00-001)

日期：2026-09-11
范围：`D:\数据智能体` 工作区递归扫描结果。

## 1. 工作区现状

扫描结果：仓库初始状态仅包含三份需求文档，无任何既有应用代码。

| 文件 | 说明 |
|---|---|
| `Metis_Data_PRD.md` | 产品需求文档（v1.0） |
| `Metis_Data_Build_Task_List.md` | 263 个细粒度任务（P00–P19） |
| `Metis_Data_Acceptance_and_Agent_Prompt.md` | Part A 总体验收 + Part B 实施提示词 |

结论：**greenfield 项目**。PRD 要求“复用现有 Browser、Agent、事件流等能力”——工作区不存在这些能力，因此全部自建；但复用本机已安装的成熟运行时（见 §3）。

## 2. 环境能力盘点（实际验证）

| 能力 | 状态 | 证据 |
|---|---|---|
| Python | 3.13.2 (miniconda) | `python --version` |
| Node | v25.6.0 | `node --version` |
| Git | 2.54.0.windows.1 | `git --version` |
| FastAPI/uvicorn | 已安装 | import 验证 |
| SQLAlchemy | 已安装 | import 验证 |
| pandas / pyarrow / numpy / scipy | 已安装 | import 验证 |
| httpx / requests | 已安装 | import 验证 |
| pydantic / yaml / openpyxl / bs4 / lxml | 已安装 | import 验证 |
| playwright | 已安装（Python 包） | import 验证 |
| pytest | 已安装 | import 验证 |
| pyreadstat / netCDF4 | 本会话安装成功 | pip install |
| 外网 | 可达 | World Bank API HTTP 200 |

## 3. 技术选型（architecture decision）

| 决策 | 选择 | 理由 |
|---|---|---|
| 后端 | Python 3.13 + FastAPI + uvicorn | 数据科学生态（pandas/pyarrow）为合成引擎刚需；asyncio 支撑并行搜索 |
| 数据库 | SQLAlchemy + SQLite（`metis/workspace/metis.db`） | 零部署依赖；Repository 层隔离，后续可换 PostgreSQL |
| 数据引擎 | pandas + pyarrow（Parquet 为内部列式格式） | PRD §34 推荐 Parquet |
| Browser | Playwright 驱动真实 headed Chromium | PRD §12 强制真实可见浏览器；locator 链原生支持 role/name → CSS → text |
| 前端 | FastAPI 托管的静态 SPA（原生 JS + WebSocket 事件流），无 Node 构建链 | 减少构建复杂度；实时事件流/实时 Browser 视图用 WS 实现 |
| 测试 | pytest + 本地 fixture HTTP server（127.0.0.1:8310） | CI 不依赖实时外网（Task List 规则 §36） |
| Vault | Windows DPAPI（CryptProtectData，ctypes）+ keyring（如可用） | PRD §14 桌面端优先 OS 安全存储；**无明文 fallback** |

## 4. 模块边界（P00-04 建立于 `metis/backend/app/`）

| 模块 | 职责 | 对应一级能力 |
|---|---|---|
| `core` | 配置、结构化日志、错误码、Workspace 路径规范 | 基线 |
| `domain` | DataRequirement/Provider/DatasetCandidate/DatasetArtifact/VariableSemantic/DownloadJob/Build/CredentialRef schema 与状态机 | 领域模型 |
| `db` | SQLAlchemy 模型、Repository、迁移、任务恢复 | 持久化 |
| `providers` | ProviderRegistry、catalog yaml、adapter contract、capability guard、health、integration matrix | Discovery |
| `search` | Requirement parser/validator、provider selector、query planner、并行 orchestrator、normalizer、去重、推荐 | Discovery |
| `downloads` | DownloadJob 门禁、流式下载、Browser 下载捕获、校验、安全解压、Raw immutable guard、格式路由 | Acquisition |
| `datasets` | 全格式 parser、Profile、Variable Semantics | Dataset Intelligence |
| `builds` | Build plan、实体/时间对齐、join、missing、derived、DAG 执行、checkpoint | Synthesis |
| `provenance` | source/transform/field lineage、checksum、package、reproduce | Provenance |
| `browser` | Playwright runtime、locator 策略链、action event stream、pause/takeover/return、介入检测 | Browser & Access |
| `auth` | Data Identity、SecretStore/Vault、密码生成、AccountStatus、登录/注册执行器 | Browser & Access |
| `api` | FastAPI routers（对外 REST/WS，UI 唯一入口） | UI 集成 |
| `events` | UI 事件流总线（所有模块经此推送前端） | 可观测性 |

依赖方向：`api → (search|downloads|builds|browser|auth|providers|datasets|provenance) → (domain, db, core)`；UI 不直接调用 provider 私有方法（PRD §8）。

## 5. 可复用/需改造/不存在 对照

| 项 | 判定 | 路径/证据 |
|---|---|---|
| 既有应用代码 | 不存在 | 工作区仅 3 个 md |
| Python 数据栈 | 可复用 | miniconda site-packages（pandas 等） |
| Playwright 浏览器二进制 | 需验证安装 | `playwright install chromium` 待执行 |
| OS 凭据库 | 可复用（Windows DPAPI） | win32 API，ctypes 直调 |
| 测试框架 | 可复用 | pytest |
