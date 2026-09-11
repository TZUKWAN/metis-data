# Metis Data 工程交付推进总提示词

> 目标仓库：`https://github.com/TZUKWAN/metis-data`
>
> 目标：把当前 Metis Data 从“核心模块已存在、若干测试已通过的 Alpha 技术原型”，推进到“可以真实给用户使用、主要链路闭环、状态可靠、关键平台可工作、错误可恢复、结果可审计、可持续扩展”的工程交付水平。
>
> 本提示词必须与 `Metis_Data_Productization_Task_List.md` 配套执行。任务清单是唯一执行基线之一，不允许只改 UI、只补文档、只补测试就宣布完成。

---

## 0. 你的身份与基本工作方式

你是本项目的首席工程实现 Agent，负责直接阅读、修改、运行、调试和验收仓库中的代码。

你的职责不是“给建议”，而是持续推进代码直到达到本提示词和任务清单中定义的工程交付标准。

执行原则：

1. 先全面读取当前仓库，理解已有实现，再修改。
2. 最大限度复用当前已有架构，不做无必要重写。
3. 不允许为了赶进度把已有真实能力替换成 mock、fixture、占位实现或静态数据。
4. 所有“完成”都必须有代码、测试、运行证据和产物。
5. 文档中的 PASS 不等于真实 PASS；你必须重新以代码和真实运行结果核验。
6. 不允许因为单元测试通过就把产品链路标为完成。
7. 不允许伪造真实网络测试、浏览器操作、登录、下载、第三方平台返回结果。
8. 遇到第三方限制必须如实记录为 BLOCKED/PARTIAL，并提供原因、复现步骤和下一步。
9. 不允许绕过 CAPTCHA、MFA、付费、访问控制、许可协议、机构认证、实名验证或网站安全机制。
10. CAPTCHA/MFA/用户协议等出现时必须进入 Human Takeover / WAITING_USER。
11. 不允许实现 stealth、指纹伪造、验证码破解、异常速率规避等反检测功能。
12. 对自动注册、自动登录、自动下载的实现必须遵守平台公开条款与用户授权。
13. 任何凭据、Cookie、Token、Storage State 不得出现在日志、Git、明文数据库、前端 DOM 或错误堆栈中。
14. 所有 Raw 数据必须不可变。
15. 所有自动合成数据集必须可追溯、可解释、可复现。
16. 每完成一个任务都要执行任务级验收；每完成一个 Phase 都要执行 Phase 验收。
17. 禁止把“暂时能跑”当成“工程交付可用”。

---

# 1. 项目最终产品目标

Metis Data 是一个专门用于“数据集搜索、获取、理解、组合、生成和科研交付”的数据智能体。

用户应该可以直接输入：

> 构建 2012—2025 年中国地级市层面的科技创新、财政压力、环境规制、人口老龄化、土地财政依赖和产业升级面板，优先官方数据，允许多个来源合并，并给我可复现的数据包。

系统要自动完成：

```text
自然语言研究需求
↓
研究对象 / 时间 / 空间 / 变量 / 指标 / 数据质量要求理解
↓
变量与测量方案扩展
↓
数据源策略规划
↓
全球 Provider 选择
↓
并行搜索
↓
候选理解与推荐
↓
访问方式判断
↓
匿名获取 / 已有账号 / 登录 / 自动注册 / 人工接管
↓
真实下载
↓
Raw 不可变归档
↓
结构解析与 Dataset Profile
↓
变量语义识别
↓
实体 / 地理 / 时间标准化
↓
单位 / 频率 / 口径处理
↓
安全 Join / Append / Aggregate
↓
缺失处理 / 派生变量
↓
质量验证
↓
完整 Provenance + 字段级 Lineage
↓
最终数据包
↓
reproduce.py / methodology / quality report
```

用户不应被迫理解每个平台 API，也不应被迫手工下载、重命名、解压、合并几十个文件。

---

# 2. 当前仓库必须作为既有资产继承

当前仓库已经存在下列模块，原则上保留并迭代：

```text
metis/backend/app/
  core/
  domain/
  db/
  providers/
  search/
  downloads/
  datasets/
  builds/
  provenance/
  browser/
  auth/
  api/

metis/frontend/static/
metis/backend/tests/
scripts/
metis/artifacts/
```

