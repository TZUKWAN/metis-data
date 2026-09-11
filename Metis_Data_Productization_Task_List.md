# Metis Data 工程交付产品化任务清单

> 适用仓库：`TZUKWAN/metis-data`
>
> 本清单针对当前已有代码继续推进，不从零重建。
>
> 每个任务必须有：目标、实施动作、产物、验收标准、失败条件。
>
> 所有任务编号稳定，工程 Agent 应在 `ENGINEERING_PROGRESS.md` 中引用编号。

---

# Phase 0：Reality Audit 与基线重建

## P00-001 记录当前 commit 基线

**目标**

确保后续所有结果可追溯。

**实施动作**

1. 获取当前 branch。
2. 获取当前 HEAD SHA。
3. 获取工作区状态。
4. 记录 Python / Node / OS / Playwright 版本。
5. 写入 `metis/artifacts/productization/baseline.json`。

**产物**

`baseline.json`

**验收标准**

JSON 至少包含：

```text
branch
commit
dirty
os
python
node
playwright
timestamp
```

**失败条件**

无法明确对应当前代码版本。

---

## P00-002 重新运行现有测试

**目标**

不依赖旧验收报告。

**实施动作**

运行全部现有 pytest。

记录：

- pass；
- fail；
- skip；
- duration。

**产物**

`baseline_tests.txt`

**验收标准**

真实命令输出保存。

**失败条件**

只复制旧报告结果。

---

## P00-003 建立能力真实性矩阵

**目标**

区分 Registry、代码存在、fixture 验证、真实网络验证、产品 UI 可用。

**实施动作**

为每个核心能力建立字段：

```text
implemented
unit_tested
fixture_e2e
real_e2e
ui_connected
production_ready
```

**产物**

`capability_reality_matrix.json`

**验收标准**

至少覆盖：

- Requirement
- Search
- Provider
- Browser
- Auth
- Registration
- Session
- Download
- Parser
- Build
- Provenance
- UI

**失败条件**

继续使用单一 PASS/FAIL 隐藏成熟度差异。

---

## P00-004 修复明显 API/UI schema 错误

**目标**

先修当前 UI 无法正常创建 Browser Session 等阻断问题。

**实施动作**

检查 FastAPI request schemas 与前端调用。

重点核对：

```text
POST /api/browser/sessions
BrowserActionIn.session_id
```

为 create session 使用独立 request schema。

**验收标准**

真实前端点击“新会话”返回 200，并创建 Browser Session。

**失败条件**

依赖手工修改请求才能工作。

---

# Phase 1：LLM Data Agent Core

## P01-001 建立 agent 模块目录

创建：

```text
app/agent/
```

以及：

