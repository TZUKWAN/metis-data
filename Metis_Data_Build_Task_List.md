# Metis Data 产品构建任务清单（极细粒度执行版）

> 版本：v1.0  
> 日期：2026-09-11  
> 用途：直接交给 Coding Agent 顺序执行。每一个任务都是最小可验收单元；不得以“基本完成”“先占位”“后续再补”标记 DONE。

---

# 0. 强制执行规则

1. 严格按 Task ID 推进；前置依赖不满足时保持 BLOCKED。
2. 每个任务完成后必须立刻运行该任务验收；任何验收失败，状态不得为 DONE。
3. 每个任务完成时必须在 `IMPLEMENTATION_PROGRESS.md` 记录修改文件、测试命令、结果、遗留问题和下一任务。
4. 禁止用假 UI、静态假数据、placeholder、TODO、pass 冒充实现。
5. Provider capability 必须如实声明。客观外部限制可以降级，但必须写明阻塞证据。
6. 所有平台至少进入 Registry 并实现 P1 搜索；存在公开稳定下载能力的平台应达到 P4；账号型平台按文档目标实现 P5/P6。
7. 不做 CAPTCHA/MFA 绕过、stealth、指纹伪装或访问控制规避。
8. Raw 不得覆盖；同名变量不得未经语义核验直接合并；m:m 默认禁止。
9. API 可稳定获取时优先官方 API；网页交互需求由 Live Browser 完成。
10. 每个 Phase 结束必须执行 Phase Regression Gate。

## 状态

- `TODO`：未开始
- `IN_PROGRESS`：执行中
- `BLOCKED`：外部/前置依赖阻塞
- `FAILED`：实现或验收失败
- `DONE`：实现完成且全部单项验收通过

---
# P00 · 工程基线与仓库约束

阶段目标：先固定工程结构、测试门禁、日志和安全底座，避免后续边做边重构。

## P00-001 · 遍历现有仓库并形成基线清单

**目标**：准确掌握现有前端、后端、Agent、Browser、文件、数据库和任务系统，优先复用已有能力。

**前置依赖**：无

**实施动作**：
1. 递归扫描仓库目录和关键配置
2. 定位应用入口、路由、状态管理、Agent tool、browser/computer-use、storage、database、test、CI
3. 输出 architecture-baseline.md，逐项说明可复用/需改造/不存在

**必须产物**：
- architecture-baseline.md

**单项验收标准**：
- [ ] 文档覆盖上述全部模块
- [ ] 每个判断给出实际文件路径
- [ ] 未改业务代码前完成此任务

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P00-002 · 记录起始版本

**目标**：保证可回退和审计。

**前置依赖**：无

**实施动作**：
1. 记录当前 branch/commit
2. 创建 Metis Data 开发分支或等价隔离
3. 确认工作区初始 diff 并记录已有未提交改动

**必须产物**：
- baseline-version.md

**单项验收标准**：
- [ ] 能用 commit 恢复改造前状态
- [ ] 不覆盖用户已有未提交修改

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P00-003 · 建立环境变量模板

**目标**：统一配置且杜绝秘密进入仓库。

**前置依赖**：无

**实施动作**：
1. 创建/更新 .env.example
2. 列出 DB、workspace、browser、provider key、vault 等配置
3. 更新 .gitignore 覆盖 .env、auth state、session、download temp

**必须产物**：
- .env.example
- .gitignore

**单项验收标准**：
- [ ] 仓库 secrets scan 不发现真实凭据
- [ ] 新环境能根据模板知道所有必需配置

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P00-004 · 建立模块目录边界

**目标**：给每个一级能力唯一代码归属。

**前置依赖**：无

**实施动作**：
1. 建立/确认 requirement、providers、browser、auth、downloads、datasets、builds、provenance、ui-events 模块
2. 禁止 Provider 私有逻辑散落 UI
3. 为每个模块写短 README 描述职责

**必须产物**：
- 模块目录
- 模块 README

**单项验收标准**：
- [ ] 不存在两个并行实现相同一级能力的目录
- [ ] 依赖方向清晰

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P00-005 · 建立统一测试入口

**目标**：所有任务必须可自动验收。

**前置依赖**：无

**实施动作**：
1. 建立 unit/integration/contract/e2e/security/performance 分类
2. 提供单独命令和全量命令
3. CI 使用同一套命令

**必须产物**：
- test scripts

**单项验收标准**：
- [ ] 人为加入失败测试时 CI 必须失败
- [ ] 空基线 smoke 测试通过

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P00-006 · 建立 lint/typecheck/format 门禁

**目标**：防止轻量模型积累不可维护代码。

**前置依赖**：无

**实施动作**：
1. 配置项目语言对应 formatter/linter/type checker
2. 加入 CI
3. 禁止 type error 通过发布

**必须产物**：
- quality config

**单项验收标准**：
- [ ] lint/typecheck/format-check 均有可执行命令
- [ ] CI 会因错误失败

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P00-007 · 建立结构化日志

**目标**：所有任务动作可追踪且可脱敏。

**前置依赖**：无

**实施动作**：
1. 统一 task_id/provider_id/action/status/duration/error_code 字段
2. 实现敏感字段 redaction
3. 禁止业务层直接输出密码、token、cookie

**必须产物**：
- logging module
- redaction tests

**单项验收标准**：
- [ ] 测试 password/token/cookie/API key 全部被遮蔽
- [ ] 可按 task_id 聚合日志

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P00-008 · 建立错误码体系

**目标**：让 Agent/UI 能明确区分可重试和需用户介入。

**前置依赖**：无

**实施动作**：
1. 定义 Provider/Auth/Browser/Download/Parse/Build/Validation/Security 错误域
2. 错误对象至少含 code/message/retryable/safe_details
3. 禁止只抛字符串异常

**必须产物**：
- error taxonomy

**单项验收标准**：
- [ ] PRD 中主要失败场景均有对应错误域
- [ ] UI 可依据 retryable 选择操作

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P00-009 · 建立 Workspace 路径规范

**目标**：隔离 raw/intermediate/final 和不同任务。

**前置依赖**：无

**实施动作**：
1. 定义 task/build 目录结构
2. 实现安全 path resolver
3. 加入路径穿越防护

**必须产物**：
- workspace module

**单项验收标准**：
- [ ] ../ 等越权路径被拒绝
- [ ] 不同 task 文件不会互相覆盖

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P00-010 · 建立 IMPLEMENTATION_PROGRESS.md

**目标**：让长周期 Agent 始终知道当前任务。

**前置依赖**：无

**实施动作**：
1. 写当前 Phase/Task/已完成/修改文件/测试/阻塞/下一任务模板
2. 每完成一个最小任务立即更新

**必须产物**：
- IMPLEMENTATION_PROGRESS.md

**单项验收标准**：
- [ ] 任意时刻都能从文件确定最低未完成任务
- [ ] 状态不得与测试结果矛盾

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

# P01 · 领域模型、数据库与状态机

阶段目标：建立全系统共享的数据结构和可恢复任务状态。

## P01-001 · 实现 DataRequirement schema

**目标**：让自然语言数据需求可持久化、校验和编辑。

**前置依赖**：无

**实施动作**：
1. 实现研究问题、数据单位、population、geography、time_range、frequency、变量角色、来源偏好、license 等字段
2. 实现 validation 和序列化
3. 保留原始用户请求

**必须产物**：
- DataRequirement model

**单项验收标准**：
- [ ] 合法 fixture 序列化往返一致
- [ ] 倒置时间范围等明显错误被拒绝
- [ ] 允许非关键字段缺失

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P01-002 · 实现 Provider schema

**目标**：统一平台元数据和 capability。

**前置依赖**：无

**实施动作**：
1. 实现 id/name/category/region/trust/status/capabilities/auth/formats/integration_level/last_verified
2. 限定唯一 provider_id

**必须产物**：
- Provider model

**单项验收标准**：
- [ ] 全 provider catalog 可被 schema 验证
- [ ] 重复 id 加载失败

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P01-003 · 实现 DatasetCandidate schema

**目标**：统一搜索结果。

**前置依赖**：无

**实施动作**：
1. 实现 title/description/provider/source_ref/url/doi/license/access/coverage/variable_hints/files 等
2. 保留 raw_metadata_ref

**必须产物**：
- DatasetCandidate

**单项验收标准**：
- [ ] 三个不同 Provider fixture 能归一化
- [ ] 未知字段用 unknown/null 而非伪造

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P01-004 · 实现 DatasetArtifact schema

**目标**：严格区分候选与已下载数据。

**前置依赖**：无

**实施动作**：
1. 记录 artifact_id/files/checksum/format/version/raw_path/source_candidate
2. 要求本地文件可验证

**必须产物**：
- DatasetArtifact

**单项验收标准**：
- [ ] 未下载 Candidate 不能创建 completed Artifact
- [ ] Artifact 文件缺失时 validation 失败

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P01-005 · 实现 VariableSemantic schema

**目标**：支持变量语义和口径比较。

**前置依赖**：无

**实施动作**：
1. 实现 canonical/original/definition/unit/scale/coding/frequency/geography/population/price_basis/currency/source/confidence

**必须产物**：
- VariableSemantic

**单项验收标准**：
- [ ] 可表达 current-price GDP 与 constant-price GDP
- [ ] 可表达 Likert/value labels

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P01-006 · 实现 DownloadJob schema

**目标**：每次下载都有明确 manifest。

**前置依赖**：无

**实施动作**：
1. 记录 provider/dataset/source/version/access/license/expected_files/status/timestamps/bytes

**必须产物**：
- DownloadJob

**单项验收标准**：
- [ ] 任何 downloader 必须绑定 job_id
- [ ] job 可重启恢复

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P01-007 · 实现 Build schema

**目标**：描述多源合成全过程。

**前置依赖**：无

**实施动作**：
1. 记录 inputs/target unit/keys/stages/options/checkpoints/outputs/warnings/provenance
2. 支持版本号

**必须产物**：
- Build model

**单项验收标准**：
- [ ] Build 配置可完整持久化
- [ ] 修改 pipeline 参数会形成新版本或明确变更记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P01-008 · 实现 CredentialRef schema

**目标**：数据库只保存秘密引用。

**前置依赖**：无

**实施动作**：
1. 仅保存 provider/account/secret_id/session_ref/metadata
2. schema 禁止 password/token 字段

**必须产物**：
- CredentialRef

**单项验收标准**：
- [ ] 数据库 dump 中无明文秘密

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P01-009 · 实现任务状态机

**目标**：禁止非法阶段跳转。

**前置依赖**：无

**实施动作**：
1. 实现 Search/Access/Build 三套状态机
2. 增加 transition guards
3. 非法转移产生固定错误

**必须产物**：
- state machines

**单项验收标准**：
- [ ] CREATED 不能直接跳 COMPLETE
- [ ] 所有合法路径有单测

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P01-010 · 建立数据库迁移和 Repository

**目标**：让所有核心状态可持久化。

**前置依赖**：无

**实施动作**：
1. 创建 migration
2. 建立 requirement/provider/candidate/download/build/account repositories
3. 事务化写入关键多对象操作

