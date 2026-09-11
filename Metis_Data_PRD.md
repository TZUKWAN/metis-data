# Metis Data 产品需求文档（PRD）

> 版本：v1.0  
> 日期：2026-09-11  
> 产品名称：Metis Data  
> 用途：产品定义、架构边界、研发统一依据、任务拆解与验收依据

---

## 0. 产品定义

Metis Data 是一个独立的数据智能体产品，面向科研、数据分析、政策研究、商业研究和 AI/机器学习场景，负责把“自然语言数据需求”转化为“可验证、可追溯、可复现的数据资产”。

核心链路：

```text
用户自然语言需求
→ 数据需求结构化
→ 全球数据源选择
→ 多平台并行搜索
→ 候选数据集归一化与推荐
→ 访问条件判断
→ 匿名/API/已有账号/自动注册/用户接管
→ 数据下载与原始文件归档
→ 数据解析与 Profile
→ 多源变量/实体/时间对齐
→ 数据清洗、合成、派生
→ 数据质量审计
→ Provenance / Lineage
→ Final Data Package
```

Metis Data 不是数据网站导航页，不是单纯 API 聚合器，也不是仅能“搜到数据”的聊天机器人。它必须完整完成发现、访问、获取、理解、合成和可复现交付。

---

# 1. 产品一级目标

Metis Data 必须具备五类一级能力。

## 1.1 Discovery Engine

负责：

- 理解用户研究问题；
- 提取数据单位、时间、地区、变量、样本、频率等需求；
- 选择合适的数据平台；
- 并行搜索多个 Provider；
- 统一不同平台返回结果；
- 去重、补充 metadata；
- 推荐最符合需求的数据集组合。

## 1.2 Browser & Access Engine

负责：

- 打开真实可见浏览器；
- 搜索网站；
- 登录；
- 普通自助注册；
- 表单填写；
- 页面浏览；
- 动态下载；
- 多标签页；
- 用户随时暂停；
- 用户接管；
- 用户完成 CAPTCHA/MFA/协议后交还 Agent。

## 1.3 Dataset Intelligence Engine

负责理解：

- 数据集主题；
- 变量；
- 样本；
- 研究单位；
- 时间范围；
- 空间范围；
- 数据类型；
- License；
- DOI；
- 论文关联；
- 数据质量；
- 是否适合用户提出的研究设计。

## 1.4 Acquisition & Synthesis Engine

负责：

- 下载；
- 校验；
- 解压；
- 格式识别；
- 编码识别；
- schema inference；
- 清洗；
- 变量语义对齐；
- 单位转换；
- 实体统一；
- 时空对齐；
- append；
- join；
- reshape；
- recode；
- 缺失处理；
- 派生变量；
- 最终数据集导出。

## 1.5 Provenance Engine

负责保存：

- 数据来源；
- Provider；
- URL；
- DOI；
- 版本；
- License；
- 下载时间；
- SHA256；
- Raw 文件；
- 每次数据转换；
- join key；
- 变量映射；
- 派生公式；
- 插补记录；
- 单位换算；
- 字段级 lineage；
- 可复现脚本。

---

# 2. 产品边界

## 2.1 必须实现

- 公开 API 数据获取；
- 公开网页数据搜索与下载；
- 登录账户数据访问；
- 普通自助注册；
- 可见 Browser Agent；
- 虚拟鼠标/键盘操作；
- DOM + Accessibility + Vision 多策略定位；
- Human-in-the-loop；
- 多源数据合成；
- 原始数据不可变；
- 数据质量审计；
- 完整 provenance；
- 可复现最终数据包。

## 2.2 明确禁止

不得实现：

- CAPTCHA 绕过；
- MFA 绕过；
- 浏览器指纹伪造；
- stealth anti-detection；
- 规避访问控制；
- 规避付费；
- 未授权抓取；
- 自动替用户接受具有额外法律责任的受限数据协议；
- 明文保存 password/token/session/API key；
- 为“填满数据”而生成伪造观测值；
- 未标记的插补；
- 未验证语义的字段直接合并；
- 未验证 cardinality 的 m:m join。