```text
__init__.py
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

**验收**

模块可 import。

---

## P01-002 OpenAI-compatible Model Client

**目标**

支持任意 OpenAI-compatible 推理服务。

**配置**

环境变量：

```text
METIS_LLM_BASE_URL
METIS_LLM_API_KEY
METIS_LLM_MODEL
METIS_LLM_REASONING_EFFORT
METIS_LLM_TIMEOUT
```

**验收**

- 没配置时明确报错；
- 配置后可以完成结构化请求；
- API key 不写日志。

---

## P01-003 LLM 重试与超时

实现：

- timeout；
- bounded retry；
- exponential backoff；
- error classification。

**验收**

429 / timeout / 5xx 测试通过。

---

## P01-004 Agent Schema

建立严格 Pydantic：

- DataRequirementPlan
- VariableConcept
- MeasurementCandidate
- SourcePlan
- SearchQueryPlan
- CandidateAnalysis
- BuildPlan
- ReviewPoint

**验收**

非法输出不能进入下游。

---

## P01-005 Requirement Planner

输入：

自然语言。

输出：

完整结构化研究数据需求。

**验收样例**

以下需求不在现有手写 lexicon：

> 中国城市科技创新、土地财政依赖、环境规制和产业升级

必须正确识别至少 4 个概念。

---

## P01-006 保留规则 Parser 为 fallback

当前 deterministic parser 不删除。

改为：

```text
LLM primary
rule fallback
rule validator
```

**验收**

模型不可用时基础需求仍可处理。

---

## P01-007 Measurement Planner

对抽象概念产生指标方案。

例如：

```text
digital economy
innovation
aging
environmental regulation
fiscal pressure
```

**验收**

每个概念输出：

- preferred measure；
- alternatives；
- proxies；
- unit；
- aggregation semantics；
- confidence。

---

## P01-008 Source Planner

根据指标和地域选择 Provider 类型。

**验收**

中国省级财政问题不能优先推荐 Kaggle。

---

## P01-009 Search Query Planner

生成：

- 中文；
- 英文；
- Provider-specific query；
- indicator code hints。

**验收**

每个 Provider query 不再局限于当前硬编码词典。

---

## P01-010 Planner Critic

新增 second-pass critic。

检查：

- 概念遗漏；
- 指标逻辑；
- geography；
- unit；
- time；
- source。

**验收**

明显矛盾需求能指出冲突。

---

## P01-011 Agent API

新增：

```text
POST /api/agent/requirements/plan
POST /api/agent/measurements/plan
POST /api/agent/sources/plan
```

**验收**

前端可调用。

---

## P01-012 前端 Requirement Review

显示：

- 研究对象；
- 时间；
- 地理；
- 变量；
- 测量；
- assumptions；
- unclear items。

用户可编辑。

**验收**

修改后 Search Plan 重算。

---

# Phase 2：Browser Productization

## P02-001 Browser Session API 拆分

分别建立：

```text
BrowserCreateSessionRequest
BrowserActionRequest
```

**验收**

create 不要求 session_id。

---

## P02-002 Live Stream 协议

实现 Browser frame stream。

推荐：

```text
WebSocket
```

帧率目标：

- 正常 15 FPS；
- 页面变化可提升；
- 后台可降频。

**验收**

连续观看浏览器无 2.5 秒跳帧感。

---

## P02-003 Browser Stream Backpressure

**目标**

慢客户端不导致内存膨胀。

**验收**

断网/慢消费测试无无限 queue。

---

## P02-004 Visible Cursor

前端 overlay 显示 cursor。

**验收**

Agent mouse move 时 UI 中可见轨迹。

---

## P02-005 Human-like mouse move

增加：

```text
move cursor
→ small interpolation
→ click
```

**验收**

DOM click 默认不直接瞬移。

---

## P02-006 Click feedback

显示点击 ring / highlight。

**验收**

用户能看到具体点击元素。

---

## P02-007 Keyboard typing

默认文本输入：

```python
locator.focus()
page.keyboard.type(text, delay=...)
```

敏感密码可允许更快输入，但 UI 不显示明文。

**验收**

普通查询在 Live Browser 中逐字可见。

---

## P02-008 Fill 仅作为特殊 fallback

**验收**

普通搜索框不默认 fill。

---

## P02-009 Browser Task Binding

Browser Session 增加：

```text
task_id
access_job_id
download_job_id
provider_id
```

**验收**

可追溯当前 Browser 在为哪个任务工作。

---

## P02-010 Tab Model

API 返回：

```text
tab id
title
url
active
```

**验收**

前端可以切换真实 tab。

---

## P02-011 Takeover

用户点击：

```text
我来操作
```

后：

- Agent dispatcher 锁定；
- 同一 Browser Context；
- 同一页面；
- 用户实际可操作。

**验收**

Agent 无输入事件。

---

## P02-012 Return

用户交还后：

- 重新读 URL；
- title；
- DOM；
- accessibility；
- active tab；
- auth state；
- intervention。

**验收**

不使用旧元素引用。

---

## P02-013 Browser Crash Recovery

模拟 Chromium kill。

**验收**

Session 标记 CRASHED，不假装 IDLE。

---

## P02-014 Browser Security

URL / event / screenshot metadata 不泄露：

- password；
- token；
- cookie；
- OTP。

---

# Phase 3：真实 Session / Vault

## P03-001 SecretStore 抽象

接口：

```python
SecretStore
set
get
delete
exists
list_keys
```

---

## P03-002 Windows DPAPI Adapter

保留现有实现。

---

## P03-003 跨平台 fallback 设计

至少确保：

- 非 Windows 不在 import 阶段崩溃；
- 明确报 `VAULT_UNAVAILABLE`。

---

## P03-004 Browser Storage State Schema

建立：

```text
provider_id
account_id
created_at
last_verified_at
expires_hint
vault_key
```

---

## P03-005 保存 storage_state

登录成功后：

```python
await context.storage_state()
```

序列化并加密。

**验收**

Vault 中保存真实 state。

---

## P03-006 恢复 storage_state

创建 Context 时载入。

**验收**

本地 fixture：

登录 → 保存 → 关闭浏览器 → 新 Context → 仍登录。

---

## P03-007 真实 session 有效性探测

Provider recipe 定义：

```text
logged_in_selector
logged_out_selector
account_url
```

**验收**

不只相信 DB status。

---

## P03-008 过期 session

检测失效。

状态：

```text
SESSION_EXPIRED
```

---

## P03-009 OAuth Credential Model

支持：

- access_token；
- refresh_token；
- expiry；
- scope。

---

## P03-010 Session 删除

删除账号：

- credentials；
- browser state；
- oauth state；
- active sessions。

**验收**

下一次需要重新认证。

---

# Phase 4：Access State Machine

## P04-001 新建 AccessJob

字段：

```text
access_job_id
provider_id
candidate_id
download_job_id
state
reason
account_id
browser_session_id
created_at
updated_at
```

---

## P04-002 State Enum

实现完整 AccessState。

---

## P04-003 Transition Guard

非法 transition 抛错。

---

## P04-004 inspect_access

Provider Adapter 返回：

```text
public
login_required
registration_possible
agreement_required
restricted
paid
unknown
```

---

## P04-005 公共数据分支

无需认证直接授权 download。

---

## P04-006 Existing Session 分支

检查真实 session。

---

## P04-007 Existing Account 分支

触发 login。

---

## P04-008 Auto Registration 分支

只有用户明确开启才执行。

---

## P04-009 WAITING_USER

CAPTCHA/MFA/Agreement/Institution/Payment：

进入 WAITING_USER。

---

## P04-010 Resume

用户完成后从 AccessJob 当前状态继续。

---

## P04-011 Access Failure

明确：

```text
INVALID_CREDENTIALS
PROVIDER_BLOCKED
REGISTRATION_FAILED
SESSION_EXPIRED
AGREEMENT_REQUIRED
```

---

## P04-012 下载主链路接入

`POST /api/downloads` 不再直接 adapter.acquire。

改为：

```text
Download Request
→ AccessJob
→ Authorized
→ Acquisition
```

---

# Phase 5：Account Center 与 Auto Registration

## P05-001 Account Center UI

展示所有 Provider：

- account；
- status；
- session；
- auto register；
- last verified。

---

## P05-002 Bind Existing Account

输入：

- account label/email；
- password/token。

敏感信息不回显。

---

## P05-003 Login API

新增：

```text
POST /api/accounts/{provider}/login
```

---

## P05-004 Login Provider Recipe

Provider-specific：

```text
login_url
email locator
password locator
submit locator
success detection
failure detection
```

---

## P05-005 Auto Registration API

新增：

```text
POST /api/accounts/{provider}/register
```

---

## P05-006 Provider Registration Recipe

字段映射。

---

## P05-007 Password Policy

每个平台支持：

```text
min length
upper
lower
digit
symbols
allowed symbols
```

---

## P05-008 Default Data Identity

用户配置：

- email；
- name；
- country；
- institution；
- role；
- ORCID；
- purpose。

---

## P05-009 Field Consent

用户可以禁用某字段自动提交。

---

## P05-010 Legal Agreement Handling

如果注册过程中存在重大条款：

必须 WAITING_USER。

---

## P05-011 Email Verification

状态：

```text
VERIFY_EMAIL_REQUIRED
```

不标 Fully Active。

---

## P05-012 Registration Retry Guard

同一 provider/account 不无限注册。

---

# Phase 6：Provider Contract 重构

## P06-001 AcquisitionDescriptor

字段：

```text
url
method
headers
filename
expected_type
expected_size
auth_context
license
metadata
```

---

## P06-002 ProviderAdapter v2

接口：

```text
discover
get_metadata
inspect_access
build_acquisition_descriptor
validate_download
```

---

## P06-003 兼容层

旧 adapter 可逐步迁移。

---

## P06-004 禁止 Adapter 直接写 Raw

静态扫描。

---

## P06-005 禁止大文件 response.content

发现：

```python
response.content
write_bytes
```

在下载路径中应整改。

---

# Phase 7：DownloadManager 工程化

## P07-001 Streaming HTTP

使用 async streaming。

---

## P07-002 Chunk Size

可配置。

---

## P07-003 Progress

记录：

```text
bytes received
total
percent
speed
eta
```

---

## P07-004 .partial

下载中只存在 staging partial。

---

## P07-005 Atomic Commit

验证成功才进入 Raw。

---

## P07-006 SHA256

流式计算。

---

## P07-007 Content Sniff

防 HTML 登录页伪装。

---

## P07-008 Content-Length Validation

如存在 expected size 则比对。

---

## P07-009 Resume Support

支持 Range 的 Provider 可断点续传。

---

## P07-010 Cancellation

取消立刻停止 network stream。

---

## P07-011 Browser Download

Browser event 也必须进入统一 verify/commit。

---

## P07-012 Multi-file Dataset

同一 Dataset 支持多个资源。

---

## P07-013 Archive Extraction

保留 zip-slip / bomb 防护。

---

## P07-014 大文件测试

至少 1GB synthetic stream 测试。

验收：

RSS 不随文件大小线性增长。

---

# Phase 8：Provider Integration Matrix

## P08-001 Integration Level Schema

等级：

P0–P7。

---

## P08-002 Provider Verification Record

字段：

```text
provider_id
capability
level
verified_at
method
test
result
blocker
```

---

## P08-003 Provider Matrix UI

展示真实等级。

---

## P08-004 禁止 Registry == Integrated

UI 文字必须明确。

---

# Phase 9：Tier 1 国际组织接入

每个平台都拆成 5 个任务：

```text
DISCOVERY
METADATA
ACCESS
DOWNLOAD
REAL E2E
```

以下每项均要求真实网络证据。

## P09-001～005 World Bank

验收：

- search；
- indicator metadata；
- access；
- CSV/API download；
- E2E。

## P09-006～010 IMF

## P09-011～015 OECD

## P09-016～020 Eurostat

## P09-021～025 WHO GHO

## P09-026～030 FAOSTAT

## P09-031～035 UN/SDG

## P09-036～040 UN Comtrade

## P09-041～045 ILOSTAT

## P09-046～050 UNESCO UIS

每个平台单项验收必须保存：

```text
metis/artifacts/providers/<provider>/verification.json
```

---

# Phase 10：美国官方 Provider

同样每个平台：

DISCOVERY / METADATA / ACCESS / DOWNLOAD / E2E。

## P10-001～005 Data.gov
## P10-006～010 Census
## P10-011～015 BLS
## P10-016～020 BEA
## P10-021～025 FRED
## P10-026～030 CDC
## P10-031～035 NOAA
## P10-036～040 NASA Earthdata
## P10-041～045 USGS
## P10-046～050 SEC EDGAR
## P10-051～055 FEC
## P10-056～060 NCES

无法下载的 catalog 型平台：

E2E 可以是：

```text
discover → resolve target → downstream download
```

---

# Phase 11：欧洲 Provider

## P11-001～005 data.europa.eu
## P11-006～010 ECB
## P11-011～015 Copernicus
## P11-016～020 data.gov.uk
## P11-021～025 ONS
## P11-026～030 UK Data Service
## P11-031～035 data.gouv.fr
## P11-036～040 INSEE
## P11-041～045 GovData
## P11-046～050 Destatis
## P11-051～055 datos.gob.es
## P11-056～060 dati.gov.it
## P11-061～065 data.overheid.nl
## P11-066～070 opendata.swiss

---

# Phase 12：科研数据仓库

## P12-001～005 Zenodo
## P12-006～010 Harvard Dataverse
## P12-011～015 Figshare
## P12-016～020 Dryad
## P12-021～025 OSF
## P12-026～030 ICPSR/openICPSR
## P12-031～035 GESIS
## P12-036～040 Mendeley Data
## P12-041～045 ScienceDB

---

# Phase 13：AI / 通用数据平台

## P13-001～005 Kaggle
## P13-006～010 Hugging Face
## P13-011～015 OpenML
## P13-016～020 UCI
## P13-021～025 Data.world
## P13-026～030 Google Dataset Search
## P13-031～035 AWS Open Data
## P13-036～040 Google Cloud Public Data
## P13-041～045 Wikidata
## P13-046～050 Wikimedia Dumps
## P13-051～055 Common Crawl

---

# Phase 14：中国 Provider

中国平台优先支持 Browser Search Recipe。

## P14-001～005 国家统计局 国家数据

必须支持：

- 浏览；
- 搜索/指标定位；
- 数据获取；
- 中文省市实体；
- E2E。

## P14-006～010 国家数据集管理服务平台
## P14-011～015 国家公共数据资源登记平台
## P14-016～020 北京公共数据开放平台
## P14-021～025 上海公共数据开放平台
## P14-026～030 深圳政府数据开放平台
## P14-031～035 武汉公共数据平台
## P14-036～040 国家基础学科公共科学数据中心
## P14-041～045 国家地球系统科学数据中心
## P14-046～050 国家青藏高原科学数据中心
## P14-051～055 中科院科学数据
## P14-056～060 ScienceDB
## P14-061～065 天池
## P14-066～070 和鲸
## P14-071～075 OpenDataLab
## P14-076～080 ModelScope
## P14-081～085 百度 AI Studio
## P14-086～090 DataFountain

---

# Phase 15：Browser Search Worker

## P15-001 Browser Search Contract

定义：

```text
search(query)
extract_results()
next_page()
open_result()
extract_metadata()
```

---

## P15-002 Recipe Schema

每 Provider：

```text
home_url
search_url
search_box
submit
result_cards
title
url
description
next
```

---

## P15-003 Dynamic Page Support

支持：

- infinite scroll；
- load more；
- pagination。

---

## P15-004 Login-Aware Search

搜索中发现 login：

进入 Access State Machine。

---

## P15-005 Candidate Normalization

Browser 结果转换 DatasetCandidate。

---

## P15-006 Browser Search Evidence

保存：

- events；
- result count；
- source URLs。

---

# Phase 16：Dataset Understanding

## P16-001 Profile 扩展

增加：

- quantiles；
- cardinality；
- pattern；
- language；
- categorical candidates。

---

## P16-002 Schema Semantics

LLM + deterministic。

---

## P16-003 Variable Dictionary

字段：

```text
name
label
definition
unit
population
frequency
source
codes
```

---

## P16-004 Unit Normalization

单位字典。

---

## P16-005 Currency / Price Basis

识别：

- current price；
- constant price；
- currency；
- PPP；
- base year。

---

## P16-006 Rate Semantics

区分：

- percent；
- fraction；
- per 1000；
- per 100000。

---

## P16-007 Categorical Mapping

生成显式 map。

---

## P16-008 Semantic Conflict

不兼容字段禁止自动 merge。

---

# Phase 17：Build Planner

## P17-001 Build Planner Agent

输入：

- requirement；
- selected assets；
- profile；
- semantics。

---

## P17-002 Target Schema

显式输出最终字段。

---

## P17-003 Input Role

每个 dataset 指明用途。

---

## P17-004 Field Mapping

source field → target field。

---

## P17-005 Key Recommendation

不硬编码 country/year。

---

## P17-006 Entity Strategy

country / province / city / firm / person 等。

---

## P17-007 Time Strategy

frequency / fiscal / period。

---

## P17-008 Aggregation Plan

每个变量单独 aggregation method。

---

## P17-009 Join Plan

明确：

```text
left
right
keys
expected cardinality
join type
coverage requirement
```

---

## P17-010 Missing Plan

变量级。

---

## P17-011 Derived Variables

公式明确。

---

## P17-012 Validation Plan

根据领域生成。

---

## P17-013 Review Points

高风险项标记 NEEDS_REVIEW。

---

# Phase 18：Build UI

## P18-001 Data Asset Selection

真正使用用户选择。

删除任何：

```javascript
STATE.artifacts.slice(0,2)
```

逻辑。

---

## P18-002 Build Plan Editor

用户可修改：

- input；
- key；
- field map；
- aggregate；
- join；
- missing。

---

## P18-003 Semantic Warning

显示冲突。

---

## P18-004 Join Preview

执行前显示：

- cardinality；
- expected rows；
- matched；
- unmatched。

---

## P18-005 Approval

高风险 plan 需要用户确认。

---

# Phase 19：Aggregation Semantics

## P19-001 Aggregation Enum

支持：

```text
mean
sum
last
first
median
weighted_mean
min
max
none
```

---

## P19-002 Variable-driven Aggregation

Build Planner 推荐。

---

## P19-003 Weighted Mean

支持权重字段。

---

## P19-004 Stock/Flow Guard

明显 stock/flow 错配 warning。

---

## P19-005 Unknown Aggregation

不能默认 mean。

进入 review。

---

# Phase 20：Join 工程化

## P20-001 Cardinality Check
## P20-002 Duplicate Key Report
## P20-003 Coverage
## P20-004 Unmatched
## P20-005 Explosion Estimate
## P20-006 M:M default block
## P20-007 Explicit override
## P20-008 Join lineage
## P20-009 Null key policy
## P20-010 Multi-stage join plan

---

# Phase 21：Validation

## P21-001 Schema Drift
## P21-002 Type Drift
## P21-003 Missing
## P21-004 Duplicate
## P21-005 Key
## P21-006 Temporal Gap
## P21-007 Geo Coverage
## P21-008 Impossible Values
## P21-009 Outlier
## P21-010 Constant Column
## P21-011 Join Coverage
## P21-012 Row Explosion
## P21-013 Unit Conflict
## P21-014 Semantic Conflict
## P21-015 Source License

每项输出：

```text
code
severity
field
count
message
remediation
```

---

# Phase 22：Provenance / Reproducibility

## P22-001 Source Provenance
## P22-002 Raw Checksum
## P22-003 Acquisition Context
## P22-004 Field Lineage
## P22-005 Transform Operation
## P22-006 Code Version
## P22-007 Build Plan Snapshot
## P22-008 Agent Decision Snapshot
## P22-009 Methodology
## P22-010 Reproduce
## P22-011 Dependency Lock
## P22-012 Raw Manifest

---

# Phase 23：任务恢复

## P23-001 Search Recovery
## P23-002 Access Recovery
## P23-003 Browser Crash State
## P23-004 Download Recovery
## P23-005 Build Recovery
## P23-006 Idempotency
## P23-007 Registration In-flight Recovery
## P23-008 Login In-flight Recovery

---

# Phase 24：前端产品化

## P24-001 Project/Task Model

支持多个数据任务。

---

## P24-002 Requirement Panel
## P24-003 Search Panel
## P24-004 Candidate Detail
## P24-005 Provider Matrix
## P24-006 Account Center
## P24-007 Live Browser
## P24-008 Downloads
## P24-009 Assets
## P24-010 Data Preview
## P24-011 Build Planner
## P24-012 Build Runtime
## P24-013 QA
## P24-014 Provenance Viewer
## P24-015 Package Download
## P24-016 Agent Conversation
## P24-017 Event Timeline
## P24-018 Error Recovery UI
## P24-019 Empty State
## P24-020 Loading State

---

# Phase 25：Agent Chat Orchestration

## P25-001 Conversation State

Agent chat 绑定 task。

---

## P25-002 Tool Calls

Agent 可以调用：

- plan requirement；
- search；
- inspect；
- access；
- download；
- profile；
- build；
- validate。

---

## P25-003 Confirmation Policy

只有高风险操作需要确认。

---

## P25-004 Explain Current State

用户问：

> 现在进行到哪了？

Agent 能基于 task state 回答。

---

## P25-005 Explain Recommendation

能解释为什么推荐某数据集。

---

## P25-006 Explain Build

能解释 join / aggregation / missing。

---

# Phase 26：安全

## P26-001 Secret Scan
## P26-002 Log Redaction
## P26-003 Browser Secret Redaction
## P26-004 API Error Redaction
## P26-005 Path Traversal
## P26-006 Zip Slip
## P26-007 Archive Bomb
## P26-008 URL Validation
## P26-009 SSRF Guard
## P26-010 File Type Sniff
## P26-011 Raw Immutable
## P26-012 Account Deletion
## P26-013 No CAPTCHA Bypass
## P26-014 No Stealth
## P26-015 License Warning

---

# Phase 27：性能

## P27-001 1GB Download
## P27-002 5M Row Profile
## P27-003 Large CSV Preview
## P27-004 Parquet
## P27-005 Multi-provider Search
## P27-006 Browser Stream
## P27-007 Large Join
## P27-008 Memory Bound
## P27-009 Cancellation Latency

---

# Phase 28：CI

## P28-001 GitHub Actions lint
## P28-002 Unit
## P28-003 Integration
## P28-004 Security
## P28-005 Frontend smoke
## P28-006 Artifact Upload
## P28-007 Scheduled Real Provider Smoke
## P28-008 Manual E2E workflow

---

# Phase 29：真实 Golden Scenarios

## P29-001 GS-1 国际宏观面板

真实执行。

**验收**

至少两来源。

---

## P29-002 GS-2 中国官方面板

真实执行。

---

## P29-003 GS-3 科研数据仓库

真实执行。

---

## P29-004 GS-4 登录恢复

真实或受控真实测试账号。

要求：

```text
login
→ persist
→ restart
→ restore
→ acquire
```

---

## P29-005 GS-5 三数据源 Build

至少 3 输入。

---

## P29-006 Golden Reproduce

删除 final 后执行 reproduce。

结果一致。

---

# Phase 30：工程交付验收

## P30-001 安装说明

新环境可按 README 启动。

---

## P30-002 `.env.example`

完整。

---

## P30-003 Migration

DB schema 升级可控。

---

## P30-004 Provider Docs

每 Provider：

- capabilities；
- auth；
- blockers。

---

## P30-005 Architecture

更新真实架构图。

---

## P30-006 Acceptance Report

输出：

`Metis_Data_Engineering_Delivery_Acceptance.md`

---

# 总体验收门槛

以下均为 P0。

只要一个失败，不能判工程交付 PASS。

## GATE-01 自然语言智能

非词典需求能正确规划。

## GATE-02 搜索

至少 20 个 Tier 1 Provider 达到真实 Discovery。

## GATE-03 Provider

Registry 不冒充 Integration。

## GATE-04 Browser

Metis UI 内可实时看到 Browser 操作。

## GATE-05 Mouse/Keyboard

鼠标与键盘动作可视。

## GATE-06 Takeover

同 Session 接管/交还。

## GATE-07 Auth

已有账号可真实登录。

## GATE-08 Session

storage state 可持久化和恢复。

## GATE-09 Registration

至少一个允许测试的平台或受控 fixture + 一个真实流程完成产品链。

## GATE-10 Access

Access State Machine 与下载闭环。

## GATE-11 Download

大文件 streaming。

## GATE-12 Raw

不可变。

## GATE-13 Build

真正使用用户选择的数据。

## GATE-14 Semantics

变量语义冲突会阻止错误合并。

## GATE-15 Aggregation

不再统一 mean。

## GATE-16 Join

m:m 默认阻止。

## GATE-17 Validation

有结构化 QA。

## GATE-18 Provenance

字段级 lineage。

## GATE-19 Reproduce

重建结果一致。

## GATE-20 Recovery

重启后任务状态真实。

## GATE-21 Security

无 Secret 泄露、无 CAPTCHA 绕过。

## GATE-22 CI

当前 commit CI 绿。

## GATE-23 Real E2E

至少 5 个 Golden Scenario 通过。

---

# 每个任务的统一完成格式

Agent 在 `ENGINEERING_PROGRESS.md` 中必须这样记录：

```markdown
## Task Pxx-xxx

Status: PASS

Goal:
...

Files Changed:
- ...

Implementation:
...

Tests:
- `command`
  - result

Evidence:
- artifact path
- screenshot
- report

Acceptance:
- [x] criterion 1
- [x] criterion 2

Remaining:
- none
```

如未完成：

```text
FAIL
```

或：

```text
BLOCKED
```

并说明具体原因。

---

# 最终 Definition of Done

Metis Data 只有在以下状态下才算工程交付可用：

```text
用户提出真实数据需求
↓
系统正确理解
↓
自动规划测量
↓
自动搜索多个真实平台
↓
用户选择或 Agent 推荐
↓
系统判断访问条件
↓
必要时自动登录/注册
↓
需要人工验证时安全接管
↓
完成真实下载
↓
解析真实数据
↓
生成数据语义
↓
生成 Build Plan
↓
进行可解释的数据合成
↓
自动 QA
↓
输出可复现数据包
↓
整个流程刷新/重启后仍可恢复
```

其中任何关键环节如果只能靠开发者手工进入后端、改数据库、复制 Cookie、运行隐藏脚本或修改源代码完成，就不算产品可用。