**必须产物**：
- migrations
- repositories

**单项验收标准**：
- [ ] 空库一键迁移成功
- [ ] 事务失败不留下半状态
- [ ] 测试库可重建

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P01-011 · 实现任务恢复服务

**目标**：应用重启后不丢搜索、下载和 Build。

**前置依赖**：无

**实施动作**：
1. 启动扫描非终态任务
2. 依据 checkpoint 恢复
3. 无法安全恢复的 Browser 外部动作进入 NEEDS_REVIEW

**必须产物**：
- recovery service

**单项验收标准**：
- [ ] 强杀进程后重启不出现假 COMPLETE
- [ ] 不可重放外部动作不被重复提交

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

# P02 · Provider Registry 与 Adapter 合同

阶段目标：建立平台接入的唯一标准。

## P02-001 · 创建 providers.catalog.yaml

**目标**：登记全部目标平台。

**前置依赖**：无

**实施动作**：
1. 按 PRD 全量平台录入
2. 每项填写 category/region/homepage/目标接入等级
3. ID 使用稳定 snake_case

**必须产物**：
- providers.catalog.yaml

**单项验收标准**：
- [ ] PRD 平台 100% 出现
- [ ] provider_id 100% 唯一

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P02-002 · 实现 Registry Loader

**目标**：启动加载并验证 Provider。

**前置依赖**：无

**实施动作**：
1. schema validation
2. 按 capability/category/region 查询
3. 加载错误给出具体 provider

**必须产物**：
- ProviderRegistry

**单项验收标准**：
- [ ] 全部合法 catalog 可加载
- [ ] 缺字段和重复 ID 测试失败

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P02-003 · 定义 ProviderAdapter contract

**目标**：上层不得直接依赖网站细节。

**前置依赖**：无

**实施动作**：
1. 定义 search/metadata/preview/access/acquire
2. 定义可选 login/register/oauth/api_key
3. 定义 timeout/cancel/error 语义

**必须产物**：
- ProviderAdapter interface

**单项验收标准**：
- [ ] mock adapter 能跑 search→metadata→access→acquire
- [ ] 不支持方法返回 UnsupportedCapability

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P02-004 · 实现 Capability Guard

**目标**：严格按照平台真实能力执行。

**前置依赖**：无

**实施动作**：
1. 调用前校验 integration_level/capability
2. 未实现能力不得 silent fallback 为成功

**必须产物**：
- capability guard

**单项验收标准**：
- [ ] P1 adapter 调下载返回明确错误
- [ ] UI 不展示不存在的动作

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P02-005 · 实现 Provider Contract Test Harness

**目标**：新平台接入必须自动验约。

**前置依赖**：无

**实施动作**：
1. 规定 fixture search/metadata/access/download 响应
2. 统一测试 cancel/timeout/error normalization

**必须产物**：
- contract test harness

**单项验收标准**：
- [ ] 任何 Adapter 缺接口或返回错误 schema 时 CI 失败

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P02-006 · 实现 Provider Health Check

**目标**：单平台异常不拖垮系统。

**前置依赖**：无

**实施动作**：
1. 配置校验或轻量健康请求
2. 记录状态/延迟/last_checked
3. 失败有 circuit state

**必须产物**：
- health service

**单项验收标准**：
- [ ] 模拟一个 Provider 500 时其他 Provider 正常

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P02-007 · 生成 Integration Matrix

**目标**：自动从 Registry 生成平台接入矩阵。

**前置依赖**：无

**实施动作**：
1. 显示 P0-P7、search/metadata/browser/auth/download/register
2. 由代码生成，禁止维护第二份手工真相源

**必须产物**：
- provider-integration-matrix.md/API

**单项验收标准**：
- [ ] 覆盖 100% Provider
- [ ] 状态与 Registry 完全一致

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

# P03 · 国际组织 Provider 接入

阶段目标：跨国、宏观和国际比较的核心官方数据源

## P03-001 · 接入 World Bank Open Data / Data360

**目标**：将 World Bank Open Data / Data360 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/world_bank/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：搜索/指标 metadata/国家年份过滤/公开下载或 API 获取；保留指标代码、来源和更新时间
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/world_bank/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P03-002 · 接入 IMF Data

**目标**：将 IMF Data 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/imf/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现可用官方检索和数据获取；保留数据库/序列标识、单位与频率
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/imf/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P03-003 · 接入 OECD Data Explorer

**目标**：将 OECD Data Explorer 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/oecd/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现数据集检索、结构/维度读取、过滤和下载
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/oecd/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P03-004 · 接入 Eurostat

**目标**：将 Eurostat 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/eurostat/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现 dataset code 检索、metadata、bulk/API 获取和版本信息
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/eurostat/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P03-005 · 接入 WHO Global Health Observatory

**目标**：将 WHO Global Health Observatory 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/who_gho/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现指标/国家/年份检索与结构化获取
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/who_gho/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P03-006 · 接入 FAOSTAT

**目标**：将 FAOSTAT 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/faostat/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现主题/指标/国家/年份数据搜索和获取
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/faostat/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P03-007 · 接入 UN 系列数据库

**目标**：将 UN 系列数据库 接入统一 Provider Adapter，目标最低等级 P2，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/un_data/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现统一 UN catalog/metadata 发现，能导航到具体可用分库；可直接获取的分库提升到 P4
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/un_data/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P03-008 · 接入 UN Comtrade

**目标**：将 UN Comtrade 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/un_comtrade/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现 reporter/partner/product/year 等维度数据检索与获取
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/un_comtrade/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P03-009 · 接入 ILOSTAT

**目标**：将 ILOSTAT 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/ilostat/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现就业指标检索，保留 sex/age/unit/classif 等维度
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/ilostat/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P03-010 · 接入 UNESCO UIS

**目标**：将 UNESCO UIS 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/unesco_uis/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现教育/科研/文化指标搜索、metadata 和可用数据下载
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/unesco_uis/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

# P04 · 美国 Provider 接入

阶段目标：覆盖美国综合目录、人口、劳工、经济、金融、卫生、地球、教育和披露数据

## P04-001 · 接入 Data.gov

**目标**：将 Data.gov 接入统一 Provider Adapter，目标最低等级 P2，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/data_gov_us/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：作为 catalog/discovery 层；解析 distribution 和真正来源 URL，不把 catalog HTML 当数据
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/data_gov_us/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P04-002 · 接入 US Census Bureau

**目标**：将 US Census Bureau 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/us_census/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现数据集/变量/地理维度检索和 API/公开下载
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/us_census/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P04-003 · 接入 Bureau of Labor Statistics

**目标**：将 Bureau of Labor Statistics 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/us_bls/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现 series/subject search、时间序列获取、series metadata
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/us_bls/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P04-004 · 接入 BEA

**目标**：将 BEA 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/us_bea/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现 dataset/parameter 查询和官方数据获取
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/us_bea/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P04-005 · 接入 FRED

**目标**：将 FRED 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/fred/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现 series search/metadata/data；API key 若需要走安全凭据
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/fred/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P04-006 · 接入 CDC Data

**目标**：将 CDC Data 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/cdc_data/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现公开 catalog/search/下载或 Socrata 类接口
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/cdc_data/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P04-007 · 接入 NOAA

**目标**：将 NOAA 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/noaa/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现数据目录和可获得数据的结构化获取；大文件必须流式
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/noaa/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P04-008 · 接入 NASA Earthdata

**目标**：将 NASA Earthdata 接入统一 Provider Adapter，目标最低等级 P5，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/nasa_earthdata/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现检索；公开可取数据 P4，需 Earthdata Login 的路径支持已有账号/session
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/nasa_earthdata/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P04-009 · 接入 USGS

**目标**：将 USGS 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/usgs/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现数据目录、metadata 和公开下载
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/usgs/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P04-010 · 接入 SEC EDGAR

**目标**：将 SEC EDGAR 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/sec_edgar/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现公开文件/结构化披露发现和下载，尊重官方请求规范
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/sec_edgar/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P04-011 · 接入 Federal Election Commission Data

**目标**：将 Federal Election Commission Data 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/fec/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现公开数据搜索/API 获取，保留字段定义与来源
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/fec/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P04-012 · 接入 NCES

**目标**：将 NCES 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/nces/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现教育统计数据集/表/文件发现与公开下载
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/nces/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

# P05 · 欧洲及其他发达经济体 Provider 接入

阶段目标：覆盖欧盟和主要欧美/亚太政府门户

## P05-001 · 接入 data.europa.eu

**目标**：将 data.europa.eu 接入统一 Provider Adapter，目标最低等级 P2，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/data_europa/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：作为欧洲公共数据 catalog；解析 distribution 与具体国家/机构来源
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/data_europa/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P05-002 · 接入 ECB Data Portal

**目标**：将 ECB Data Portal 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/ecb_data/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现 series/dataset metadata 和下载
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/ecb_data/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P05-003 · 接入 Copernicus Data Space

**目标**：将 Copernicus Data Space 接入统一 Provider Adapter，目标最低等级 P5，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/copernicus/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现 catalog search；公开/需账号访问按真实能力处理，大对象下载流式
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/copernicus/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P05-004 · 接入 data.gov.uk / National Data Library

**目标**：将 data.gov.uk / National Data Library 接入统一 Provider Adapter，目标最低等级 P2，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/uk_data_gov/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现 catalog search 和 distribution 解析
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/uk_data_gov/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P05-005 · 接入 UK ONS

**目标**：将 UK ONS 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/ons/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现 dataset/edition/version/时间数据获取
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/ons/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P05-006 · 接入 UK Data Service

**目标**：将 UK Data Service 接入统一 Provider Adapter，目标最低等级 P5，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/uk_data_service/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现检索和 access requirement；已有账户登录；受限数据必须用户介入
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/uk_data_service/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P05-007 · 接入 data.gouv.fr

**目标**：将 data.gouv.fr 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/fr_data_gouv/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现 dataset/API 搜索、metadata、公开资源下载
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/fr_data_gouv/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P05-008 · 接入 INSEE

**目标**：将 INSEE 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/insee/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现统计序列/数据集搜索和获取
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/insee/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P05-009 · 接入 Germany GovData

**目标**：将 Germany GovData 接入统一 Provider Adapter，目标最低等级 P2，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/de_govdata/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现 catalog search/distribution
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/de_govdata/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P05-010 · 接入 Destatis GENESIS

**目标**：将 Destatis GENESIS 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/destatis_genesis/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现表/统计主题检索和数据获取；认证需求如实处理
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/destatis_genesis/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P05-011 · 接入 datos.gob.es

**目标**：将 datos.gob.es 接入统一 Provider Adapter，目标最低等级 P2，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/es_datos/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现 catalog/API 搜索和 distribution 解析
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/es_datos/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P05-012 · 接入 dati.gov.it

**目标**：将 dati.gov.it 接入统一 Provider Adapter，目标最低等级 P2，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/it_dati/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现 catalog 搜索和资源定位
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/it_dati/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P05-013 · 接入 data.overheid.nl

**目标**：将 data.overheid.nl 接入统一 Provider Adapter，目标最低等级 P2，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/nl_overheid/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现 catalog 搜索和资源定位
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/nl_overheid/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P05-014 · 接入 opendata.swiss