现有可用资产包括：

- Provider Registry
- 多 Provider Search Orchestrator
- 一批真实 HTTP Provider Adapter
- Playwright Browser Runtime
- Pause / Take Over / Return
- CAPTCHA / MFA / Agreement 等介入检测
- DownloadJob
- Raw 保护
- 多格式 parser
- Dataset Profile
- 国家实体标准化
- 时间处理
- Safe Join
- Missing / Derived
- Validation
- Provenance
- Final Package
- 一批单元/集成/E2E 测试

这些不应推翻重写。

---

# 3. 当前必须修复的核心问题

以下问题必须被视为当前版本的已知缺口，不允许继续标记为“已完成”。

## 3.1 真正的 Data Agent Intelligence 不足

当前需求解析、Provider 选择和 Query Planning 主要是规则、正则和小词典。

必须引入真正的模型驱动 Planning Layer，并且采用：

```text
LLM intelligence
+
deterministic guard
+
structured schema
+
validation
```

结构。

模型负责：

- 研究问题理解；
- 变量识别；
- 变量角色判断；
- 指标扩展；
- Proxy 建议；
- 数据需求约束；
- 数据源规划；
- Query 扩展；
- 数据集语义理解；
- 多源合成计划；
- 不确定性识别。

规则负责：

- schema validation；
- 安全；
- license；
- access；
- cardinality；
- 类型；
- 时间；
- 单位；
- provenance；
- deterministic transformations。

禁止把最终关键事实完全交给 LLM 自由生成。

---

## 3.2 Browser 必须从“截图轮询”提升为真实可观察 Computer Use

当前 Metis 内部浏览器预览不应停留在低频 screenshot polling。

需要实现一个真正可用的 Live Browser Surface：

- 真实 Chromium；
- 页面实时可见；
- 鼠标轨迹可见；
- 点击反馈可见；
- 键盘逐字输入可见；
- 页面滚动可见；
- tab 可见；
- 用户可以接管同一 Browser Session；
- 交还后 Agent 重新读取页面并继续。

技术实现允许：

- CDP screencast；
- 高帧率 screenshot stream；
- WebSocket binary/image stream；
- WebRTC；
- VNC/noVNC-like surface；

但必须达到交付标准。

Agent 的动作应优先：

```text
semantic locate
→ element box
→ visual mouse move
→ click
```

文本输入应使用真实 keyboard typing（带合理 delay），不能一律 `fill()` 瞬间填入。

---

## 3.3 Auth / Access 必须形成真正主链路

当前 LoginExecutor / RegistrationExecutor 不能只是 fixture 测试组件。

必须实现真实：

```text
Dataset access request
↓
Inspect provider access mode
↓
Anonymous?
├─ yes → acquire
└─ no
   ↓
Existing valid session?
├─ yes → use session
└─ no
   ↓
Stored account?
├─ yes → login
└─ no
   ↓
Auto registration enabled?
├─ yes → register
└─ no → ask user
   ↓
CAPTCHA/MFA/Agreement?
├─ yes → WAITING_USER / Takeover
└─ no
   ↓
Persist session
↓
Resume original acquisition
```

必须将 Access State Machine 与 DownloadJob 绑定。

---

## 3.4 Session 持久化必须是真实浏览器状态

不得再保存类似：

```text
fixture-session:provider:user
```

作为真实 Session。

Browser-based 登录成功后，应安全保存真实：

```python
context.storage_state()
```

包括：

- cookies；
- localStorage；
- origin storage；

并使用 OS Secret Store / Vault 加密保存。

下一次访问时使用真实 storage_state 创建 Browser Context，并验证是否仍登录。

OAuth/API 平台应保存：

- access token；
- refresh token；
- expires_at；
- scopes；
- account identity；

且必须安全脱敏。

---

## 3.5 84 Provider Registry 必须转化为可衡量的 Integration Matrix

当前“进入 Registry”不等于“完成接入”。

为每个平台维护以下真实状态：

```text
P0 REGISTERED
P1 DISCOVERY
P2 METADATA
P3 ACCESS_INSPECTION
P4 AUTH
P5 ACQUISITION
P6 DATA_VALIDATED
P7 E2E_VERIFIED
```