使用 headed Chromium 和真实鼠标/键盘事件，是为了提供真实网页交互、稳定操作和可观察性，不以规避网站风控为工程目标。

---

# 3. 用户画像

主要用户：

- 哲学社会科学研究者；
- 经济学、社会学、教育学、公共管理、人口学等研究者；
- 计算社会科学研究者；
- 博硕士研究生；
- 高校教师；
- 数据分析师；
- 政策研究人员；
- AI/ML 研究者；
- 需要构建分析/训练/评估数据集的团队。

---

# 4. 核心使用场景

## 4.1 单数据集搜索

用户：

> 找一个 2018—2025 年大学生生成式 AI 使用情况的数据集，最好包含 GPA、自我效能和学习投入。

系统：

1. 解析时间、研究对象、变量、粒度；
2. 搜索学术仓储和数据社区；
3. 比较变量覆盖；
4. 返回候选；
5. 显示来源、DOI、License、样本和不足；
6. 用户选择后下载；
7. 保存 Raw 与 provenance。

## 4.2 跨国面板构建

用户：

> 构建 2015—2025 年全球国家层面的 AI 发展、青年就业、教育水平、人均 GDP 和产业结构面板。

系统应：

- 搜索 World Bank、ILOSTAT、OECD、UNESCO、IMF 等；
- 自动判断指标；
- 统一 ISO3；
- 对齐年份；
- 核验单位与统计口径；
- 合并；
- 输出匹配率；
- 输出缺失情况；
- 输出最终 panel；
- 输出方法说明和 lineage。

## 4.3 需要网页登录

访问需要账号的平台时：

```text
PUBLIC/API
→ EXISTING SESSION
→ EXISTING ACCOUNT
→ AUTO REGISTRATION
→ USER INTERVENTION
```

遇到 CAPTCHA、MFA、手机验证码、机构认证、付费、Restricted Data Agreement 时必须暂停，并将 Browser 控制权交给用户。

## 4.4 用户已有账号

账户中心支持：

- 选择 Provider；
- 登录已有账号；
- OAuth/API key（平台支持时）；
- 保存安全认证状态；
- 删除单个平台凭据；
- 清除 session；
- 查看最后验证时间。

---

# 5. 产品主界面

默认桌面三栏：

```text
┌────────────────────────────────────────────────────────────────┐
│                         Metis Data                             │
├──────────────┬────────────────────────────────┬────────────────┤
│ Task / Data  │ Live Browser / Data Preview    │ Data Agent     │
│              │                                │                │
│ Requirements │ 真实网页                        │ 当前动作          │
│ Sources      │ 鼠标/键盘                       │ 工具事件          │
│ Candidates   │ Dataset 表格                    │ 推荐理由          │
│ Downloads    │ Schema / Profile               │ 风险/阻塞         │
│ Builds       │                                │ 用户介入提示       │
│ Provenance   │                                │                │
└──────────────┴────────────────────────────────┴────────────────┘
```

右侧 Agent 面板不展示隐式 chain-of-thought，只显示：

- 正在执行什么；
- 为什么选择某数据集的简短依据；
- 工具事件；
- 错误；
- 风险；
- 用户需要完成的步骤。

---

# 6. 数据源范围

全部平台进入统一 Provider Registry。允许分阶段做到不同接入等级，但不得漏登记。

## 6.1 国际组织

- World Bank Open Data / Data360
- IMF Data
- OECD Data Explorer
- Eurostat
- WHO Global Health Observatory
- FAOSTAT
- UN 系列数据库
- UN Comtrade
- ILOSTAT
- UNESCO UIS

## 6.2 美国

- Data.gov
- US Census Bureau
- Bureau of Labor Statistics
- BEA
- FRED
- CDC Data
- NOAA
- NASA Earthdata
- USGS
- SEC EDGAR
- Federal Election Commission 数据门户
- NCES

## 6.3 欧洲

- data.europa.eu
- Eurostat
- ECB Data Portal
- Copernicus Data Space
- data.gov.uk / National Data Library
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

## 6.4 加拿大、澳大利亚、新西兰

- Canada Open Government Portal
- data.gov.au
- data.govt.nz

## 6.5 日本、韩国