**目标**：将 opendata.swiss 接入统一 Provider Adapter，目标最低等级 P2，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/ch_opendata/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现 catalog 搜索和 distribution
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/ch_opendata/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P05-015 · 接入 Canada Open Government Portal

**目标**：将 Canada Open Government Portal 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/canada_open/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现 catalog/search/公开资源下载
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/canada_open/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P05-016 · 接入 data.gov.au

**目标**：将 data.gov.au 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/australia_data/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现 catalog/search，按 licence/access 区分公开与受限资源
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/australia_data/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P05-017 · 接入 data.govt.nz

**目标**：将 data.govt.nz 接入统一 Provider Adapter，目标最低等级 P2，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/nz_data/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现 catalog/search/distribution
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/nz_data/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P05-018 · 接入 Japan e-Stat

**目标**：将 Japan e-Stat 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/jp_estat/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现统计表检索和 API/文件获取
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/jp_estat/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P05-019 · 接入 data.go.jp

**目标**：将 data.go.jp 接入统一 Provider Adapter，目标最低等级 P2，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/jp_data_go/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现政府 Open Data Catalog 搜索和 distribution
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/jp_data_go/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P05-020 · 接入 Korea data.go.kr

**目标**：将 Korea data.go.kr 接入统一 Provider Adapter，目标最低等级 P5，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/kr_data/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现 catalog/API 检索；API key/账号状态进入 Vault，需申请能力明确展示
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/kr_data/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

# P06 · 中国官方与科研 Provider 接入

阶段目标：覆盖国家级、地方和国家科学数据体系

## P06-001 · 接入 国家数据集管理服务平台 NDSMS

**目标**：将 国家数据集管理服务平台 NDSMS 接入统一 Provider Adapter，目标最低等级 P5，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/cn_ndsms/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现站内搜索/metadata；公开数据下载；需登录时支持已有账号/普通注册；受限申请用户介入
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/cn_ndsms/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P06-002 · 接入 国家统计局“国家数据”

**目标**：将 国家统计局“国家数据” 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/cn_nbs/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现指标/地区/年份搜索和公开数据获取；保留指标定义
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/cn_nbs/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P06-003 · 接入 国家公共数据资源登记平台

**目标**：将 国家公共数据资源登记平台 接入统一 Provider Adapter，目标最低等级 P2，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/cn_public_registry/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：作为发现/登记资源层；解析可用资源和访问方式，不假设均可直接下载
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/cn_public_registry/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P06-004 · 接入 北京市公共数据开放平台

**目标**：将 北京市公共数据开放平台 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/beijing_open_data/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现站内/API 搜索和公开下载
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/beijing_open_data/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P06-005 · 接入 上海公共数据开放平台

**目标**：将 上海公共数据开放平台 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/shanghai_open_data/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现站内/API 搜索和公开下载
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/shanghai_open_data/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P06-006 · 接入 深圳市政府数据开放平台

**目标**：将 深圳市政府数据开放平台 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/shenzhen_open_data/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现站内/API 搜索和公开下载
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/shenzhen_open_data/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P06-007 · 接入 武汉公共数据开放平台

**目标**：将 武汉公共数据开放平台 接入统一 Provider Adapter，目标最低等级 P2，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/wuhan_open_data/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现可用 catalog/browser search；公开下载能力按平台真实接口提升
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/wuhan_open_data/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P06-008 · 接入 国家基础学科公共科学数据中心

**目标**：将 国家基础学科公共科学数据中心 接入统一 Provider Adapter，目标最低等级 P5，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/nbsdc/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现搜索/metadata；公开资源下载；需账号/申请的准确进入对应状态
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/nbsdc/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P06-009 · 接入 国家地球系统科学数据中心

**目标**：将 国家地球系统科学数据中心 接入统一 Provider Adapter，目标最低等级 P5，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/geodata_cn/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现目录检索和下载/登录访问
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/geodata_cn/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P06-010 · 接入 国家青藏高原科学数据中心

**目标**：将 国家青藏高原科学数据中心 接入统一 Provider Adapter，目标最低等级 P5，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/tpdc/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现数据检索、metadata、登录/下载；受限申请用户介入
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/tpdc/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P06-011 · 接入 中国科学院相关科学数据中心

**目标**：将 中国科学院相关科学数据中心 接入统一 Provider Adapter，目标最低等级 P2，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/cas_science_data/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：先形成可扩展子 Provider 目录；各中心按具体站点逐个提升能力
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/cas_science_data/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P06-012 · 接入 ScienceDB

**目标**：将 ScienceDB 接入统一 Provider Adapter，目标最低等级 P5，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/sciencedb/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现 search/metadata/DOI/files；公开下载 P4，账号路径 P5
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/sciencedb/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

# P07 · 科研仓储与 AI/数据社区 Provider 接入

阶段目标：覆盖论文数据、通用仓储、ML 数据集和国内社区

## P07-001 · 接入 Zenodo

**目标**：将 Zenodo 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/zenodo/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：search/metadata/files/DOI/version/license/公开下载
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/zenodo/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-002 · 接入 Harvard Dataverse

**目标**：将 Harvard Dataverse 接入统一 Provider Adapter，目标最低等级 P5，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/harvard_dataverse/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：search/metadata/files；公开下载；restricted file 准确识别；账户路径
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/harvard_dataverse/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-003 · 接入 Mendeley Data

**目标**：将 Mendeley Data 接入统一 Provider Adapter，目标最低等级 P5，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/mendeley_data/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：search/metadata/DOI/files；需登录路径走 Vault/Browser
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/mendeley_data/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-004 · 接入 Figshare

**目标**：将 Figshare 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/figshare/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：search/metadata/files/DOI/version/公开下载
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/figshare/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-005 · 接入 Dryad

**目标**：将 Dryad 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/dryad/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：search/metadata/论文关联/license/files/下载
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/dryad/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-006 · 接入 OSF

**目标**：将 OSF 接入统一 Provider Adapter，目标最低等级 P5，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/osf/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：public project/data 搜索与下载；私有/账号资源仅在用户授权下访问
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/osf/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-007 · 接入 ICPSR

**目标**：将 ICPSR 接入统一 Provider Adapter，目标最低等级 P5，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/icpsr/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：search/metadata/access classification；公开/账号数据；restricted data 强制用户介入
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/icpsr/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-008 · 接入 openICPSR

**目标**：将 openICPSR 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/openicpsr/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：公开社科数据检索、metadata、下载
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/openicpsr/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-009 · 接入 GESIS

**目标**：将 GESIS 接入统一 Provider Adapter，目标最低等级 P5，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/gesis/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：search/metadata；公开下载和账号访问区分
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/gesis/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-010 · 接入 Dataverse 网络

**目标**：将 Dataverse 网络 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/dataverse_network/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：实现通用 Dataverse adapter，可通过 base_url 注册多个实例
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/dataverse_network/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-011 · 接入 Academic Torrents

**目标**：将 Academic Torrents 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/academic_torrents/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：搜索 metadata；合法公开 torrent 获取；大文件有配额和暂停
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/academic_torrents/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-012 · 接入 Kaggle Datasets

**目标**：将 Kaggle Datasets 接入统一 Provider Adapter，目标最低等级 P6，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/kaggle/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：搜索/metadata；已有账号登录；普通注册能力；真实下载；不得绕过 CAPTCHA
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/kaggle/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-013 · 接入 Hugging Face Datasets

**目标**：将 Hugging Face Datasets 接入统一 Provider Adapter，目标最低等级 P5，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/huggingface_datasets/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：search/metadata/revision/files；公开下载；gated dataset 用户授权/登录
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/huggingface_datasets/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-014 · 接入 OpenML

**目标**：将 OpenML 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/openml/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：search/metadata/data file/API 获取
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/openml/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-015 · 接入 UCI Machine Learning Repository

**目标**：将 UCI Machine Learning Repository 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/uci_ml/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：search/metadata/公开文件下载
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/uci_ml/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-016 · 接入 Papers with Code Datasets

**目标**：将 Papers with Code Datasets 接入统一 Provider Adapter，目标最低等级 P2，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/papers_with_code/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：作为论文-数据集索引，解析数据集外部来源，不把索引页作为数据
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/papers_with_code/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-017 · 接入 Data.world

**目标**：将 Data.world 接入统一 Provider Adapter，目标最低等级 P5，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/data_world/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：search/metadata；公开/账号数据区分，账号凭据走 Vault
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/data_world/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-018 · 接入 AWS Registry of Open Data

**目标**：将 AWS Registry of Open Data 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/aws_open_data/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：catalog search；对象存储路径/说明解析；支持大文件选择性获取
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/aws_open_data/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-019 · 接入 Google Dataset Search

**目标**：将 Google Dataset Search 接入统一 Provider Adapter，目标最低等级 P2，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/google_dataset_search/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：作为发现层；解析外部数据来源，不宣称自身托管
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/google_dataset_search/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-020 · 接入 Google Cloud Public Datasets / BigQuery

**目标**：将 Google Cloud Public Datasets / BigQuery 接入统一 Provider Adapter，目标最低等级 P5，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/bigquery_public/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：dataset metadata/query；云凭据安全；支持 query 结果导出为 artifact
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/bigquery_public/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-021 · 接入 Azure Open Datasets

**目标**：将 Azure Open Datasets 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/azure_open_data/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：search/metadata/可用数据获取
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/azure_open_data/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-022 · 接入 Common Crawl

**目标**：将 Common Crawl 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/common_crawl/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：索引和公开对象数据获取；大规模任务必须范围控制
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/common_crawl/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-023 · 接入 Wikimedia Dumps

**目标**：将 Wikimedia Dumps 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/wikimedia_dumps/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：dump discovery/version/files/checksum/流式下载
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/wikimedia_dumps/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-024 · 接入 Wikidata

**目标**：将 Wikidata 接入统一 Provider Adapter，目标最低等级 P4，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/wikidata/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：SPARQL/API 查询并将结果固化为带 query provenance 的 artifact
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/wikidata/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-025 · 接入 阿里云天池 Tianchi

**目标**：将 阿里云天池 Tianchi 接入统一 Provider Adapter，目标最低等级 P6，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/tianchi/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：数据集搜索；已有账号/普通注册；下载；需要实名认证/协议时用户介入
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/tianchi/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-026 · 接入 和鲸 HeyWhale/Kesci

**目标**：将 和鲸 HeyWhale/Kesci 接入统一 Provider Adapter，目标最低等级 P6，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/heywhale/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：搜索、账号、普通注册、可下载数据；受限动作用户介入
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/heywhale/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-027 · 接入 OpenDataLab

**目标**：将 OpenDataLab 接入统一 Provider Adapter，目标最低等级 P6，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/opendatalab/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：搜索/metadata/账号/下载，按平台许可和访问状态处理
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/opendatalab/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-028 · 接入 ModelScope Datasets

**目标**：将 ModelScope Datasets 接入统一 Provider Adapter，目标最低等级 P5，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/modelscope/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：search/metadata/revision/files；账号/gated 路径
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/modelscope/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-029 · 接入 百度 AI Studio