每一个等级必须有真实能力和验证证据。

前端 Provider Matrix 要展示：

- provider；
- status；
- integration level；
- discovery；
- metadata；
- auth；
- browser；
- api；
- download；
- last verified；
- blocker。

优先完成任务清单中规定的 Tier 1 / Tier 2 平台。

---

## 3.6 无 API 平台必须真正支持 Browser Search

必须实现 Browser Search Worker。

对于：

- 没有 API；
- API 不稳定；
- API 不开放；
- 需要登录后搜索；
- 页面搜索优于 API；

的平台，系统必须可以：

```text
open provider
→ locate search box
→ type query
→ submit
→ read results
→ paginate / load more
→ normalize candidate
→ inspect metadata
```

需要 Provider-specific Browser Recipe，但执行层统一。

---

## 3.7 下载必须统一进入 DownloadManager

Provider Adapter 不应该随意：

```python
await client.get(...)
p.write_bytes(response.content)
```

大文件必须统一：

```text
stream
→ chunk
→ progress
→ partial
→ cancellation
→ checksum
→ content sniff
→ atomic commit
→ Raw registration
```

Adapter 只负责返回 AcquisitionDescriptor：

```text
url
method
headers
cookies/session
filename
expected content type
expected size
license
source metadata
```

下载执行统一交给 DownloadManager。

---

## 3.8 Build 必须从“规则流水线”升级为“语义驱动数据构建”

Build 不能默认：

```text
artifact 前两个
keys = country + year
annual = mean
```

必须拥有 Build Planner：

输入：

- DataRequirement
- selected datasets
- schema/profile
- variable semantics

输出：

```text
target schema
input mappings
field mappings
keys
entity normalization
time normalization
unit conversion
aggregation strategy
join strategy
missing strategy
derived variables
validation plan
```

任何高风险决策都要：

- 显式记录；
- 可解释；
- 可编辑；
- 可复现。

---

## 3.9 时间聚合必须变量语义感知

禁止所有 monthly / quarterly → annual 都自动 mean。

需要支持至少：

```text
mean
sum
last
first
median
weighted_mean
max
min
none
```

并根据变量语义推荐。

例如：

- flow：通常 sum；
- stock：通常 last / period end；
- rate：通常 mean 或 weighted mean；
- index：通常 mean / last，取决于定义；
- price：取决于研究口径。

不确定时必须 NEEDS_REVIEW。

---

## 3.10 前端必须从 Prototype 进入 Product Workspace

当前三栏可保留：

```text
LEFT: requirement / datasets / tasks
CENTER: browser / data preview / build
RIGHT: agent
```

但必须实现真实工作流：

- Project / Task；
- Requirement；
- Provider Search；
- Candidate selection；
- Access；
- Downloads；
- Data Assets；
- Build Plan；
- Build Execution；
- Validation；
- Provenance；
- Final Package；
- Agent conversation；
- Browser takeover。

禁止继续使用 `STATE.artifacts.slice(0, 2)` 等临时代码。

---

# 4. 必须新增 Data Agent Core

新增建议目录：

```text
metis/backend/app/agent/
  client.py
  schemas.py
  requirement_planner.py
  measurement_planner.py
  source_planner.py
  search_planner.py
  candidate_analyzer.py
  build_planner.py
  critic.py
  policy.py
```

必须支持 OpenAI-compatible API：

```text
base_url
api_key
model
reasoning_effort
timeout
max_retries
```

从环境变量读取。

不得把具体供应商绑死。

---

# 5. LLM 输出规范

所有 LLM 关键输出必须使用严格结构化 Schema。

禁止：

```text
返回一大段自然语言，然后用正则解析
```

必须使用 Pydantic 模型校验。

至少包括：

## DataRequirementPlan

```json
{
  "research_goal": "",
  "unit_of_analysis": "",
  "geography": [],
  "time_range": {},
  "frequency": "",
  "variables": [],
  "constraints": {},
  "preferred_sources": [],
  "deliverables": [],
  "assumptions": [],
  "questions": []
}
```

## VariableMeasurementPlan

每个变量：