- e-Stat
- data.go.jp
- data.go.kr

## 6.6 中国

- 国家数据集管理服务平台 NDSMS
- 国家统计局“国家数据”
- 国家公共数据资源登记平台
- 北京市公共数据开放平台
- 上海公共数据开放平台
- 深圳市政府数据开放平台
- 武汉等主要城市开放数据平台
- 国家基础学科公共科学数据中心
- 国家地球系统科学数据中心
- 国家青藏高原科学数据中心
- 中国科学院相关科学数据中心
- ScienceDB

## 6.7 全球科研数据仓储

- Zenodo
- Harvard Dataverse
- Mendeley Data
- Figshare
- Dryad
- OSF
- ICPSR
- openICPSR
- GESIS
- Dataverse 网络
- Academic Torrents

## 6.8 AI / 数据科学 / 通用

- Kaggle Datasets
- Hugging Face Datasets
- OpenML
- UCI Machine Learning Repository
- Papers with Code
- Data.world
- AWS Registry of Open Data
- Google Dataset Search
- Google Cloud Public Datasets / BigQuery
- Azure Open Datasets
- Common Crawl
- Wikimedia Dumps
- Wikidata
- 阿里云天池
- 和鲸 HeyWhale/Kesci
- OpenDataLab
- ModelScope
- 百度 AI Studio
- DataFountain

---

# 7. Provider Registry

每个平台必须有统一声明。

```yaml
provider_id:
name:
category:
country_or_region:
homepage:
trust_class:
status:

capabilities:
  discovery_api:
  discovery_http:
  discovery_browser:
  metadata_api:
  preview:
  anonymous_download:
  authenticated_download:
  registration:
  oauth:
  api_key:
  restricted_data:

auth_modes:
formats:
licenses:
rate_limit_notes:
browser_required_for:
terms_url:
privacy_url:
adapter_version:
integration_level:
last_verified_at:
```

接入等级：

- P0：登记/导航；
- P1：可搜索；
- P2：可读取标准 metadata；
- P3：可预览；
- P4：可下载公开数据；
- P5：可用用户账户下载；
- P6：可普通自动注册；
- P7：完整 provider-specific 解析和版本处理。

UI 必须显示真实等级。

---

# 8. Provider Adapter 标准接口

上层 Agent 只调用统一接口：

```text
search_datasets(requirement, filters)
get_dataset_metadata(provider_id, dataset_ref)
preview_dataset(provider_id, dataset_ref)
get_access_requirements(provider_id, dataset_ref)
acquire_dataset(provider_id, dataset_ref, access_context)
refresh_auth(provider_id)
```

可选：

```text
login(provider_id)
register_account(provider_id)
request_api_key(provider_id)
```

禁止 UI 直接调用 provider 私有实现。

---

# 9. Data Requirement Schema

自然语言必须转结构化对象：

```yaml
goal:
research_question:
data_task_type:
unit_of_analysis:
population:
geography:
time_range:
frequency:

variables:
  outcomes:
  exposures:
  mediators:
  moderators:
  controls:
  identifiers:
  optional:

preferred_sources:
excluded_sources:
trust_requirement:
license_requirement:
access_tolerance:
format_preferences:
max_missing_rate:
notes:
```

Agent 可以合理推断默认值，但必须显式展示重要推断。

---

# 10. Search & Discovery

搜索渠道：

```text
官方 API
→ 官方结构化 endpoint/catalog
→ Provider Browser Search
→ 外部数据集索引补充
```

要求：

- 多 Provider 并发；
- provider-specific timeout；
- rate limit；
- exponential backoff；
- circuit breaker；
- cancellation；
- 单个平台失败不阻塞整体；
- 搜索历史可持久化。

去重依据：

- DOI；
- dataset ID；
- canonical URL；
- title + author + year；
- checksum；
- mirror 关系。

---

# 11. 候选推荐

不得只给一个总分。

每个候选至少展示：

- 主题匹配；
- 核心变量覆盖；
- 研究单位；
- 时间覆盖；
- 空间覆盖；
- 来源类别；
- DOI/论文关联；
- License；
- 可获取性；
- 文档完整性；
- 已知缺失；
- 推荐原因；
- 不足和未知。