**目标**：将 百度 AI Studio 接入统一 Provider Adapter，目标最低等级 P5，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/baidu_ai_studio/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：数据集搜索/metadata/账号下载；实名或额外协议用户介入
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/baidu_ai_studio/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P07-030 · 接入 DataFountain

**目标**：将 DataFountain 接入统一 Provider Adapter，目标最低等级 P5，并如实声明无法自动化的能力。

**前置依赖**：P02-001~P02-006

**实施动作**：
1. 先审计该平台当前公开搜索、metadata、API、浏览器、认证、下载和注册路径，写入 `providers/datafountain/CAPABILITIES.md`
2. 按统一 Adapter contract 实现：数据搜索/竞赛数据 access 分类；需加入竞赛/协议时用户介入
3. 为 search/metadata/access/download/auth（适用时）建立离线 fixture；增加 contract test、错误路径、取消和超时
4. 至少执行一次真实 smoke（CI 可不依赖实时外网），记录当前 last_verified_at；如果平台能力与目标等级客观不符，真实降低 capability 并记录阻塞原因，不得伪造完成

**必须产物**：
- providers/datafountain/adapter
- CAPABILITIES.md
- fixtures
- contract tests

**单项验收标准**：
- [ ] Provider Registry 中状态与真实实现一致
- [ ] search 至少达到 P1；可公开下载的平台应完成 P4；账号型平台按目标完成 P5/P6 或明确真实外部阻塞
- [ ] 搜索结果统一为 DatasetCandidate，下载统一生成 DownloadJob/DatasetArtifact
- [ ] 错误页面/登录页不会被当成数据集文件
- [ ] contract test 全通过且真实 smoke 结果有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

# P08 · Browser Runtime 与可视化 Computer Use

阶段目标：实现真实可见、可靠定位、可暂停和可接管的网页执行层。

## P08-001 · 启动 headed Chromium Browser Runtime

**目标**：浏览器必须是真实交互环境。

**前置依赖**：无

**实施动作**：
1. 复用现有 Browser/Computer Use，如不存在则建立成熟 Chromium automation runtime
2. Browser context 与 task/session 绑定
3. 生命周期结束清理 orphan process

**必须产物**：
- BrowserRuntime

**单项验收标准**：
- [ ] 能真实打开页面并显示
- [ ] 任务关闭后无孤儿浏览器进程

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P08-002 · 实现 BrowserSession

**目标**：隔离多个任务和标签页。

**前置依赖**：无

**实施动作**：
1. 记录 session_id/task_id/current_tab/tabs/owner/status
2. 持久化非敏感恢复信息

**必须产物**：
- BrowserSession

**单项验收标准**：
- [ ] 两个任务不会串 session
- [ ] 切 tab 状态正确

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P08-003 · 实现 navigate/back/forward

**目标**：可靠导航。

**前置依赖**：无

**实施动作**：
1. URL 校验
2. timeout/wait strategy
3. 记录 redirect chain

**必须产物**：
- navigation tools

**单项验收标准**：
- [ ] 正常导航通过
- [ ] 超时返回 retryable error
- [ ] 危险 scheme 被拒绝

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P08-004 · 实现 DOM 与 Accessibility 读取

**目标**：用语义而非坐标理解页面。

**前置依赖**：无

**实施动作**：
1. 提取 role/name/text/stable attrs
2. 限制内容量
3. 密码字段 value 不回传

**必须产物**：
- browser.read

**单项验收标准**：
- [ ] 按钮/输入框可被语义识别
- [ ] secret 输入值不出 tool result

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P08-005 · 实现 click/double_click

**目标**：按 locator 执行真实点击。

**前置依赖**：无

**实施动作**：
1. 支持 role/name/text/css
2. 元素不可见先滚动
3. 点击后等待条件可配置

**必须产物**：
- click tools

**单项验收标准**：
- [ ] 测试页改变布局仍可点击相同语义按钮
- [ ] 不存在元素有诊断

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P08-006 · 实现 type/keyboard

**目标**：真实填写搜索、登录、注册表单。

**前置依赖**：无

**实施动作**：
1. 支持 fill/type/press
2. secret 参数标记
3. 日志只显示 masked

**必须产物**：
- type/key tools

**单项验收标准**：
- [ ] 输入内容正确
- [ ] password 不进日志

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P08-007 · 实现 scroll/select/upload

**目标**：覆盖常见交互。

**前置依赖**：无

**实施动作**：
1. 页面和容器滚动
2. select option
3. 上传路径必须在用户授权范围

**必须产物**：
- interaction tools

**单项验收标准**：
- [ ] fixture 全通过
- [ ] 越权文件路径被拒绝

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P08-008 · 实现多 tab 和 popup 管理

**目标**：处理下载说明和 OAuth 页面。

**前置依赖**：无

**实施动作**：
1. new/close/switch
2. 捕获 target=_blank/popup
3. 关闭当前页选择有效 tab

**必须产物**：
- tab manager

**单项验收标准**：
- [ ] 弹窗可被识别并切换
- [ ] tab 状态与 UI 同步

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P08-009 · 实现 screenshot + vision fallback

**目标**：处理缺少稳定 DOM 的页面。

**前置依赖**：无

**实施动作**：
1. 截取 viewport
2. 定义视觉定位结果格式
3. 仅作为后备

**必须产物**：
- vision locator interface

**单项验收标准**：
- [ ] 无 DOM fixture 能定位目标
- [ ] 正常 DOM 页面不默认走 vision

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P08-010 · 实现 Locator Strategy Chain

**目标**：固定可靠降级顺序。

**前置依赖**：无

**实施动作**：
1. role/name→semantic DOM→text→stable selector→vision→coordinate fallback
2. 每次记录采用策略

**必须产物**：
- locator resolver

**单项验收标准**：
- [ ] 页面改版位移不导致主要操作失败
- [ ] 固定坐标不会先于语义定位

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P08-011 · 实现 Browser Action Event Stream

**目标**：让用户实时看到 AI 操作。

**前置依赖**：无

**实施动作**：
1. 事件含 action/target/status/time/session
2. secret target/value 脱敏
3. 前端订阅

**必须产物**：
- browser event stream

**单项验收标准**：
- [ ] 页面 click/type/scroll 与右侧事件同步
- [ ] 密码只显示 ********

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P08-012 · 实现 Pause

**目标**：用户可中断自动化。

**前置依赖**：无

**实施动作**：
1. 加入 cancellation/pause token
2. 当前原子动作结束后停止派发后续动作

**必须产物**：
- pause controller

**单项验收标准**：
- [ ] 连续动作中暂停后不产生新输入
- [ ] 状态显示 PAUSED

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P08-013 · 实现 Take Over

**目标**：用户获得同一 Browser 控制。

**前置依赖**：无

**实施动作**：
1. owner=human
2. 停止 Agent dispatcher
3. 不重建 session

**必须产物**：
- takeover controller

**单项验收标准**：
- [ ] 接管期间 Agent 输入次数为 0
- [ ] 用户可操作同页面

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P08-014 · 实现 Return to Agent

**目标**：交还后重新感知当前网页。

**前置依赖**：无

**实施动作**：
1. owner=agent
2. 重新读取 URL/DOM/accessibility
3. 废弃旧坐标和失效 locator

**必须产物**：
- resume controller

**单项验收标准**：
- [ ] 用户导航到新页后 Agent 能从新状态继续

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P08-015 · 实现强制介入检测

**目标**：识别 CAPTCHA/MFA/受限协议等。

**前置依赖**：无

**实施动作**：
1. DOM/text/URL/provider rule 联合检测
2. 生成 intervention reason/action
3. 立即 pause

**必须产物**：
- intervention detector

**单项验收标准**：
- [ ] CAPTCHA fixture 进入 WAITING_USER
- [ ] 不产生绕过动作

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P08-016 · 实现 Browser Crash Recovery

**目标**：浏览器崩溃不伪造完成。

**前置依赖**：无

**实施动作**：
1. 监听 disconnect
2. 可安全时重建 context
3. 不可恢复的外部表单状态进入 NEEDS_REVIEW

**必须产物**：
- browser recovery

**单项验收标准**：
- [ ] 强杀 Browser 后任务状态正确
- [ ] 不会重复提交注册/协议

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

# P09 · 账户、身份、自动注册与安全 Vault

阶段目标：实现用户已有账号与普通自助注册两种路径。

## P09-001 · 实现 Data Identity

**目标**：保存用户允许用于注册的身份字段。

**前置依赖**：无

**实施动作**：
1. name/email/country/institution/role/ORCID/research-purpose
2. 字段逐项可编辑和关闭自动填充

**必须产物**：
- DataIdentity

**单项验收标准**：
- [ ] 未授权字段不会提交
- [ ] 可删除身份资料

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P09-002 · 实现 SecretStore 抽象

**目标**：业务层只通过引用访问秘密。

**前置依赖**：无

**实施动作**：
1. get/set/delete/metadata
2. 禁止业务 DB 保存 secret

**必须产物**：
- SecretStore

**单项验收标准**：
- [ ] mock tests 通过
- [ ] secret 不出现在对象序列化

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P09-003 · 接入本机安全 Vault

**目标**：使用 OS credential/keychain 或现有安全存储。

**前置依赖**：无

**实施动作**：
1. Windows/macOS/Linux 按项目目标平台实现
2. 严禁 plaintext json fallback

**必须产物**：
- Vault backend

**单项验收标准**：
- [ ] 磁盘全文检索找不到测试明文密码
- [ ] 删除操作不可再次读取

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P09-004 · 实现独立强密码生成器

**目标**：每个平台生成不同密码。

**前置依赖**：无

**实施动作**：
1. 默认≥16字符，大小写、数字、特殊字符
2. 支持 Provider 密码规则 override
3. 使用安全随机源

**必须产物**：
- password generator

**单项验收标准**：
- [ ] 1000 次测试满足规则
- [ ] 两个平台注册密码不同

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P09-005 · 实现 AccountStatus

**目标**：区分 registered/logged_in/expired/blocked/verification_required。

**前置依赖**：无

**实施动作**：
1. 持久化非秘密 account metadata
2. last_verified

**必须产物**：
- account state

**单项验收标准**：
- [ ] session 过期可准确转 expired

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P09-006 · 实现 SessionStore

**目标**：安全复用 cookies/local storage/token。

**前置依赖**：无

**实施动作**：
1. 加密保存
2. TTL/expiry
3. 按 Provider 删除
4. 不进普通日志

**必须产物**：
- session store

**单项验收标准**：
- [ ] 应用重启可恢复测试登录
- [ ] 删除后不可继续使用

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P09-007 · 实现 Access Inspector

**目标**：访问前判断公开/API/登录/注册/介入。

**前置依赖**：无

**实施动作**：
1. 结合 Provider capability、dataset metadata、session 和页面状态

**必须产物**：
- access inspector

**单项验收标准**：
- [ ] 公开数据不错误要求登录
- [ ] restricted 不走 public path

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P09-008 · 实现已有账号绑定

**目标**：用户主动登录现有平台账户。

**前置依赖**：无