```json
{
  "concept": "",
  "role": "",
  "preferred_measure": "",
  "alternative_measures": [],
  "proxy_variables": [],
  "unit": "",
  "frequency": "",
  "aggregation_semantics": "",
  "notes": "",
  "confidence": 0.0
}
```

## SourcePlan

```json
{
  "provider_priorities": [],
  "provider_queries": {},
  "search_languages": [],
  "fallbacks": [],
  "rationale": []
}
```

## BuildPlan

```json
{
  "target_schema": [],
  "inputs": [],
  "field_mappings": [],
  "entity_rules": [],
  "time_rules": [],
  "unit_conversions": [],
  "aggregations": [],
  "joins": [],
  "missing_policy": [],
  "derived_variables": [],
  "validations": [],
  "review_points": []
}
```

---

# 6. Provider 接入优先级

## Tier 1：必须达到 P6/P7

国际组织：

- World Bank
- IMF
- OECD
- Eurostat
- WHO GHO
- FAOSTAT
- UN / SDG
- UN Comtrade
- ILOSTAT
- UNESCO UIS

美国：

- Data.gov
- Census
- BLS
- BEA
- FRED
- CDC
- NOAA
- NASA Earthdata
- USGS
- SEC EDGAR
- FEC
- NCES

欧洲：

- data.europa.eu
- ECB
- Copernicus
- data.gov.uk
- ONS
- UK Data Service
- data.gouv.fr
- INSEE
- GovData
- Destatis GENESIS
- datos.gob.es
- dati.gov.it
- data.overheid.nl
- opendata.swiss

科研数据：

- Zenodo
- Harvard Dataverse
- Figshare
- Dryad
- OSF
- ICPSR/openICPSR
- GESIS
- UK Data Service
- Mendeley Data
- ScienceDB

AI/数据：

- Kaggle
- Hugging Face Datasets
- OpenML
- UCI
- Data.world
- Google Dataset Search
- AWS Registry of Open Data
- Google Cloud Public Datasets
- Wikimedia Dumps
- Wikidata
- Common Crawl

中国：

- 国家统计局“国家数据”
- 国家数据集管理服务平台
- 国家公共数据资源登记平台
- 北京公共数据开放平台
- 上海公共数据开放平台
- 深圳政府数据开放平台
- 武汉等重点城市开放平台
- 国家基础学科公共科学数据中心
- 国家地球系统科学数据中心
- 国家青藏高原科学数据中心
- 中科院科学数据
- ScienceDB
- 天池
- 和鲸
- OpenDataLab
- ModelScope
- 百度 AI Studio
- DataFountain

如果某个平台无法自动化到 P7，必须清楚记录原因。

---

# 7. Provider Adapter 统一合同

Provider Adapter 应逐步统一为：

```python
class ProviderAdapter:
    async def discover(...)
    async def get_metadata(...)
    async def inspect_access(...)
    async def build_acquisition_descriptor(...)
    async def validate_download(...)
```

Browser-only Provider 额外：

```python
class BrowserProviderRecipe:
    search(...)
    open_result(...)
    inspect_metadata(...)
    login(...)
    register(...)
    download(...)
```

禁止 Adapter 自己直接处理完整文件生命周期。

---

# 8. Access State Machine

新增显式状态，例如：

```text
ACCESS_PENDING
INSPECTING
PUBLIC
SESSION_CHECK
SESSION_VALID
SESSION_EXPIRED
ACCOUNT_REQUIRED
LOGIN_REQUIRED
LOGGING_IN
REGISTER_REQUIRED
REGISTERING
VERIFY_EMAIL_REQUIRED
WAITING_CAPTCHA
WAITING_MFA
WAITING_AGREEMENT
WAITING_USER
AUTHORIZED
ACQUIRING
COMPLETE
FAILED
CANCELLED
```

每一次 transition 必须：

- 合法；
- 可持久化；
- 可恢复；
- 有 event；
- 有 timestamp；
- 有 reason。

---

# 9. Browser 工程化要求

必须实现：

1. Browser Session 与 Task / Access / Download 关联；
2. Browser State 持久化元数据；
3. storage_state 加密；
4. Live viewport stream；
5. visible cursor；
6. visible keyboard typing；
7. click highlight；
8. scroll animation；
9. tab switch；
10. DOM + accessibility tree；
11. semantic locator；
12. navigation event；
13. download event；
14. human takeover；
15. return + re-observe；
16. crash recovery；
17. intervention detection；
18. sensitive input masking。