未知不得按“满足”处理。

---

# 12. Browser & Computer Use

必须使用真实可见 Chromium/Chrome 浏览器实例。

支持：

```text
navigate
click
double_click
type
press_key
scroll
select
upload
download
new_tab
close_tab
switch_tab
back
forward
read_dom
read_accessibility
screenshot
```

元素定位顺序：

1. accessibility role + name；
2. semantic DOM；
3. text locator；
4. stable CSS/data attribute；
5. vision；
6. coordinate fallback。

固定坐标不得成为主要定位方式。

用户必须能看到页面、点击、输入和滚动。

---

# 13. Human-in-the-loop

提供：

- Pause；
- Take Over；
- Return to Agent；
- Stop。

接管后：

- Agent 停止所有输入；
- 用户继续操作同一 session；
- 交还后 Agent 重新读取当前 URL/DOM；
- 不允许继续使用旧页面固定坐标。

强制介入：

- CAPTCHA；
- MFA；
- 手机 OTP；
- 机构认证；
- 身份证件；
- 付费；
- restricted agreement；
- 需要用户承担额外义务的协议。

---

# 14. Data Identity 与 Credential Vault

用户可保存：

- 姓名；
- 默认邮箱；
- 国家/地区；
- 所属机构；
- 身份/职业；
- ORCID（可选）；
- 研究用途模板（可选）。

密码方案：

- 用户管理 Metis Data 主解锁；
- 每个平台自动生成不同密码；
- 默认至少 16 位；
- 大写；
- 小写；
- 数字；
- 特殊字符；
- 根据平台规则自适应；
- 不跨平台复用。

不得明文保存：

- password；
- API key；
- access token；
- refresh token；
- cookie；
- auth state。

桌面端优先调用 OS 安全存储。

---

# 15. 自动注册

允许自动完成普通自助注册：

- 打开注册页；
- 填写 Data Identity；
- 生成独立密码；
- 填写普通注册表；
- 提交；
- 判断注册结果。

出现以下状态则进入用户介入：

- CAPTCHA；
- 邮箱验证无法自动安全完成；
- 手机验证码；
- MFA；
- 机构认证；
- 受控数据申请；
- 额外协议；
- 付费。

注册日志仅记录 Provider、时间、邮箱标识、结果，不记录明文密码。

---

# 16. Download Job

任何下载前创建 manifest：

```yaml
download_job_id:
provider_id:
dataset_ref:
dataset_title:
source_url:
version:
access_mode:
license:
expected_files:
started_at:
completed_at:
status:
```

下载后：

- 文件存在性；
- MIME；
- 真实格式；
- 大小；
- SHA256；
- 压缩包完整性；
- 安全解压；
- metadata；
- manifest 更新。

必须防止把登录 HTML 当 CSV/ZIP 保存。

---

# 17. Raw Data

标准目录：

```text
workspace/
  raw/
    <provider>/
      <dataset-id>/
        <version>/
```

原则：

- raw immutable；
- 不原地清洗；
- 不原地改名覆盖；
- transform 输出 intermediate；
- final 单独输出；
- 相同 checksum 可内容去重，但逻辑引用保留。

---

# 18. 数据格式

v1 最低支持：

- CSV/TSV；
- XLS/XLSX；
- JSON/JSONL；
- XML；
- Parquet；
- Stata DTA；
- SPSS SAV；
- SAS；
- ZIP/TAR/GZ；
- GeoJSON；
- Shapefile；
- NetCDF；
- SQLite；
- HTML table。

后续扩展：

- RData/RDS；
- Arrow；
- GeoTIFF；
- HDF5；
- Remote SQL；
- Object Storage。

---

# 19. Dataset Profile

每个 acquired artifact 自动生成：

- title；
- description；
- publisher；
- authors；
- DOI；
- Provider；
- version；
- License；
- files；
- row count；
- column count；
- schema；
- data type；
- sample；
- missing rate；
- unique；
- min/max；
- duplicate；
- likely ID；
- likely key；
- likely time field；
- likely geography field；
- value labels；
- variable labels；
- codebook。

大文件应 stream/chunk，不得反复整体复制。