**实施动作**：
1. 账户中心选择 Provider
2. 由 Browser/OAuth/API key 完成合法登录
3. 秘密写 Vault

**必须产物**：
- account binding

**单项验收标准**：
- [ ] 成功后状态 logged_in
- [ ] 日志无秘密

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P09-009 · 实现登录执行器

**目标**：Agent 可使用已授权凭据登录。

**前置依赖**：无

**实施动作**：
1. 从 Vault 取 secret
2. 填写/提交
3. 分类 invalid credential/session expired/captcha

**必须产物**：
- auth.login

**单项验收标准**：
- [ ] 错误密码不会误判成功
- [ ] CAPTCHA 转用户介入

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P09-010 · 实现登录重试上限

**目标**：降低锁号风险。

**前置依赖**：无

**实施动作**：
1. Provider-specific max attempts
2. backoff
3. 达到上限暂停

**必须产物**：
- login retry guard

**单项验收标准**：
- [ ] 连续错误不会无限重试

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P09-011 · 实现自动注册总开关与 Provider 覆盖

**目标**：只有用户授权时才能创建账号。

**前置依赖**：无

**实施动作**：
1. 全局开关
2. 单平台 allow/deny
3. 记录授权状态

**必须产物**：
- registration consent

**单项验收标准**：
- [ ] 关闭时任何 Provider 都不能提交注册

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P09-012 · 实现注册字段映射

**目标**：把 Data Identity 映射到不同表单。

**前置依赖**：无

**实施动作**：
1. email/name/username/password/institution 等
2. provider-specific mapping

**必须产物**：
- registration mapper

**单项验收标准**：
- [ ] 标准 fixture 表单能正确填充
- [ ] 未授权身份字段空置

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P09-013 · 实现普通注册提交器

**目标**：完成合法普通自助注册。

**前置依赖**：无

**实施动作**：
1. 生成 provider 独立密码
2. 填表
3. 提交
4. 解析 success/duplicate/password_rule/verify_email

**必须产物**：
- auth.register

**单项验收标准**：
- [ ] 各结果 fixture 分类准确
- [ ] 密码存 Vault

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P09-014 · 实现邮箱验证挂起状态

**目标**：不能安全自动完成时明确交给用户。

**前置依赖**：无

**实施动作**：
1. 状态 VERIFY_EMAIL_REQUIRED
2. 允许 user takeover 后 resume

**必须产物**：
- verification workflow

**单项验收标准**：
- [ ] 未验证不标 active
- [ ] 验证后可继续

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P09-015 · 实现 CAPTCHA/MFA/协议/实名拦截

**目标**：高风险节点强制用户处理。

**前置依赖**：无

**实施动作**：
1. 与 Browser detector 联动
2. 禁止自动 accept restricted agreement
3. 禁止证件自动提交

**必须产物**：
- auth intervention

**单项验收标准**：
- [ ] CAPTCHA/MFA/实名 fixture 均停止 Agent

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P09-016 · 实现账户删除、登出和 session revoke

**目标**：用户可撤销授权。

**前置依赖**：无

**实施动作**：
1. 删除 Vault secret
2. 清 session
3. 更新 account state

**必须产物**：
- account revoke

**单项验收标准**：
- [ ] 删除后下一次访问必须重新认证

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

# P10 · 需求解析、搜索编排、去重与推荐

阶段目标：把用户研究问题转成高质量候选数据集。

## P10-001 · 实现自然语言 Requirement Parser

**目标**：生成 DataRequirement。

**前置依赖**：无

**实施动作**：
1. 抽取研究问题、对象、时间、地区、粒度、变量角色、来源偏好
2. 合理推断可选默认值
3. 重要推断加入 assumptions

**必须产物**：
- requirement parser

**单项验收标准**：
- [ ] 至少 20 个测试请求达到预期结构
- [ ] 不完整请求不强制填写所有非关键字段

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P10-002 · 实现 Requirement Validator

**目标**：识别互相冲突或不可执行约束。

**前置依赖**：无

**实施动作**：
1. 时间、频率、粒度、格式、来源冲突检查

**必须产物**：
- requirement validator

**单项验收标准**：
- [ ] 明显冲突给出可解释错误

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P10-003 · 实现 Provider Selector

**目标**：按需求选择最相关平台。

**前置依赖**：无

**实施动作**：
1. 国家/地区、学科、变量、来源可信度、访问偏好
2. 优先官方/国际组织满足 hard constraints

**必须产物**：
- provider selector

**单项验收标准**：
- [ ] 中国宏观需求不会默认只搜 Kaggle
- [ ] 用户 excluded_sources 生效

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P10-004 · 实现 Query Planner

**目标**：为不同 Provider 生成搜索策略。

**前置依赖**：无

**实施动作**：
1. 多语言关键词
2. 指标/主题拆分
3. provider-specific query syntax

**必须产物**：
- query plan

**单项验收标准**：
- [ ] 同一需求对不同平台生成适合的查询

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P10-005 · 实现并行 Search Orchestrator

**目标**：多个 Provider 并发。

**前置依赖**：无

**实施动作**：
1. global/provider concurrency
2. timeout/retry/backoff
3. cancellation
4. health/circuit breaker

**必须产物**：
- search orchestrator

**单项验收标准**：
- [ ] 一个 Provider 超时不阻塞其他结果

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P10-006 · 实现 Browser Search Worker

**目标**：没有稳定 API 时用真实浏览器搜索。

**前置依赖**：无

**实施动作**：
1. 打开 Provider
2. 输入 query
3. 读取结果
4. 事件实时可见

**必须产物**：
- browser search worker

**单项验收标准**：
- [ ] 用户可在 Live Browser 看到真实搜索

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P10-007 · 实现 Candidate Normalizer

**目标**：统一平台结果。

**前置依赖**：无

**实施动作**：
1. 转换 DatasetCandidate
2. 保留原始 metadata 引用

**必须产物**：
- normalizer

**单项验收标准**：
- [ ] 至少 8 类 Provider fixture 输出同一 schema

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P10-008 · 实现精确去重

**目标**：DOI/URL/provider ID/checksum。

**前置依赖**：无

**实施动作**：
1. canonical DOI
2. canonical URL
3. mirror relationship

**必须产物**：
- deduplicator

**单项验收标准**：
- [ ] 同 DOI 结果只形成一个逻辑候选

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P10-009 · 实现模糊去重

**目标**：处理没有 DOI 的镜像。

**前置依赖**：无

**实施动作**：
1. title/author/year 相似度
2. 低置信不静默合并

**必须产物**：
- fuzzy dedupe

**单项验收标准**：
- [ ] 不同版本不会被误合并

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P10-010 · 实现 Metadata Enrichment

**目标**：只深挖高价值候选。

**前置依赖**：无

**实施动作**：
1. top-N/按需 metadata
2. 控制请求量

**必须产物**：
- enrichment pipeline

**单项验收标准**：
- [ ] 不会无脑对所有结果发重请求

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P10-011 · 实现 Variable Hint Extraction

**目标**：从 metadata/codebook/preview 判断变量。

**前置依赖**：无

**实施动作**：
1. 变量名、标签、定义、问卷题项
2. 置信度

**必须产物**：
- variable hints

**单项验收标准**：
- [ ] 含 codebook fixture 能命中核心变量

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P10-012 · 实现 Coverage Evaluator

**目标**：逐项判断时间、空间、单位和样本。

**前置依赖**：无

**实施动作**：
1. 与 Requirement 比较
2. 输出 gaps

**必须产物**：
- coverage report

**单项验收标准**：
- [ ] 缺年份/地区不会被标记完整匹配

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P10-013 · 实现 License Parser

**目标**：解析常见许可和未知状态。

**前置依赖**：无

**实施动作**：
1. CC0/CC-BY/ODC/custom/unknown
2. 保留许可原始链接/文本引用

**必须产物**：
- license parser

**单项验收标准**：
- [ ] UNKNOWN 不会自动当开放

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P10-014 · 实现 Trust Classification

**目标**：区分官方、国际组织、学术、社区。

**前置依赖**：无

**实施动作**：
1. 依据发布主体和平台类型
2. 不把社区上传自动视为官方

**必须产物**：
- trust classification

**单项验收标准**：
- [ ] Kaggle 用户数据不会标 A 级官方

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P10-015 · 实现候选推荐解释

**目标**：输出 reasons + limitations。

**前置依赖**：无

**实施动作**：
1. 变量覆盖、粒度、时间、空间、来源、许可、访问、文档
2. hard constraint 优先

**必须产物**：
- recommendation object

**单项验收标准**：
- [ ] 每个候选至少一条依据和不足/unknown

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P10-016 · 实现搜索历史、进度和取消

**目标**：用户可观察并终止。

**前置依赖**：无

**实施动作**：
1. provider queued/running/done/error/result_count
2. 持久化 SearchRun
3. cancel 传播到 browser/API worker

**必须产物**：
- SearchRun
- progress events

**单项验收标准**：
- [ ] 取消后不再新增结果
- [ ] 重启可看历史

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

# P11 · 下载、Raw 文件与数据解析

阶段目标：把候选转换成可靠、不可污染的原始数据资产。

## P11-001 · 实现 DownloadJob 创建门禁

**目标**：所有下载先建任务。

**前置依赖**：无

**实施动作**：
1. 创建 manifest
2. 绑定 candidate/provider/source/version/access/license

**必须产物**：
- DownloadJob service

**单项验收标准**：
- [ ] 无 job_id downloader 拒绝执行

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P11-002 · 实现 HTTP/API 流式下载

**目标**：避免大文件全内存。

**前置依赖**：无

**实施动作**：
1. streaming
2. progress
3. timeout
4. retry/resume 策略

**必须产物**：
- http downloader

**单项验收标准**：
- [ ] 大文件下载内存稳定
- [ ] 中断可明确恢复/重试

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P11-003 · 实现 Browser Download 捕获

**目标**：监听页面真实 download event。

**前置依赖**：无

**实施动作**：
1. 把 event 绑定 DownloadJob
2. 记录 suggested filename/source tab

**必须产物**：
- browser downloader

**单项验收标准**：
- [ ] 真实点击后文件进入正确 job

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P11-004 · 实现 partial→raw 原子提交

**目标**：半文件不能进入 Raw。

**前置依赖**：无

**实施动作**：
1. 临时扩展名
2. 下载完成并校验后 atomic rename

**必须产物**：
- atomic storage

**单项验收标准**：
- [ ] 中断后 raw 无伪完成文件

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P11-005 · 实现 SHA256/size 校验

**目标**：建立内容身份。

**前置依赖**：无

**实施动作**：
1. 计算 checksum/size
2. 写 manifest

**必须产物**：
- checksum service

**单项验收标准**：
- [ ] 重复下载同文件 hash 一致

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P11-006 · 实现 MIME/内容识别

**目标**：防登录页伪装。

**前置依赖**：无

**实施动作**：
1. magic/content sniff
2. 检测 text/html unexpected

**必须产物**：
- file type detector

**单项验收标准**：
- [ ] HTML 保存成 .csv 时被拦截

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P11-007 · 实现安全解压

**目标**：防 zip slip/压缩炸弹。

**前置依赖**：无