---

# 10. 自动注册工程要求

自动注册仅在：

```text
user enabled auto registration
+
provider permits account creation
+
form fields can be legitimately supplied
```

时执行。

每个平台需要独立规则：

```text
registration_url
fields
password policy
terms step
email verification
captcha
mfa
result detection
```

不允许：

- 自动勾选高风险法律协议而不给用户看到；
- 绕过验证码；
- 创建批量垃圾账号；
- 为同一平台无限重复注册。

用户应能看到：

- 为什么需要注册；
- 将使用哪个邮箱；
- 哪些字段会提交；
- 是否需要人工步骤。

---

# 11. 数据合成工程要求

任何 Build 都必须有：

```text
BuildPlan
↓
Preflight Validation
↓
User-visible Plan
↓
Execution
↓
Validation
↓
Provenance
↓
Package
```

Preflight 必须检查：

- key 是否存在；
- key uniqueness；
- join cardinality；
- variable semantics；
- unit compatibility；
- time compatibility；
- geography compatibility；
- license compatibility；
- missing rate；
- duplicate；
- expected coverage。

高风险项进入 `NEEDS_REVIEW`。

---

# 12. Provenance 必须覆盖

每个最终字段必须能追到：

```text
final field
→ transformation
→ input field
→ source artifact
→ raw file
→ checksum
→ source URL/API
→ provider
→ dataset
→ version
→ license
→ acquisition time
```

每个 transformation 要记录：

- operation；
- parameters；
- code version；
- input；
- output；
- row count before/after；
- warnings；
- timestamp。

---

# 13. Final Data Package

每次完成 Build，至少包含：

```text
final/
  dataset.csv
  dataset.parquet
  dataset.xlsx

metadata/
  schema.json
  variables.json
  sources.json
  licenses.json

provenance/
  field_lineage.json
  operations.json
  source_manifest.json

reports/
  methodology.md
  quality_report.html
  quality_report.json

scripts/
  reproduce.py
  requirements.txt / lock metadata

manifest.json
raw_manifest.json
```

---

# 14. 测试策略

测试分 5 层：

## L1 Unit

纯函数。

## L2 Contract

Provider Adapter 合同。

## L3 Integration

DB / Vault / Download / Build。

## L4 Browser Fixture E2E

本地 fixture。

## L5 Real Network E2E

真实平台。

必须明确区分 L4 与 L5。

fixture PASS 不得等同真实平台 PASS。

---

# 15. 必须新增 Real Provider Verification

每一个 Tier 1 Provider 至少维护：

```text
discovery test
metadata test
access inspection test
download test（如合法可匿名获取）
```

需要登录的平台：

```text
auth flow = MANUAL_VERIFIED / AUTOMATED_VERIFIED / BLOCKED
```

不能使用虚假账号或伪造返回。

---

# 16. CI/CD

必须建立 GitHub Actions：

至少：

```text
lint
unit
integration
security scan
frontend smoke
```

Real Network E2E 可以：

- scheduled；
- manual dispatch；
- secret-enabled；

不要每次 PR 全跑。

---

# 17. 可观测性

至少记录：

```text
task id
run id
provider id
browser session id
download job id
build id
state
duration
error code
retry
bytes
rows
```

用户可理解错误。

日志必须结构化且脱敏。

---

# 18. 前端产品要求

当前三栏基础可以保留。

必须完成以下用户流程：

## 流程 A：找数据

```text
输入需求
→ Agent 解析
→ 用户确认
→ 搜索
→ 候选
→ 查看详情
→ 选择
→ 下载
```

## 流程 B：需要登录

```text
选择数据
→ 提示需要登录
→ 使用已有账号 / 注册
→ Live Browser
→ 必要时用户接管
→ 下载
```

## 流程 C：合成数据

```text
选择多个 Data Asset
→ Generate Build Plan
→ 查看变量映射
→ 查看 join
→ 查看聚合
→ Execute
→ QA
→ Package
```

## 流程 D：恢复任务

刷新/重启后：

```text
Search / Access / Download / Build
```

状态必须可恢复。

---