---

# 20. Variable Semantics

每个变量统一描述：

```yaml
canonical_name:
original_name:
display_name:
definition:
unit:
scale:
coding:
frequency:
geography_level:
population:
price_basis:
currency:
source_dataset:
source_field:
confidence:
```

合并前至少检查：

- 概念；
- 单位；
- 人群；
- 统计范围；
- 时间口径；
- 地理粒度；
- 名义/实际价格；
- 百分比/比例；
- 指数基期。

同名不等于同义。

---

# 21. Data Synthesis

必须支持：

- append；
- keyed join；
- 多年份合并；
- 多地区合并；
- 多国 panel；
- 个体数据 + 宏观数据；
- unit conversion；
- recode；
- reshape；
- aggregation；
- derived variables；
- missing policies；
- interpolation/imputation。

任何操作都必须产生日志和 provenance。

---

# 22. Entity Resolution

v1 至少支持：

- ISO2；
- ISO3；
- 国家名称；
- 常见国家别名；
- 中国省级行政区；
- 中国省级代码；
- 中国地级市基础字典；
- 地级行政区代码；
- 可扩展实体表。

模糊匹配必须记录 confidence。

低置信匹配不能静默进入 final。

历史行政区变化应保留时间版本信息。

---

# 23. 时间对齐

支持：

- 年；
- 季；
- 月；
- 日。

不同频率不能直接无提示 merge。

任何：

- annualization；
- aggregation；
- interpolation；
- carry forward；

都必须记录方法。

---

# 24. Join 安全

执行 join 前必须：

1. 定义 key；
2. 检查 key 类型；
3. 检查重复；
4. 识别 1:1 / 1:m / m:1 / m:m；
5. 预测输出行数；
6. 计算预计覆盖；
7. 执行。

m:m 默认阻止。

执行后输出：

- matched；
- unmatched left；
- unmatched right；
- coverage；
- row count before/after；
- 示例 unmatched entities。

---

# 25. 缺失与插补

默认：不自动插补。

支持：

- none；
- drop；
- forward fill；
- backward fill；
- linear interpolation；
- group interpolation；
- statistical/model imputation。

任何生成值必须：

- 有标记；
- 有方法；
- 有参数；
- 有来源；
- 在 quality report 中统计比例。

---

# 26. 数据质量

最低检查：

- key uniqueness；
- duplicate rows；
- missing；
- impossible values；
- outlier；
- unit anomaly；
- temporal gap；
- join coverage；
- unmatched entities；
- constant column；
- type drift；
- row count drift；
- encoding anomaly。

检查结果有 severity：

- INFO；
- WARNING；
- ERROR；
- BLOCKING。

---

# 27. Provenance

数据集级记录：

- Provider；
- source URL；
- DOI；
- dataset ID；
- version；
- License；
- download timestamp；
- checksum；
- access mode。

Transformation 记录：

```yaml
operation_id:
timestamp:
input_artifacts:
output_artifacts:
operation_type:
parameters:
code_version:
row_count_before:
row_count_after:
column_count_before:
column_count_after:
warnings:
```

字段级：

```text
final.youth_unemployment
→ unit/rename/join
→ source_field
→ raw file
→ provider dataset
→ URL/DOI
```

---

# 28. Final Data Package

```text
build_<id>/
├── final/
│   ├── dataset.parquet
│   ├── dataset.csv
│   └── dataset.xlsx
├── raw/
├── intermediate/
├── metadata/
│   ├── dataset.json
│   ├── variables.json
│   └── sources.json
├── provenance/
│   ├── lineage.json
│   ├── transformations.json
│   └── checksums.json
├── reports/
│   ├── quality_report.html
│   └── methodology.md
└── scripts/
    └── reproduce.py
```

如果 raw 因体量采用外部内容寻址存储，也必须输出 raw 引用 manifest。

---

# 29. Agent 状态机

Search：

```text
CREATED
→ REQUIREMENT_PARSED
→ PROVIDERS_SELECTED
→ SEARCHING
→ CANDIDATES_NORMALIZED
→ CANDIDATES_EVALUATED
→ WAITING_USER_SELECTION / AUTO_SELECTED
→ COMPLETED
```