**实施动作**：
1. 规范路径
2. 大小/文件数/层级限制

**必须产物**：
- safe extractor

**单项验收标准**：
- [ ] ../evil fixture 无法写出目录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P11-008 · 实现 Raw Immutable Guard

**目标**：所有 transform 只能读 Raw。

**前置依赖**：无

**实施动作**：
1. Raw 只读逻辑
2. 写入强制 intermediate/final

**必须产物**：
- immutability guard

**单项验收标准**：
- [ ] 尝试覆盖 raw 被拒绝

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P11-009 · 实现内容去重

**目标**：相同 checksum 减少重复存储。

**前置依赖**：无

**实施动作**：
1. content-addressed reference 或安全等价方案
2. 逻辑 source 引用仍分别保留

**必须产物**：
- artifact dedupe

**单项验收标准**：
- [ ] 重复内容只存一份物理对象但 provenance 不丢

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P11-010 · 实现下载配额与磁盘检查

**目标**：大数据提前阻止磁盘打满。

**前置依赖**：无

**实施动作**：
1. known size 预检
2. unknown size 保留安全阈值
3. 可配置 max

**必须产物**：
- quota guard

**单项验收标准**：
- [ ] 磁盘不足时不启动下载

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P11-011 · 实现格式路由

**目标**：按真实格式选择 parser。

**前置依赖**：无

**实施动作**：
1. CSV/XLSX/JSON/Parquet/DTA/SAV/SAS/GeoJSON/Shapefile/NetCDF/SQLite/HTML

**必须产物**：
- parser router

**单项验收标准**：
- [ ] 扩展名错误不会直接选错 parser

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P11-012 · 实现 CSV/TSV parser

**目标**：支持编码、分隔符和 chunk。

**前置依赖**：无

**实施动作**：
1. UTF-8/常见中文编码
2. delimiter sniff
3. stream/chunk

**必须产物**：
- csv parser

**单项验收标准**：
- [ ] GBK 中文 fixture 正确

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P11-013 · 实现 XLS/XLSX parser

**目标**：多 Sheet 全部可见。

**前置依赖**：无

**实施动作**：
1. 枚举 sheet
2. 识别候选数据表但不丢弃其他 sheet

**必须产物**：
- excel parser

**单项验收标准**：
- [ ] 多 sheet fixture 全部显示

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P11-014 · 实现 JSON/JSONL/Parquet parser

**目标**：处理主流结构化格式。

**前置依赖**：无

**实施动作**：
1. JSON array/object/jsonl
2. Parquet schema/sample 不全表读取

**必须产物**：
- json/parquet parsers

**单项验收标准**：
- [ ] JSONL 行数正确
- [ ] Parquet preview 快速

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P11-015 · 实现 DTA/SAV/SAS parser

**目标**：保留统计软件元数据。

**前置依赖**：无

**实施动作**：
1. 读取变量标签和值标签

**必须产物**：
- stat parsers

**单项验收标准**：
- [ ] SPSS value labels 不丢

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P11-016 · 实现 Geo/Science 基础 parser

**目标**：至少可靠 profile 特殊格式。

**前置依赖**：无

**实施动作**：
1. GeoJSON/Shapefile CRS/schema
2. NetCDF dimensions/variables

**必须产物**：
- geo/science parsers

**单项验收标准**：
- [ ] 特殊格式不会被普通表 parser 错误处理

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

# P12 · Dataset Profile 与语义层

阶段目标：让每个数据集在合成前被充分理解。

## P12-001 · 实现 Schema Inference

**目标**：可靠推断列类型。

**前置依赖**：无

**实施动作**：
1. 多段采样/统计
2. mixed type/null 处理

**必须产物**：
- schema inference

**单项验收标准**：
- [ ] 前若干行空值不会导致错误类型

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P12-002 · 实现基础 Profile

**目标**：行列、缺失、唯一、范围、样例。

**前置依赖**：无

**实施动作**：
1. stream/approx 方案支持大表

**必须产物**：
- dataset profile

**单项验收标准**：
- [ ] 100MB+ CSV 不 OOM

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P12-003 · 实现重复行和主键候选

**目标**：辅助合成。

**前置依赖**：无

**实施动作**：
1. 重复率
2. 单列 key
3. 有限组合 key

**必须产物**：
- key hints

**单项验收标准**：
- [ ] province+year 能识别组合候选

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P12-004 · 识别时间字段

**目标**：发现 year/date/quarter/month。

**前置依赖**：无

**实施动作**：
1. 列名+值模式+metadata

**必须产物**：
- time hints

**单项验收标准**：
- [ ] 2020年/2020Q1/date fixture 正确

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P12-005 · 识别地理字段

**目标**：发现 ISO/行政区代码/名称。

**前置依赖**：无

**实施动作**：
1. ISO2/ISO3/省市/代码模式

**必须产物**：
- geo hints

**单项验收标准**：
- [ ] country_code/city_code fixture 正确

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P12-006 · 识别 ID/权重/量表题项候选

**目标**：服务社科数据。

**前置依赖**：无

**实施动作**：
1. 变量名、labels、值分布

**必须产物**：
- role hints

**单项验收标准**：
- [ ] 问卷 fixture 可识别一组 Likert items

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P12-007 · 实现 Codebook Detection

**目标**：关联 README/codebook/dictionary。

**前置依赖**：无

**实施动作**：
1. 文件名、metadata、内容特征

**必须产物**：
- codebook links

**单项验收标准**：
- [ ] 数据文件与 codebook 能关联

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P12-008 · 生成 VariableSemantic

**目标**：原始字段进入统一语义模型。

**前置依赖**：无

**实施动作**：
1. 结合 labels/codebook/metadata
2. 保存 confidence

**必须产物**：
- VariableSemantic records

**单项验收标准**：
- [ ] 每个最终候选字段都保留 original_name/source_field

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P12-009 · 实现语义比较器

**目标**：判断 compatible/convertible/conflict/unknown。

**前置依赖**：无

**实施动作**：
1. definition/unit/population/frequency/geography/price basis 比较

**必须产物**：
- semantic comparator

**单项验收标准**：
- [ ] current GDP vs constant GDP 不判 compatible

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P12-010 · 实现 Profile 持久化与缓存

**目标**：checksum 绑定结果。

**前置依赖**：无

**实施动作**：
1. profile_id=artifact/checksum/version
2. 文件变化自动失效

**必须产物**：
- profile store

**单项验收标准**：
- [ ] 同 hash 可复用，不同 hash 不误复用

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

# P13 · Data Synthesis Engine

阶段目标：实现多源清洗、实体解析、时空对齐、合并和派生。

## P13-001 · 实现 Build 创建

**目标**：定义目标 unit、key、time、output。

**前置依赖**：无

**实施动作**：
1. 从用户需求和所选 datasets 创建 BuildConfig
2. 默认 missing_policy=none
3. 默认禁止 m:m

**必须产物**：
- BuildConfig

**单项验收标准**：
- [ ] 未明确 key 时不会直接 merge

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P13-002 · 实现 Input Compatibility Scan

**目标**：执行前先发现粒度/时间/许可/键冲突。

**前置依赖**：无

**实施动作**：
1. 比较 schema/row/key/time/geo/license
2. 产生 blocking/warning

**必须产物**：
- compatibility report

**单项验收标准**：
- [ ] 明显单位层级冲突能阻止自动合成

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P13-003 · 实现 Canonical Field Map

**目标**：原列映射统一目标字段。

**前置依赖**：无

**实施动作**：
1. 保留 source dataset/source field
2. 一对多/多对一映射显式

**必须产物**：
- field map

**单项验收标准**：
- [ ] 最终列可追溯原列

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P13-004 · 实现单位转换框架

**目标**：只进行明确可验证转换。

**前置依赖**：无

**实施动作**：
1. 注册 conversion
2. 记录 factor/formula
3. 无法确定单位不转换

**必须产物**：
- unit converter

**单项验收标准**：
- [ ] 比例↔百分比转换正确且有 provenance

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P13-005 · 实现国家实体 Resolver

**目标**：统一 ISO2/ISO3/name/alias。

**前置依赖**：无

**实施动作**：
1. 版本化 alias table
2. confidence

**必须产物**：
- country resolver

**单项验收标准**：
- [ ] US/USA/United States 同 canonical ID

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P13-006 · 实现中国省级 Resolver

**目标**：名称、简称和代码统一。

**前置依赖**：无

**实施动作**：
1. 版本化行政区表
2. 省/自治区/直辖市别名

**必须产物**：
- province resolver

**单项验收标准**：
- [ ] 北京/北京市/110000 匹配

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P13-007 · 实现中国地级市 Resolver

**目标**：支持地级行政区与历史版本基础。

**前置依赖**：无

**实施动作**：
1. 地级名称/代码
2. valid_from/valid_to
3. 历史变化 warning

**必须产物**：
- prefecture resolver

**单项验收标准**：
- [ ] 历史不存在实体不静默映射到现代城市

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P13-008 · 实现 Fuzzy Entity Resolver

**目标**：只作为后备。

**前置依赖**：无

**实施动作**：
1. 候选相似度
2. 阈值
3. 低置信人工确认/阻塞

**必须产物**：
- fuzzy resolver

**单项验收标准**：
- [ ] 低于阈值不会自动进入 final

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P13-009 · 实现年度时间规范化

**目标**：统一 year。

**前置依赖**：无

**实施动作**：
1. string/int/date→year
2. 财政年标记

**必须产物**：
- year normalizer

**单项验收标准**：
- [ ] FY2020 不无提示当自然年

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P13-010 · 实现月/季度规范化

**目标**：统一 period。

**前置依赖**：无

**实施动作**：
1. 季度/月解析和排序

**必须产物**：
- period normalizer

**单项验收标准**：
- [ ] 2020Q1 等正确

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P13-011 · 实现频率冲突检测

**目标**：不同频率不得盲合。

**前置依赖**：无

**实施动作**：
1. annual/quarter/month/day compare

**必须产物**：
- frequency guard

**单项验收标准**：
- [ ] 月度+年度直接 join 被阻止

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P13-012 · 实现 Aggregation

**目标**：明确 sum/mean/last/weighted。

**前置依赖**：无

**实施动作**：
1. 操作参数显式
2. 写 provenance

**必须产物**：
- aggregation op

**单项验收标准**：
- [ ] 月→年方法在 lineage 可见

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P13-013 · 实现 Append

**目标**：同 schema 纵向拼接。

**前置依赖**：无

**实施动作**：
1. 列对齐
2. 类型一致性
3. source row provenance

**必须产物**：
- append op

**单项验收标准**：
- [ ] 结果行数可解释

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P13-014 · 实现 Keyed Join

**目标**：显式 left/inner/full。

**前置依赖**：无

**实施动作**：
1. key
2. cardinality validation
3. collision suffix policy

**必须产物**：
- join op

**单项验收标准**：
- [ ] 声明 1:1 遇到重复立即失败

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P13-015 · 实现 Join Coverage

**目标**：统计匹配率和未匹配实体。

**前置依赖**：无

**实施动作**：
1. matched/unmatched left/right
2. 示例