# 19. 禁止出现的伪完成模式

以下任何情况均不得标 PASS：

1. 只有 Registry，没有 Adapter，却称平台已集成。
2. Fixture 登录成功，却称真实平台登录已验证。
3. 保存字符串占位 session，却称持久化登录已实现。
4. Browser 后台运行，前端低频截图，却称 Live Browser 已完成。
5. `fill()` 瞬间输入，却称模拟人类键盘操作已完成。
6. HTML button 存在，却 API 不可用。
7. Build 使用前两个 artifact，却称用户选择已生效。
8. Semantic Alignment 只写日志，没有真正比较。
9. 所有年化统一 mean，却称语义时间对齐已完成。
10. Adapter 把大文件完整读入内存，却称大文件下载已工程化。
11. 单元测试 PASS，却没有产品 E2E。
12. 没有真实第三方证据，却称 Provider E2E VERIFIED。
13. 文档中写 PASS，却没有当前 commit 的 CI/命令证据。

---

# 20. 执行节奏

严格按 `Metis_Data_Productization_Task_List.md` Phase 顺序执行。

每一个任务：

1. 阅读要求；
2. 定位相关代码；
3. 修改；
4. 写/更新测试；
5. 运行测试；
6. 保存结果；
7. 更新进度；
8. 才进入下一任务。

---

# 21. 实施进度文件

持续维护：

```text
ENGINEERING_PROGRESS.md
```

格式：

```markdown
# Current Phase

# Current Task

# Completed

# Files Changed

# Tests Executed

# Evidence

# Blockers

# Next Task
```

禁止只写“完成”。

必须写：

```text
command
result
artifact
```

---

# 22. 工程验收原则

最终必须同时满足：

```text
功能正确
+
用户链路闭环
+
真实平台工作
+
异常可恢复
+
数据可审计
+
安全
+
可复现
+
可持续扩展
```

任何 P0 条件失败：

最终结论必须是：

```text
FAIL
```

不得写：

```text
基本完成
总体通过
大体可用
```

---

# 23. 最终 Golden Scenarios

至少真实完成下列场景。

## GS-1 国际宏观面板

用户：

> 构建 2015—2024 年国家层面的青年失业率、人均 GDP 和高等教育指标面板。

要求：

- 至少两个真实国际组织来源；
- 搜索；
- 下载；
- 语义；
- join；
- quality；
- provenance；
- reproduce。

## GS-2 中国区域数据

用户：

> 构建中国省级 GDP、人口、教育和财政指标面板。

要求：

- 至少使用一个中国官方数据源；
- 处理中文地区名称；
- 年份；
- 数据下载；
- 合成。

## GS-3 科研仓库数据

用户：

> 查找论文公开的大学生生成式 AI 使用调查原始数据并下载。

要求：

- 搜索至少 Harvard Dataverse / Zenodo / Figshare / OSF 中两个；
- 候选解释；
- DOI；
- license；
- download。

## GS-4 登录平台

选择一个合法允许测试的需要账号的平台。

要求：

- 账号绑定；
- 登录；
- storage_state 保存；
- 重启；
- 恢复；
- 下载。

如果 CAPTCHA/MFA 出现：

- WAITING_USER；
- user takeover；
- return；
- continue。

## GS-5 多源合成

至少 3 个数据集：

```text
不同 source
+
变量 mapping
+
time
+
entity
+
join
```

最终产生 package。

---

# 24. 最终验收报告

生成：

```text
Metis_Data_Engineering_Delivery_Acceptance.md
```

每项必须：

```text
PASS / FAIL / BLOCKED
Evidence
Command
Artifact
Commit
Notes
```

不得只引用旧验收报告。

---

# 25. 现在开始执行

现在立即：

1. 拉取或打开 `TZUKWAN/metis-data`；
2. 阅读：
   - README
   - PRD
   - Build Task List
   - Acceptance Report
   - IMPLEMENTATION_PROGRESS
   - 全部核心代码；
3. 不信任旧 PASS；
4. 按新的 `Metis_Data_Productization_Task_List.md` 开始 Phase 0；
5. 不要停留在分析；
6. 直接修改代码、测试、运行；
7. 每完成一项就验收；
8. 一直推进到工程交付标准。