Access：

```text
ACCESS_CHECK
→ PUBLIC_DOWNLOAD
or
→ AUTH_REQUIRED
  → SESSION_CHECK
  → LOGIN
  → REGISTER
  → USER_INTERVENTION
→ DOWNLOADING
→ VERIFYING
→ PROFILING
→ ACQUIRED
```

Build：

```text
BUILD_CREATED
→ INPUTS_READY
→ SCHEMA_ANALYSIS
→ SEMANTIC_ALIGNMENT
→ ENTITY_RESOLUTION
→ TEMPORAL_ALIGNMENT
→ TRANSFORM
→ JOIN
→ QA
→ PROVENANCE_FINALIZE
→ EXPORT
→ COMPLETE
```

状态必须持久化，可恢复。

---

# 30. Agent Tool 设计

建议工具：

```text
data.requirement.parse
provider.search
provider.metadata
provider.preview
provider.access.inspect

browser.open
browser.navigate
browser.read
browser.click
browser.type
browser.scroll
browser.download
browser.pause_for_user

auth.get_status
auth.login
auth.register
auth.logout

download.create_job
download.verify

dataset.profile
dataset.preview

schema.infer
schema.align
entity.resolve
time.align
data.transform
data.join
data.validate

provenance.record
build.export
```

不要给模型一个无约束万能接口后让它自行完成全部业务。

---

# 31. 安全和日志

日志自动脱敏：

- password；
- token；
- refresh token；
- API key；
- cookie；
- Authorization header；
- OTP。

所有错误需有：

- error code；
- message；
- retryable；
- task id；
- provider id；
- safe details。

---

# 32. 错误恢复

必须覆盖：

- 404/500；
- API schema 改版；
- selector 失效；
- session 过期；
- login 失败；
- 下载中断；
- checksum 异常；
- ZIP 损坏；
- parse 失败；
- encoding 失败；
- join explosion；
- key 不唯一；
- Browser crash；
- 网络中断；
- 用户取消；
- 应用重启。

关键错误不得静默跳过。

---

# 33. MVP 代表性 Provider

首版至少完整跑通 8 个代表性来源：

1. World Bank；
2. Eurostat；
3. ILOSTAT；
4. Data.gov；
5. Zenodo；
6. Harvard Dataverse；
7. Kaggle；
8. 国家统计局或 NDSMS。

其余平台全部进入 Provider Registry，后续按统一 Adapter 规范逐步提升等级。

---

# 34. 性能要求

- Provider registry 加载 < 500ms；
- 多 API Provider 支持并发；
- 单 Provider 失败不阻塞整体；
- 下载使用 streaming；
- 大 CSV profile 使用 chunk；
- Parquet 作为推荐内部列式格式；
- Build 支持 checkpoint；
- UI 主线程不能被下载/解析长任务阻塞。

---

# 35. 可观测性

至少记录：

- task_id；
- provider；
- action；
- duration；
- retry；
- status；
- browser step；
- bytes downloaded；
- profile duration；
- build stage；
- join coverage；
- validation warning。

需要开发诊断页，但不暴露 secrets。

---

# 36. 产品原则

1. 来源优先。
2. Raw 永远不可覆盖。
3. 语义先于 merge。
4. API 可稳定获取时优先 API。
5. 必要网页登录使用真实可见 Browser。
6. 自动化必须可观察。
7. 自动化必须可暂停、接管、恢复。
8. 不绕过访问控制。
9. 不确定时显式标记。
10. 插补和推导必须可追溯。
11. 最终交付是数据资产，不是聊天文字。
12. 每个结果必须能回答“这个值从哪里来的”。

---

# 37. Definition of Done

任何功能只有同时满足以下条件才算完成：

- 有真实代码；
- 有单元测试；
- 有集成测试或 fixture；
- 有错误路径；
- 有日志；
- 有文档；
- 有明确验收步骤；
- 无硬编码凭据；
- 无关键 placeholder；
- UI 与真实后端连通；
- 通过对应总体体验收条款。

整个产品只有完成完整 Golden Path 并通过总体 P0 验收，才允许标记 v1.0 完成。