**必须产物**：
- join report

**单项验收标准**：
- [ ] UI/报告可看到 coverage

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P13-016 · 实现 Join Explosion Guard

**目标**：阻止笛卡尔积。

**前置依赖**：无

**实施动作**：
1. 预估 cardinality/output rows
2. m:m 默认阻塞

**必须产物**：
- join guard

**单项验收标准**：
- [ ] 异常重复 key 不产生巨量结果

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P13-017 · 实现 Missing Policy

**目标**：默认不填。

**前置依赖**：无

**实施动作**：
1. none/drop/ffill/bfill/interpolate/impute 接口
2. 逐列配置

**必须产物**：
- missing policy

**单项验收标准**：
- [ ] 无配置时 0 个值被插补

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P13-018 · 实现插补值标记

**目标**：所有生成值可追溯。

**前置依赖**：无

**实施动作**：
1. mask/operation id/method/parameters

**必须产物**：
- imputation lineage

**单项验收标准**：
- [ ] 任意插补值能查询方法

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P13-019 · 实现 Recode

**目标**：类别编码统一。

**前置依赖**：无

**实施动作**：
1. value labels
2. mapping table
3. unknown category

**必须产物**：
- recode op

**单项验收标准**：
- [ ] 0/1、1/2、M/F fixture 可统一且保留原码映射

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P13-020 · 实现 Reshape

**目标**：wide/long。

**前置依赖**：无

**实施动作**：
1. id_vars/value_vars
2. 列名冲突保护

**必须产物**：
- reshape op

**单项验收标准**：
- [ ] fixture 可正确转换

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P13-021 · 实现 Derived Variable

**目标**：公式受控并可追溯。

**前置依赖**：无

**实施动作**：
1. 安全表达式/函数
2. 记录依赖字段和公式

**必须产物**：
- derive op

**单项验收标准**：
- [ ] 修改公式会改变 build version/provenance

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P13-022 · 实现 Build Plan Preview

**目标**：执行前展示所有步骤。

**前置依赖**：无

**实施动作**：
1. inputs/keys/semantic conversions/entity/time/join/missing/output
2. 高风险突出

**必须产物**：
- plan preview

**单项验收标准**：
- [ ] 用户能在执行前看到删除/插补/聚合

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P13-023 · 实现 Build DAG Executor

**目标**：按依赖执行全部操作。

**前置依赖**：无

**实施动作**：
1. 拓扑排序
2. 幂等 retry
3. 错误停止

**必须产物**：
- build executor

**单项验收标准**：
- [ ] 重试不会重复叠加 transform

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P13-024 · 实现 Stage Checkpoint

**目标**：长任务可恢复。

**前置依赖**：无

**实施动作**：
1. 每阶段 intermediate artifact
2. checkpoint metadata

**必须产物**：
- checkpoints

**单项验收标准**：
- [ ] 强杀后从最近安全点恢复

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P13-025 · 实现大数据执行路径

**目标**：1GB 级别不依赖全表多份复制。

**前置依赖**：无

**实施动作**：
1. 根据现有栈采用 streaming/Arrow/Polars/DuckDB 等可靠方案
2. 清理临时文件

**必须产物**：
- large-data executor

**单项验收标准**：
- [ ] 压力测试不 OOM，峰值内存有记录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

# P14 · 质量审计、Provenance 与最终数据包

阶段目标：让结果真正可用于科研和审计。

## P14-001 · 建立 Validation Framework

**目标**：统一检查结果。

**前置依赖**：无

**实施动作**：
1. severity/code/field/rows/message/remediation

**必须产物**：
- validation model

**单项验收标准**：
- [ ] INFO/WARNING/ERROR/BLOCKING 可区分

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P14-002 · 实现 Key Uniqueness Check

**目标**：验证目标主键。

**前置依赖**：无

**实施动作**：
1. duplicate keys/count/sample

**必须产物**：
- key validation

**单项验收标准**：
- [ ] panel key 重复触发 blocking/error

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P14-003 · 实现 Missing Audit

**目标**：核心变量和总体缺失。

**前置依赖**：无

**实施动作**：
1. field rate
2. core threshold
3. by entity/time

**必须产物**：
- missing report

**单项验收标准**：
- [ ] 超阈值能告警

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P14-004 · 实现 Range/Impossible Value Check

**目标**：识别明显错误。

**前置依赖**：无

**实施动作**：
1. 用户/语义约束
2. 比例/年龄等通用检查

**必须产物**：
- range validation

**单项验收标准**：
- [ ] 约束 0-100 时 150 被检测

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P14-005 · 实现 Temporal Gap Check

**目标**：发现面板缺期。

**前置依赖**：无

**实施动作**：
1. 按 entity 分组检测 gaps

**必须产物**：
- temporal report

**单项验收标准**：
- [ ] 缺 2020 能列出

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P14-006 · 整合 Join Coverage Validation

**目标**：低匹配率不得静默。

**前置依赖**：无

**实施动作**：
1. 阈值和 unmatched samples

**必须产物**：
- join validation

**单项验收标准**：
- [ ] coverage 低于 blocking threshold 不生成无警告 final

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P14-007 · 实现 Source Provenance

**目标**：每个 Artifact 有完整来源。

**前置依赖**：无

**实施动作**：
1. Provider/URL/DOI/version/license/timestamp/checksum/access

**必须产物**：
- sources.json

**单项验收标准**：
- [ ] 所有 final input 都能找到 source record

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P14-008 · 实现 Transformation Provenance

**目标**：每个操作前后可审计。

**前置依赖**：无

**实施动作**：
1. operation/params/input/output/row-col before-after/warnings/code version

**必须产物**：
- transformations.json

**单项验收标准**：
- [ ] Build 每一步有 operation_id

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P14-009 · 实现字段级 Lineage

**目标**：final column 追溯 source field。

**前置依赖**：无

**实施动作**：
1. rename/map/convert/join/derive graph

**必须产物**：
- lineage.json

**单项验收标准**：
- [ ] 随机 10 列均可追溯

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P14-010 · 生成 Quality Report

**目标**：给用户可读的数据质量报告。

**前置依赖**：无

**实施动作**：
1. missing/key/join/range/time/inserted values/warnings

**必须产物**：
- quality_report.html

**单项验收标准**：
- [ ] 指标与 validator 原始结果一致

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P14-011 · 生成 Methodology Report

**目标**：说明数据如何得到。

**前置依赖**：无

**实施动作**：
1. 数据源、版本、清洗、变量对齐、实体、时间、join、插补、限制

**必须产物**：
- methodology.md

**单项验收标准**：
- [ ] 不得出现 provenance 中不存在的虚构步骤

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P14-012 · 生成 Reproduce Script

**目标**：固定流程可重建。

**前置依赖**：无

**实施动作**：
1. 从 manifest/pipeline 生成 reproduce.py 或项目等价脚本
2. 锁定依赖版本

**必须产物**：
- reproduce script

**单项验收标准**：
- [ ] 干净 fixture 环境可重建同 schema/行列/关键 hash

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P14-013 · 实现 CSV/Parquet/XLSX Export

**目标**：提供常用最终格式。

**前置依赖**：无

**实施动作**：
1. 类型转换
2. XLSX 行数限制处理
3. 大数据优先 Parquet

**必须产物**：
- final exports

**单项验收标准**：
- [ ] 三个格式在可支持规模下都能读取且行列一致

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P14-014 · 组装 Data Package

**目标**：按 PRD 标准目录交付。

**前置依赖**：无

**实施动作**：
1. final/raw refs/intermediate/metadata/provenance/reports/scripts
2. 写顶层 manifest

**必须产物**：
- build package

**单项验收标准**：
- [ ] 目录完整
- [ ] manifest 文件存在性全校验

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

# P15 · 前端产品体验

阶段目标：把底层能力完整暴露为可理解、可控制的产品。

## P15-001 · 实现 Metis Data 三栏主工作区

**目标**：建立稳定桌面布局。

**前置依赖**：无

**实施动作**：
1. 左任务树
2. 中 Live Browser/Data Preview
3. 右 Agent Events

**必须产物**：
- main workspace

**单项验收标准**：
- [ ] 1440px 桌面完整可用
- [ ] 不存在核心控件遮挡

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P15-002 · 实现自然语言数据任务输入

**目标**：聊天输入创建真实 Task。

**前置依赖**：无

**实施动作**：
1. 输入→Requirement Parser→Task
2. 显示 loading/error

**必须产物**：
- task composer

**单项验收标准**：
- [ ] 提交后 DB 有真实 task

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P15-003 · 实现 Requirement Card

**目标**：显示 Agent 解析和假设。

**前置依赖**：无

**实施动作**：
1. 时间/地理/单位/变量/来源偏好
2. 可编辑并重新规划

**必须产物**：
- requirement card

**单项验收标准**：
- [ ] 修改粒度后 Provider/Query Plan 更新

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P15-004 · 实现 Provider Progress

**目标**：实时展示并行搜索。

**前置依赖**：无

**实施动作**：
1. queued/running/done/error/result count

**必须产物**：
- search progress UI

**单项验收标准**：
- [ ] 单 Provider 错误不遮蔽其他成功

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P15-005 · 实现 Candidate Cards

**目标**：直接比较数据适配度。

**前置依赖**：无

**实施动作**：
1. source/time/geo/unit/variables/license/access/reasons/limitations

**必须产物**：
- candidate UI

**单项验收标准**：
- [ ] 用户无需打开网页即可识别关键差异

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P15-006 · 实现 Dataset Detail

**目标**：完整 metadata/files/codebook。

**前置依赖**：无

**实施动作**：
1. 来源/DOI/license/version/variables/files/access

**必须产物**：
- dataset detail

**单项验收标准**：
- [ ] 信息来源与后端 Candidate/Metadata 一致

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P15-007 · 实现 Live Browser View

**目标**：展示真实 Browser。

**前置依赖**：无

**实施动作**：
1. 嵌入或同步 Browser view
2. owner/session/url 状态

**必须产物**：
- browser UI

**单项验收标准**：
- [ ] 用户肉眼能看到真实页面点击/输入/滚动

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P15-008 · 实现 Pause/Takeover/Return/Stop

**目标**：控制权显式。

**前置依赖**：无

**实施动作**：
1. 四个动作与后端 controller 连接

**必须产物**：
- browser controls

**单项验收标准**：
- [ ] 接管后 Agent 0 输入

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P15-009 · 实现 User Intervention Card

**目标**：高风险节点清楚告诉用户做什么。

**前置依赖**：无

**实施动作**：
1. reason/instruction/continue

**必须产物**：
- intervention UI

**单项验收标准**：
- [ ] 用户不读开发日志也能处理 CAPTCHA/MFA/协议

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P15-010 · 实现 Accounts 页面

**目标**：管理已有账号和 session。

**前置依赖**：无

**实施动作**：
1. provider search/status/login/remove/last verified

**必须产物**：
- accounts UI

**单项验收标准**：
- [ ] 删除后状态实时变未登录

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P15-011 · 实现 Auto Registration 设置

**目标**：全局和平台级开关。

**前置依赖**：无

**实施动作**：
1. 说明自动范围和必须用户处理事项

**必须产物**：
- registration settings

**单项验收标准**：
- [ ] 关闭后后台不会注册

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P15-012 · 实现 Downloads 页面

**目标**：查看进度、来源、文件和失败。

**前置依赖**：无

**实施动作**：
1. job list/detail/retry/open raw

**必须产物**：
- downloads UI

**单项验收标准**：
- [ ] 中断任务可正确重试

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P15-013 · 实现 Data Preview

**目标**：高性能表格和 schema/profile。

**前置依赖**：无

**实施动作**：
1. virtualized table
2. 列搜索
3. 统计摘要

**必须产物**：
- preview UI

**单项验收标准**：
- [ ] 10万行不一次性渲染

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P15-014 · 实现 Build Builder

**目标**：选择数据和配置合成。

**前置依赖**：无

**实施动作**：
1. inputs/key/map/unit/entity/time/join/missing
2. 显示 plan

**必须产物**：
- build UI

**单项验收标准**：
- [ ] m:m blocking 在执行前可见

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P15-015 · 实现 Build Progress

**目标**：展示 checkpoint 和 QA。

**前置依赖**：无

**实施动作**：
1. stage/progress/warnings/recovery

**必须产物**：
- build progress

**单项验收标准**：
- [ ] 失败能定位到具体阶段

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P15-016 · 实现 Provenance Viewer

**目标**：查看 source、transform、字段血缘。

**前置依赖**：无

**实施动作**：
1. 来源列表
2. operation timeline
3. column lineage

**必须产物**：
- provenance UI

**单项验收标准**：
- [ ] 点击 final 字段可见完整 source chain

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P15-017 · 实现 Final Build Summary

**目标**：提供最终交付。

**前置依赖**：无

**实施动作**：
1. rows/columns/time/geo/sources/missing/join/warnings/download package

**必须产物**：
- build summary

**单项验收标准**：
- [ ] 用户可直接判断数据是否适用

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P15-018 · 限制 Agent 面板为可解释摘要

**目标**：不显示隐式推理链。

**前置依赖**：无

**实施动作**：
1. 显示动作、结果、简短依据、错误和用户请求
2. 隐藏 secret/内部 chain-of-thought

**必须产物**：
- agent event UI

**单项验收标准**：
- [ ] 不暴露私有推理或 secrets

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

# P16 · 安全、E2E、恢复、性能与发布

阶段目标：用可执行证据证明产品完整。

## P16-001 · 全仓 Secrets Scan

**目标**：发布前阻止凭据泄露。

**前置依赖**：无

**实施动作**：
1. pre-commit/CI scan
2. 扫描 fixture/log/config

**必须产物**：
- security scan

**单项验收标准**：
- [ ] 放入测试 secret CI 必须失败

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P16-002 · 日志脱敏回归

**目标**：覆盖全部秘密类型。

**前置依赖**：无

**实施动作**：
1. password/token/cookie/API key/OTP/Auth header

**必须产物**：
- redaction E2E

**单项验收标准**：
- [ ] 所有测试 secret 均无法在日志全文找到

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P16-003 · 路径与压缩安全回归

**目标**：防 traversal/zip slip。

**前置依赖**：无

**实施动作**：
1. download/upload/unzip/workspace

**必须产物**：
- path security tests

**单项验收标准**：
- [ ] 恶意 fixture 不越界写文件

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P16-004 · Browser Intervention E2E

**目标**：验证不能绕过 CAPTCHA/MFA。

**前置依赖**：无

**实施动作**：
1. 测试站点模拟 captcha/mfa/agreement

**必须产物**：
- browser safety E2E

**单项验收标准**：
- [ ] 均进入 WAITING_USER 且无绕过操作

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P16-005 · 公开 API Golden Subflow

**目标**：Requirement→World Bank/ILO→Raw→Profile。

**前置依赖**：无

**实施动作**：
1. 使用真实 smoke + recorded fixture

**必须产物**：
- E2E evidence

**单项验收标准**：
- [ ] 完整 Artifact/Provenance 生成

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P16-006 · 学术仓储 Golden Subflow

**目标**：Zenodo/Dataverse 搜索下载。

**前置依赖**：无

**实施动作**：
1. search→metadata→download→profile

**必须产物**：
- E2E evidence

**单项验收标准**：
- [ ] DOI/license/checksum 完整

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P16-007 · 认证下载 E2E

**目标**：测试账号路径。

**前置依赖**：无

**实施动作**：
1. Vault→login→session→download
2. 使用测试站点/专用测试账户，不提交真实凭据

**必须产物**：
- auth E2E

**单项验收标准**：
- [ ] 重启 session 可复用，日志无秘密

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P16-008 · 自动注册 E2E

**目标**：普通注册和验证挂起。

**前置依赖**：无

**实施动作**：
1. consent→password→form→success/verify

**必须产物**：
- registration E2E

**单项验收标准**：
- [ ] 关闭 consent 时 0 次提交

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P16-009 · Takeover E2E

**目标**：Agent→Human→Agent。

**前置依赖**：无

**实施动作**：
1. 中途用户改变页面
2. 交还重新感知

**必须产物**：
- takeover E2E

**单项验收标准**：
- [ ] 不使用旧坐标盲操作

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P16-010 · 国家面板合成 Golden Test

**目标**：至少两个来源构建 panel。

**前置依赖**：无

**实施动作**：
1. World Bank + ILO fixture
2. ISO3/year join
3. QA/lineage/export

**必须产物**：
- golden build

**单项验收标准**：
- [ ] 最终包完整且 join coverage 可解释

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P16-011 · 中国行政区合成 E2E

**目标**：省/地级名称代码与历史。

**前置依赖**：无

**实施动作**：
1. 别名和历史变化 fixture

**必须产物**：
- entity E2E

**单项验收标准**：
- [ ] 现代别名统一，历史冲突警告

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P16-012 · 变量语义冲突 E2E

**目标**：验证同名不同义。

**前置依赖**：无

**实施动作**：
1. current vs constant GDP

**必须产物**：
- semantic E2E

**单项验收标准**：
- [ ] 不能静默覆盖

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P16-013 · m:m Join 防爆 E2E

**目标**：验证 cardinality guard。

**前置依赖**：无

**实施动作**：
1. 重复 key fixture

**必须产物**：
- join safety E2E

**单项验收标准**：
- [ ] 无笛卡尔积 final

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P16-014 · 插补透明性 E2E

**目标**：验证生成值可追溯。

**前置依赖**：无

**实施动作**：
1. linear interpolation fixture

**必须产物**：
- missing E2E

**单项验收标准**：
- [ ] 插补 mask/operation/report 全一致

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P16-015 · 崩溃恢复 E2E

**目标**：搜索、下载、Build 各强杀一次。

**前置依赖**：无

**实施动作**：
1. 重启恢复

**必须产物**：
- recovery E2E

**单项验收标准**：
- [ ] 无重复外部提交/Artifact/假完成

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P16-016 · 任务取消 E2E

**目标**：Search/Download/Build 均可取消。

**前置依赖**：无

**实施动作**：
1. 传播 cancellation
2. 回收 workers

**必须产物**：
- cancel E2E

**单项验收标准**：
- [ ] 取消后无新 final/外部请求

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P16-017 · 1GB 级性能测试

**目标**：验证大文件路径。

**前置依赖**：无

**实施动作**：
1. 记录时间、峰值内存、临时磁盘
2. 不要求 CI 每次运行，可发布前运行

**必须产物**：
- benchmark report

**单项验收标准**：
- [ ] 无 OOM
- [ ] UI 不冻结

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P16-018 · Provider 故障隔离

**目标**：单平台 500/timeout/schema change。

**前置依赖**：无

**实施动作**：
1. 模拟故障

**必须产物**：
- resilience tests

**单项验收标准**：
- [ ] 其他 Provider 继续完成

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P16-019 · 全链路科研 Golden Scenario

**目标**：从一句研究需求到最终 Data Package。

**前置依赖**：无

**实施动作**：
1. 至少 4 Provider 搜索
2. 至少 2 个数据源实际进入 Build
3. 完整 provenance/reproduce

**必须产物**：
- golden acceptance artifact

**单项验收标准**：
- [ ] 总体体验收 A1-A10 全通过

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

## P16-020 · 生成 v1.0 Final Acceptance Report

**目标**：以证据宣布是否完成。

**前置依赖**：无

**实施动作**：
1. 填写全部 P0/P1
2. Provider Matrix
3. 测试命令和结果
4. Known Limitations 只能放 P1/P2

**必须产物**：
- Final Acceptance Report

**单项验收标准**：
- [ ] 任何 P0 FAIL 时最终 verdict 必须 FAIL

**失败判定**：任一必需产物不存在、任一验收项不满足、存在伪实现或测试被规避时，本任务不得标记 DONE。

---

# P17 · Phase Regression Gate

每完成任一 Phase，必须额外执行：

- [ ] 本 Phase 所有非明确外部阻塞任务均 DONE；
- [ ] unit tests 全绿；
- [ ] integration/contract tests 全绿；
- [ ] 当前已具备的 E2E 子集全绿；
- [ ] lint/typecheck/format-check 全绿；
- [ ] secrets scan 全绿；
- [ ] 无新增未说明 TODO/placeholder；
- [ ] architecture/change log 已更新；
- [ ] `IMPLEMENTATION_PROGRESS.md` 与实际 Git/test 状态一致；
- [ ] 生成 `artifacts/test-reports/<phase>.md`；

# P18 · 禁止自行简化清单

- [ ] 不把 Live Browser 改成动画或截图轮播；
- [ ] 不把 Browser 主要定位改成固定坐标；
- [ ] 不用一个全平台共享明文密码；
- [ ] 不把 Data.gov、data.europa.eu、Google Dataset Search 等目录/索引误当文件托管站；
- [ ] 不因标题包含关键词就宣称数据具备某变量；
- [ ] 不因同名字段就默认含义相同；
- [ ] 不在 join 前省略 cardinality 检查；
- [ ] 不覆盖 raw；
- [ ] 不把 UNKNOWN License 当开放；
- [ ] 不自动代用户接受 Restricted Data Agreement；
- [ ] 不生成伪造观测以补齐数据；
- [ ] 不隐藏插补、聚合、单位换算；
- [ ] 不虚报 Provider integration level；

# P19 · 产品最终 Definition of Done

只有同时满足：

1. 本任务清单 v1.0 必需任务完成或仅存在有证据的外部平台客观阻塞；
2. 总体体验收所有 P0 通过；
3. 至少 8 个代表性 Provider 完整真实跑通；
4. 全 Provider Registry 无遗漏且均至少具备实际 P1 搜索能力或记录可验证的外部不可实现原因；
5. Live Browser + Pause + Takeover + Return 通过；
6. Existing Account + Auto Registration + User Intervention 通过；
7. 多源数据合成通过；
8. Raw immutable 通过；
9. Provenance/字段 lineage 完整；
10. Reproduce Golden Test 通过；
11. Secrets Scan 通过；
12. Crash Recovery 通过；
13. `Final Acceptance Report` 为 PASS；

才允许标记 `Metis Data v1.0 DONE`。