# Metis Data 产品总体体验收要求 + Coding Agent 实施提示词

> 版本：v1.0  
> 日期：2026-09-11  
> 说明：本文件包含两个完整独立部分。  
> **Part A：产品总体体验收要求**  
> **Part B：可直接复制给 Coding Agent 的完整实施提示词**

---

# Part A · 产品总体体验收要求

## A0. 总体验收原则

Metis Data 不能以“页面能打开”“接口返回 200”“有一段 Agent 回复”“代码文件存在”作为完成依据。

总体验收必须验证完整真实业务闭环：

```text
自然语言需求
→ DataRequirement
→ Provider 选择
→ 多平台并行发现
→ 候选数据集理解与推荐
→ Access 判断
→ Public/API / Existing Account / Auto Registration / User Intervention
→ 真实下载
→ Raw Artifact
→ Dataset Profile
→ 多源数据合成
→ QA
→ Provenance / Lineage
→ Final Data Package
→ Reproduce
```

验收分级：

- **P0：发布阻塞项**。任意一项 FAIL，v1.0 不得宣布完成。
- **P1：v1.0 重要项**。原则上必须通过；若受真实第三方外部能力变化阻塞，必须有证据和降级说明。
- **P2：增强项**。可进入后续版本。

---

# A1. P0 · 自然语言需求解析验收

测试输入：

> 构建 2015—2023 年国家层面的青年失业率、人均 GDP、教育水平面板，优先使用官方或国际组织数据。

必须满足：

- [ ] 创建真实持久化 DataRequirement；
- [ ] `unit_of_analysis` 识别为国家级；
- [ ] 时间范围识别为 2015—2023；
- [ ] 频率默认或推断为年度时，要在 assumptions 中显示；
- [ ] 识别青年失业率；
- [ ] 识别人均 GDP；
- [ ] 识别教育水平；
- [ ] preferred source 包含官方/国际组织；
- [ ] 用户可以修改解析字段；
- [ ] 修改后 Provider Selection 和 Query Plan 会重新计算；
- [ ] 原始用户请求保留；
- [ ] 不要求用户机械补齐所有非必要字段。

FAIL 条件：

- 只把原句当搜索关键词；
- 没有结构化 Requirement；
- 修改 Requirement 后搜索计划不变；
- Agent 隐式改变核心时间或研究单位但不显示。

---

# A2. P0 · Provider Registry 验收

必须检查 PRD 中所有平台。

要求：

- [ ] 全部 Provider 均存在唯一 `provider_id`；
- [ ] category 正确；
- [ ] region/country 正确；
- [ ] integration level 明确；
- [ ] capabilities 明确；
- [ ] auth mode 明确；
- [ ] browser requirement 明确；
- [ ] 未实现能力不得标 true；
- [ ] Registry 是唯一能力真相源；
- [ ] UI Integration Matrix 由 Registry 自动生成；
- [ ] Provider 不能只因写入列表就宣称“已完整接入”。

最低要求：

- 每个平台至少应有实际 P1 搜索能力；
- 公开稳定下载平台应尽可能达到 P4；
- 账号型平台按任务清单目标达到 P5；
- 支持普通自助注册且适合自动执行的平台达到 P6；
- 因第三方现实限制未达到目标的，必须有：
  - 真实 capability audit；
  - 阻塞原因；
  - 最后验证时间；
  - 不虚报。

---

# A3. P0 · 多 Provider 并行搜索验收

使用一个跨国社科需求，至少同时启用：

- World Bank；
- ILOSTAT；
- Eurostat 或 OECD；
- Zenodo 或 Harvard Dataverse。

必须：

- [ ] 至少 4 个 Provider 进入并行任务；
- [ ] UI 分别显示 queued/running/done/error；
- [ ] 一个 Provider timeout 时其他 Provider 继续；
- [ ] 一个 Provider 500 时其他 Provider 继续；
- [ ] 搜索结果统一为 DatasetCandidate；
- [ ] 每条结果保留真实 Provider；
- [ ] 保留 source ref；
- [ ] 保留 source URL；
- [ ] DOI 存在时规范化；
- [ ] 结果可取消；
- [ ] 取消后不再产生新 Provider 请求；
- [ ] 搜索历史重启后可查看。

FAIL 条件：

- 顺序搜索导致一个平台卡死整个任务；
- 失败平台让整个 SearchRun 失败；
- 结果失去来源信息；
- 返回静态假结果。

---

# A4. P0 · 去重验收

准备：

- 同一 DOI 来自两个平台；
- 同一 dataset 有镜像 URL；
- 标题相似但版本年份不同的两个真实数据集。

必须：

- [ ] 同 DOI 合并为一个逻辑候选；
- [ ] 镜像来源保留为多个 acquisition source；
- [ ] 不删除 provenance；
- [ ] 不同版本不能因标题相似被误合并；
- [ ] fuzzy dedupe 的低置信结果不得自动合并。

---

# A5. P0 · 候选数据集理解验收

随机选择至少 5 个候选。

每个候选卡必须显示或可展开查看：

- [ ] Provider；
- [ ] 发布者/作者；
- [ ] 标题；
- [ ] 描述；
- [ ] DOI（存在时）；
- [ ] 来源 URL；
- [ ] 时间范围；
- [ ] 空间范围；
- [ ] 研究单位；
- [ ] 核心变量覆盖；
- [ ] 文件格式；
- [ ] License；
- [ ] access mode；
- [ ] 是否需登录；
- [ ] 是否 restricted；
- [ ] 推荐原因；
- [ ] 限制、不足或 unknown。

推荐逻辑必须：

- [ ] hard constraints 优先；
- [ ] 不能因官方来源就忽视核心变量缺失；
- [ ] 不能因标题命中关键词就宣称变量存在；
- [ ] UNKNOWN License 不能按开放处理；
- [ ] 社区上传数据不得自动标为官方来源。

---

# A6. P0 · Live Browser 真实性验收

验收人员肉眼观察。

必须：

- [ ] 打开真实网页；
- [ ] URL 真实变化；
- [ ] 页面真实导航；
- [ ] 搜索框真实输入；
- [ ] 鼠标/点击行为可见；
- [ ] 页面滚动可见；
- [ ] Browser 不是截图轮播；
- [ ] Browser 不是录屏；
- [ ] Browser 不是 UI 伪动画；
- [ ] Agent Action Event 与页面实际变化一致；
- [ ] 多 Tab 可工作；
- [ ] 弹窗可被捕获；
- [ ] 下载可由真实 Browser 事件捕获。

---

# A7. P0 · Browser 元素定位验收

构造一个测试页面，先把“Download”按钮放在顶部，随后动态移到底部。

必须：

- [ ] 两种布局下均能找到相同语义按钮；
- [ ] 主定位不能依赖固定 x/y；
- [ ] 优先使用 accessibility role/name；
- [ ] 其次 DOM/text/stable attribute；
- [ ] DOM 不可靠时才降级 Vision；
- [ ] coordinate 只能作为最终 fallback；
- [ ] 调试日志可以看到本次使用了哪一种 locator strategy。

FAIL：

- 页面移动按钮后即无法工作；
- 默认直接用固定坐标；
- Vision 是唯一方式；
- selector 失败后无限重复点击。

---

# A8. P0 · Pause / Take Over / Return 验收

## A8.1 Pause

在连续至少 10 个 Browser Action 的测试中点击 Pause：

- [ ] 当前不可中断原子动作可以结束；
- [ ] 之后不得派发新 click；
- [ ] 不得派发新 type；
- [ ] 不得派发新 navigation；
- [ ] 状态显示 PAUSED。

## A8.2 Take Over

点击“我来操作”：

- [ ] owner 切换为 human；
- [ ] Agent input dispatcher 关闭；
- [ ] Agent 输入事件数为 0；
- [ ] 用户继续使用同一个 session；
- [ ] 用户可输入、点击、滚动、导航；
- [ ] 不重建 Browser。

## A8.3 Return

用户手动进入另一个页面后点击“交还 Agent”：

- [ ] owner 回到 agent；
- [ ] Agent 重新读取 current URL；
- [ ] Agent 重新读取 DOM/accessibility；
- [ ] 旧坐标/旧元素引用被废弃；
- [ ] 能从当前页面继续；
- [ ] 无法继续时明确进入可恢复错误，不盲点旧页面。

---

# A9. P0 · CAPTCHA / MFA / 协议介入验收

使用测试站点分别模拟：

1. CAPTCHA；
2. OTP/MFA；
3. 手机验证；
4. 机构身份认证；
5. restricted data agreement；
6. 付费确认。

必须：

- [ ] Agent 自动检测；
- [ ] 立即停止输入；
- [ ] 状态为 WAITING_USER；
- [ ] UI 明确说明触发原因；
- [ ] 允许用户接管；
- [ ] 用户完成后可交还；
- [ ] Agent 重新感知页面后继续。

严格要求：

- [ ] CAPTCHA 绕过代码不存在；
- [ ] MFA 绕过代码不存在；
- [ ] fingerprint spoofing 不存在；
- [ ] stealth anti-detection 不存在；
- [ ] Agent 不自动替用户接受 Restricted Data Agreement；
- [ ] Agent 不自动提交证件或付费。

---

# A10. P0 · Vault 与秘密安全验收

准备测试 secret：

- password；
- API key；
- OAuth access token；
- refresh token；
- cookie；
- OTP；
- Authorization header。

要求：

- [ ] 业务数据库无明文 secret；
- [ ] 普通日志无明文 secret；
- [ ] Error report 无明文 secret；
- [ ] Browser Action Event 无密码内容；
- [ ] `.env` 不进入 Git；
- [ ] auth state 不进入 Git；
- [ ] secrets scan 全通过；
- [ ] Vault 删除后 secret 不可读取；
- [ ] 每个平台 secret 可单独撤销。

FAIL：

- plaintext JSON 存密码；
- 数据库直接存 password；
- debug 日志打印 cookie；
- 任何测试 secret 可被仓库全文搜索到。

---

# A11. P0 · 独立密码验收

自动注册两个测试 Provider。

必须：

- [ ] 使用两个不同密码；
- [ ] 默认至少 16 字符；
- [ ] 含大写；
- [ ] 含小写；
- [ ] 含数字；
- [ ] 含特殊字符；
- [ ] 使用安全随机源；
- [ ] Provider 特定规则可 override；
- [ ] 密码写入 Vault；
- [ ] 普通 UI 不明文展示；
- [ ] 普通日志不展示。

---

# A12. P0 · 已有账号登录验收

测试站点模拟已有账户：

- [ ] 用户可绑定；
- [ ] secret 写 Vault；
- [ ] Agent 可登录；
- [ ] 登录成功识别准确；
- [ ] 错误密码识别为 invalid credentials；
- [ ] 不无限重试；
- [ ] session 可安全保存；
- [ ] 应用重启后 session 可合法复用；
- [ ] session 过期后进入 expired；
- [ ] 用户删除账户后下一次访问必须重新认证。

---

# A13. P0 · 自动注册验收

普通自助注册 fixture：

- [ ] 用户开启 auto registration 后才允许执行；
- [ ] 关闭时 0 次注册提交；
- [ ] 使用 Data Identity；
- [ ] 使用独立密码；
- [ ] 字段映射正确；
- [ ] 可识别注册成功；
- [ ] 可识别 duplicate email；
- [ ] 可识别 password rule failed；
- [ ] 可识别 verify email required；
- [ ] 未验证时不得标 fully active；
- [ ] CAPTCHA 出现后停止。

---

# A14. P0 · DownloadJob 验收

任何下载：

- [ ] 先生成 DownloadJob；
- [ ] 有 provider；
- [ ] 有 dataset ref；
- [ ] 有 source URL；
- [ ] 有 access mode；
- [ ] 有 version（若存在）；
- [ ] 有 License 状态；
- [ ] 有开始时间；
- [ ] 有完成/失败状态；
- [ ] 有实际文件记录。

无 DownloadJob 的 downloader 调用必须失败。

---

# A15. P0 · HTTP/API 下载验收

使用大于 100MB 的 fixture 或等效生成数据：

- [ ] streaming 下载；
- [ ] 不一次性读入全部文件；
- [ ] UI/事件有进度；
- [ ] 网络中断产生可重试错误；
- [ ] partial 文件不会进入 raw；
- [ ] 完成后 atomic rename；
- [ ] SHA256；
- [ ] 文件大小；
- [ ] manifest 更新。

---

# A16. P0 · Browser 下载验收

真实测试下载页：

- [ ] Browser 点击 Download；
- [ ] 捕获真实 download event；
- [ ] 绑定正确 DownloadJob；
- [ ] 文件进入该任务的 raw 临时路径；
- [ ] 下载完成后校验；
- [ ] suggested filename 被记录；
- [ ] source tab/URL 被记录；
- [ ] 页面显示“下载成功”但无文件时不得判完成。

---

# A17. P0 · 文件识别安全验收

准备：

- HTML 登录页伪装为 `.csv`；
- HTML 错误页伪装为 `.zip`；
- 正常 CSV；
- 正常 ZIP。

必须：

- [ ] HTML 伪 CSV 被识别；
- [ ] HTML 伪 ZIP 被识别；
- [ ] 不生成 DatasetArtifact Completed；
- [ ] 正常文件通过；
- [ ] 错误有明确 `INVALID_DOWNLOAD_CONTENT` 或等价错误码。

---

# A18. P0 · 安全解压验收

测试：

- 正常 ZIP；
- `../evil.txt` zip slip；
- 超大解压比例压缩包；
- 超多小文件压缩包。

必须：

- [ ] 正常 ZIP 成功；
- [ ] zip slip 被拒绝；
- [ ] 超出阈值停止；
- [ ] 不写出 Workspace；
- [ ] 部分解压失败不被当成功。

---

# A19. P0 · Raw Immutable 验收

下载后：

1. 记录 Raw checksum；
2. 完成清洗；
3. 完成 Join；
4. 完成 Export；
5. 再计算 Raw checksum。

必须：

- [ ] Raw checksum 不变；
- [ ] transform 只写 intermediate/final；
- [ ] 尝试写 raw 被拦截；
- [ ] final 不能覆盖 raw 文件名路径。

---

# A20. P0 · 格式解析验收

最低 fixture：

- UTF-8 CSV；
- GBK/中文编码 CSV；
- TSV；
- XLS；
- XLSX 多 Sheet；
- JSON；
- JSONL；
- Parquet；
- DTA；
- SAV；
- SAS；
- GeoJSON；
- Shapefile；
- NetCDF；
- SQLite；
- HTML table。

要求：

- [ ] 正确 route；
- [ ] 不只根据扩展名盲判；
- [ ] 行列/结构可获取；
- [ ] 多 Sheet 不被丢弃；
- [ ] DTA/SAV 的 variable/value labels 尽可能保留；
- [ ] Geo 数据识别 CRS/geometry metadata；
- [ ] NetCDF 至少识别 dimensions/variables；
- [ ] unsupported 明确报错而不是 crash。

---

# A21. P0 · Dataset Profile 验收

每个表格型数据集至少产生：

- [ ] row count；
- [ ] column count；
- [ ] schema；
- [ ] type；
- [ ] nullable；
- [ ] sample；
- [ ] missing rate；
- [ ] unique；
- [ ] numeric min/max；
- [ ] duplicate row count；
- [ ] likely key；
- [ ] likely time；
- [ ] likely geography；
- [ ] likely ID；
- [ ] codebook link（若存在）。

100MB+ 数据：

- [ ] profile 不 OOM；
- [ ] preview 不要求全表渲染。

---

# A22. P0 · Variable Semantics 验收

构造：

- `GDP` current local currency；
- `GDP` constant 2015 USD；
- `unemployment_rate` percentage；
- `unemployment_rate` fraction；
- `gender` 0/1；
- `sex` M/F。

要求：

- [ ] 同名 GDP 被识别为不同口径；
- [ ] 不直接覆盖；
- [ ] percentage/fraction 被判 convertible；
- [ ] conversion 有公式；
- [ ] gender/sex 可通过明确 mapping 对齐；
- [ ] original field 和 coding 始终保留；
- [ ] UNKNOWN semantics 不能冒充 compatible。

---

# A23. P0 · 国家实体解析验收

fixture：

```text
United States
USA
US
840
GB
United Kingdom
China
CHN
```

必须：

- [ ] 合法别名映射至同一 canonical country；
- [ ] ISO2/ISO3 可互转；
- [ ] 原始值保留；
- [ ] confidence 记录；
- [ ] 无法确定的国家名不静默猜测。

---

# A24. P0 · 中国行政区解析验收

fixture：

```text
北京
北京市
110000
内蒙古
内蒙古自治区
武汉
武汉市
420100
```

必须：

- [ ] 省级别名规范化；
- [ ] 地级名称/代码规范化；
- [ ] canonical ID 稳定；
- [ ] 原始名称保留；
- [ ] 历史行政区变化有 valid_from/valid_to 或等价版本机制；
- [ ] 历史不存在实体不能无提示映射为现代实体；
- [ ] fuzzy match 低置信结果不进入 final。

---

# A25. P0 · 时间规范化验收

fixture：

```text
2020
"2020年"
2020-01-01
2020Q1
2020-03
FY2020
```

要求：

- [ ] 年、季、月可正确识别；
- [ ] FY2020 不无提示当自然年；
- [ ] 不同频率 Join 前触发冲突检查；
- [ ] 月→年必须明确 aggregation；
- [ ] aggregation 方法写 provenance。

---

# A26. P0 · Join Cardinality 验收

准备：

- 1:1；
- 1:m；
- m:1；
- m:m。

要求：

- [ ] Join 前识别 cardinality；
- [ ] 声明 1:1 时实际重复必须失败；
- [ ] m:m 默认阻止；
- [ ] 不产生意外笛卡尔积；
- [ ] 输出预计/实际 row count；
- [ ] 输出 matched/unmatched；
- [ ] 输出 coverage。

---

# A27. P0 · 多源国家面板 Golden Build

Dataset A：

```text
country_name, iso3, year, gdp_per_capita
```

Dataset B：

```text
country, country_code, year, youth_unemployment
```

要求：

- [ ] 国家实体统一；
- [ ] year 统一；
- [ ] key 明确为 country/year；
- [ ] cardinality 正确；
- [ ] Join 成功；
- [ ] coverage 有统计；
- [ ] unmatched 有样例；
- [ ] final row count 合理；
- [ ] 两个 source 均保留；
- [ ] 字段 lineage 完整。

---

# A28. P0 · 缺失与插补验收

默认 Build：

- [ ] 未配置时 0 个缺失值被自动填补。

配置线性插值：

- [ ] 插补只作用指定字段/分组；
- [ ] 插补值有 mask 或 lineage；
- [ ] operation id 可查；
- [ ] method 可查；
- [ ] parameters 可查；
- [ ] quality report 显示插补比例；
- [ ] Raw 不变。

---

# A29. P0 · Derived Variable 验收

创建：

```text
gdp_per_capita = gdp / population
```

要求：

- [ ] 公式明确；
- [ ] 输入字段明确；
- [ ] output field 明确；
- [ ] division by zero 有处理；
- [ ] lineage 标记 derived；
- [ ] 修改公式后版本/operation 变化。

---

# A30. P0 · Validation 验收

至少检测：

- [ ] key duplicate；
- [ ] missing；
- [ ] impossible value；
- [ ] outlier/warning；
- [ ] temporal gap；
- [ ] join coverage；
- [ ] unmatched entities；
- [ ] constant columns；
- [ ] type drift；
- [ ] row count drift。

每条 Validation 必须有：

- code；
- severity；
- message；
- affected field/rows（适用时）；
- remediation（可提供时）。

---

# A31. P0 · Provenance 验收

数据集级：

- [ ] Provider；
- [ ] source URL；
- [ ] DOI；
- [ ] dataset ID；
- [ ] version；
- [ ] License；
- [ ] download time；
- [ ] access mode；
- [ ] checksum。

Transformation：

- [ ] operation id；
- [ ] input；
- [ ] output；
- [ ] type；
- [ ] params；
- [ ] row count before/after；
- [ ] column count before/after；
- [ ] warning；
- [ ] code version。

字段级随机抽 10 列：

- [ ] source field 可追溯；
- [ ] rename 可追溯；
- [ ] unit conversion 可追溯；
- [ ] recode 可追溯；
- [ ] derived formula 可追溯；
- [ ] join source 可追溯。

---

# A32. P0 · Final Data Package 验收

每个完成 Build 至少包含：

```text
final/
  dataset.parquet
  dataset.csv
  dataset.xlsx   # 数据规模允许时
metadata/
  dataset.json
  variables.json
  sources.json
provenance/
  lineage.json
  transformations.json
  checksums.json
reports/
  quality_report.html
  methodology.md
scripts/
  reproduce.py
```

同时必须有：

- raw/ 或可靠 raw reference manifest；
- intermediate/ 或 checkpoint manifest；
- 顶层 package manifest。

所有 manifest 引用文件必须实际存在。

---

# A33. P0 · Methodology Report 验收

报告必须根据真实 provenance 自动生成，至少说明：

- 数据来源；
- 获取日期；
- 版本；
- 许可；
- 数据文件；
- 变量选择；
- 变量映射；
- 单位变换；
- 实体对齐；
- 时间对齐；
- Join；
- 缺失处理；
- 派生变量；
- 质量检查；
- 未匹配数据；
- 关键 warnings。

FAIL：

- 报告写了实际上没有发生的处理；
- 报告漏掉插补；
- 报告无法对应 source manifest。

---

# A34. P0 · Reproduce 验收

固定 fixture 构建完成后：

1. 删除 final；
2. 删除 intermediate；
3. 保留 raw 或允许脚本从固定测试 source 重取；
4. 在干净环境执行 reproduce；
5. 比较结果。

必须：

- [ ] schema 等价；
- [ ] 行数一致；
- [ ] 列数一致；
- [ ] 关键统计一致；
- [ ] 确定性步骤 checksum 一致；
- [ ] 不依赖聊天历史；
- [ ] 不需要人工修改脚本；
- [ ] dependency/version 有记录。

---

# A35. P0 · 崩溃恢复验收

分别在以下位置强杀进程：

1. Search 进行中；
2. Download 50%；
3. Profile 进行中；
4. Join 完成后；
5. Export 前。

重启：

- [ ] 无假 COMPLETE；
- [ ] 不重复 raw；
- [ ] 不重复注册账号；
- [ ] 不重复提交外部协议；
- [ ] 可恢复步骤从 checkpoint 继续；
- [ ] 不可安全重放的外部 Browser 操作进入 NEEDS_REVIEW；
- [ ] UI 清楚告诉用户当前状态。

---

# A36. P0 · Cancel 验收

对 Search/Download/Build 分别取消。

必须：

- [ ] cancellation 传播到子 worker；
- [ ] 不再发送新外部请求；
- [ ] Browser worker 停止；
- [ ] partial 文件按策略清理/保留为可恢复状态；
- [ ] 不生成 Completed Final；
- [ ] 任务状态明确为 CANCELLED。

---

# A37. P0 · Secrets Scan 验收

发布前：

- [ ] Git 历史和当前工作树运行 secrets scan；
- [ ] `.env` 排除；
- [ ] session state 排除；
- [ ] fixture 不含真实 secret；
- [ ] test secret 触发规则；
- [ ] 扫描结果保存到 Final Acceptance Report。

---

# A38. P0 · 全链路 Golden Scenario

测试需求：

> 构建 2015—2023 年国家层面的青年失业、人均 GDP 和教育水平面板，优先官方/国际组织数据，并交付 CSV、Parquet、XLSX、数据说明、数据质量报告和可复现脚本。

必须真实完成：

```text
Requirement
→ 至少 4 Provider 搜索
→ 候选推荐
→ 至少 2 Source 获取
→ Raw
→ Profile
→ Variable Semantics
→ Entity Resolution
→ Time Alignment
→ Join
→ Validation
→ Provenance
→ Final Package
→ Reproduce
```

任何一个箭头由静态 mock 代替则 Golden Scenario FAIL。

---

# A39. P1 · UX 验收

一个没有读代码的普通用户应能完成：

- [ ] 创建数据任务；
- [ ] 修改 Requirement；
- [ ] 查看 Provider 搜索进度；
- [ ] 查看候选；
- [ ] 比较推荐理由；
- [ ] 打开数据详情；
- [ ] 打开 Live Browser；
- [ ] Pause；
- [ ] Take Over；
- [ ] Return；
- [ ] 绑定已有账号；
- [ ] 删除账号；
- [ ] 开关自动注册；
- [ ] 查看下载；
- [ ] 预览表格；
- [ ] 查看 schema/profile；
- [ ] 加入 Build；
- [ ] 查看 Build Plan；
- [ ] 看到 m:m/语义/缺失警告；
- [ ] 执行 Build；
- [ ] 查看 QA；
- [ ] 查看 Provenance；
- [ ] 下载 Final Data Package。

---

# A40. P1 · 性能验收

最低：

- [ ] Provider Registry 加载不造成明显 UI 阻塞；
- [ ] 多 Provider 真并发；
- [ ] 100MB CSV Profile 不 OOM；
- [ ] 1GB 级测试数据走 chunk/columnar/streaming；
- [ ] 10 万行 Preview 不一次性 DOM 渲染；
- [ ] Download/Build 不阻塞 UI 主线程；
- [ ] 长 Build 可 checkpoint；
- [ ] 记录 benchmark：时间、峰值内存、临时磁盘。

---

# A41. 发布阻塞清单

出现任何一项，Final Verdict 必须 FAIL：

- 明文 secret；
- Live Browser 是假动画；
- 默认固定坐标操作；
- CAPTCHA/MFA 绕过；
- stealth/fingerprint spoofing；
- Raw 被覆盖；
- 下载无 DownloadJob；
- 数据无来源；
- 登录 HTML 被当数据；
- UNKNOWN License 被当开放；
- 同名列无语义检查直接覆盖；
- m:m 无 guard；
- 插补无标记；
- Final 无 lineage；
- Provenance 无 source URL/ID；
- Reproduce 失败；
- 崩溃恢复重复外部提交；
- Provider capability 虚报；
- Golden Scenario 失败。

---

# A42. 最终验收报告模板

```markdown
# Metis Data v1.0 Final Acceptance Report

## 1. Version
branch:
commit:
tag:
date:

## 2. Environment
OS:
runtime:
database:
browser:
workspace:

## 3. P0 Acceptance
A1: PASS/FAIL + evidence
A2: PASS/FAIL + evidence
...
A38: PASS/FAIL + evidence

## 4. P1 Acceptance
A39: PASS/FAIL
A40: PASS/FAIL

## 5. Provider Matrix
Provider | Target | Actual | Search | Metadata | Download | Auth | Registration | Browser | Test

## 6. Golden Scenario
input:
providers:
selected datasets:
build:
outputs:
reproduce:
result:

## 7. Security
secrets scan:
vault:
log redaction:
session:
result:

## 8. Browser
headed:
locator:
pause:
takeover:
intervention:
crash recovery:
result:

## 9. Data Synthesis
semantic:
entity:
time:
cardinality:
join:
missing:
validation:
result:

## 10. Provenance
source:
transform:
field lineage:
checksum:
reproduce:
result:

## 11. Performance
dataset size:
duration:
peak memory:
temporary disk:
result:

## 12. Known Limitations
只允许真实 P1/P2 或第三方客观限制。
不得把任何 P0 FAIL 放到这里规避验收。

## 13. Final Verdict
PASS / FAIL
```

只有全部 P0 为 PASS，Final Verdict 才能为 PASS。

---

# Part B · 可直接发送给 Coding Agent 的完整提示词

以下从 `[PROMPT START]` 到 `[PROMPT END]` 可以整体复制给实现 Agent。

---

## [PROMPT START]

你现在要在当前工作区内实现一个独立产品/Agent：**Metis Data**。

你的工作目标是实际完成产品，不是给我再写一份方案，不是只做 UI demo，不是只描述技术路线。

你必须先遍历现有工作区，完整理解已有架构，尽可能复用现有 Browser、Agent、事件流、文件、数据库、任务调度和 UI 能力，然后严格按照工作区中的三份 Metis Data 文档逐项实现、逐项测试、逐项验收。

### 1. 必读文档

首先完整读取：

1. `Metis_Data_PRD.md`
2. `Metis_Data_Build_Task_List.md`
3. `Metis_Data_Acceptance_and_Agent_Prompt.md`

如果下载后文件名有轻微变化，以文档标题为准。

三份文档共同构成需求真相源。

优先级：

1. 安全边界；
2. 总体验收 P0；
3. PRD；
4. Build Task List；
5. 你根据当前技术栈做的局部工程实现选择。

不得自行删除核心能力。

### 2. 开始顺序

不要先写 UI。

严格从：

```text
P00
→ P01
→ P02
→ P03...
```

开始执行。

首先完成：

- 仓库扫描；
- 基线记录；
- 模块边界；
- 测试门禁；
- logging；
- errors；
- workspace；
- progress tracking。

如果项目已有对应能力，先读源码确认，再复用/改造。

不要因为重新写更方便就建立第二套平行系统。

### 3. 每个最小任务的执行循环

每一个 Task ID 都按以下流程：

```text
READ TASK
→ CHECK DEPENDENCY
→ INSPECT EXISTING CODE
→ IMPLEMENT
→ WRITE/UPDATE TEST
→ RUN TASK ACCEPTANCE
→ FIX FAILURE
→ RUN AGAIN
→ UPDATE IMPLEMENTATION_PROGRESS.md
→ COMMIT / RECORD DIFF
→ NEXT TASK
```

任务只有全部验收通过才标 DONE。

如果第三方平台发生客观变化：

- 记录真实现状；
- 保存 capability audit；
- 写 last_verified_at；
- 如实降低 integration level；
- 继续推进其他任务。

不允许通过伪造成功状态解决外部限制。

### 4. IMPLEMENTATION_PROGRESS.md

如果不存在则创建。

必须持续维护：

```markdown
# Metis Data Implementation Progress

## Current Phase
Pxx

## Current Task
Pxx-xxx

## Completed
- Task IDs

## Modified Files
- path
- path

## Tests Executed
- command
- PASS/FAIL

## Blockers
- provider / reason / evidence

## Next Task
Pxx-xxx
```

每完成一个 Task 立刻更新。

### 5. 不要问无关紧要的技术选择

如果存在：

- 数据库 ORM 具体选法；
- 文件类怎么命名；
- 某个内部接口小差异；
- 前端组件内部组织；
- 测试 fixture 目录；

根据现有仓库技术栈做最合理选择，记录 architecture decision，然后继续。

只有涉及：

- 删除用户数据；
- 真实付费；
- 提交真实个人证件；
- 接受真实受限数据法律协议；
- 修改生产凭据；
- 破坏性生产迁移；

才停止那个危险动作。

其他任务继续做。

### 6. 产品核心链路不可删

必须完整存在：

```text
Natural Language Requirement
→ DataRequirement
→ Provider Selection
→ Query Planning
→ Parallel Search
→ Candidate Normalization
→ Deduplication
→ Dataset Intelligence
→ Recommendation
→ Access Inspection
→ Acquisition
→ Raw
→ Profile
→ Semantic Alignment
→ Entity Resolution
→ Temporal Alignment
→ Transform / Join
→ QA
→ Provenance
→ Export
→ Reproduce
```

不能把其中任何状态只存在聊天文本里。

必须有真实对象、状态、数据或 artifact。

### 7. Provider 架构

先统一，再逐个平台。

必须有：

```text
ProviderRegistry
Provider
ProviderCapabilities
ProviderAdapter
ProviderContractTest
ProviderHealth
IntegrationMatrix
```

统一接口至少：

```text
search_datasets
get_dataset_metadata
preview_dataset
get_access_requirements
acquire_dataset
refresh_auth
```

可选：

```text
login
register_account
request_api_key
```

UI 不允许调用 provider-specific 私有方法。

### 8. 全平台接入要求

PRD 中列出的所有平台全部进入 Registry。

不要只做 MVP 8 个。

最低：

- 所有 Provider 至少有真实 P1 搜索；
- 有稳定公开下载能力的做到 P4；
- 账号型平台按 Build Task List 做 P5；
- 普通自助注册型平台按适用条件做 P6。

MVP 代表性真实闭环至少：

- World Bank；
- Eurostat；
- ILOSTAT；
- Data.gov；
- Zenodo；
- Harvard Dataverse；
- Kaggle；
- 国家统计局或 NDSMS。

每个平台必须有：

```text
CAPABILITIES.md
adapter
fixture
contract test
真实 smoke 记录
last_verified_at
```

如果平台只有 catalog：

例如 Data.gov、data.europa.eu、Google Dataset Search、Papers with Code，

必须将其视为发现层，解析真正 distribution/source。

不能把 catalog HTML 当数据文件。

### 9. Browser

Browser 必须是真实可见 headed Chromium/Chrome。

如果项目已有 Computer Use，优先复用。

支持：

```text
navigate
back
forward
click
double click
type
key
scroll
select
upload
download
new tab
close tab
switch tab
DOM read
accessibility read
screenshot
```

定位策略固定：

```text
Accessibility role/name
→ Semantic DOM
→ Text
→ Stable CSS/data attribute
→ Vision
→ Coordinate fallback
```

固定坐标不能是主要实现。

### 10. Browser 用户可观察

用户必须实时看到：

- 当前网页；
- 页面导航；
- AI 点击；
- AI 输入；
- AI 滚动；
- 下载触发；
- 当前操作状态。

右侧事件流显示：

- action；
- target；
- status；
- timestamp；
- provider/task。

任何 secret value 都必须 mask。

### 11. Pause / Take Over / Return

必须真实控制后端 dispatcher。

Pause：

- 当前原子动作结束；
- 停止新动作。

Take Over：

- owner=human；
- Agent 0 输入；
- 不重建 session。

Return：

- owner=agent；
- 重新读取 URL；
- 重新读取 DOM/accessibility；
- 丢弃旧坐标；
- 从用户当前页面继续。

### 12. 严禁 Browser 对抗机制

不要实现：

- CAPTCHA bypass；
- MFA bypass；
- OTP interception 绕过；
- browser fingerprint spoofing；
- stealth anti-detection；
- rate limit evasion；
- 访问控制规避；
- paywall bypass。

出现以下情况：

```text
CAPTCHA
MFA
Phone OTP
Institution Verification
Identity Verification
Restricted Data Agreement
Payment
High-risk Terms
```

立即：

```text
PAUSE
→ WAITING_USER
→ SHOW REASON
→ ALLOW TAKEOVER
→ USER FINISHES
→ RETURN
→ RE-READ PAGE
→ CONTINUE
```

### 13. Access Strategy

按照：

```text
Public Anonymous / Official API
→ Existing Valid Session
→ Existing User Account
→ Auto Registration
→ User Intervention
```

执行。

不要所有数据都强制走 Browser。

官方 API 可稳定完成时优先 API。

Browser 主要处理：

- 页面搜索；
- 登录；
- 注册；
- 授权；
- 动态资源；
- 无稳定 API 的下载。

### 14. Data Identity

实现用户数据身份：

```text
name
email
country
institution
role
ORCID optional
research purpose optional
```

用户可以逐项编辑和禁用自动提交。

### 15. Vault

实现 SecretStore abstraction。

优先：

- Windows Credential Manager；
- macOS Keychain；
- Linux Secret Service；
- 或项目已有等价安全 Secret Store。

禁止 plaintext fallback。

数据库只保存：

```text
secret_id
provider_id
account metadata
session ref
```

不保存 secret 本体。

### 16. 密码

不要实现全平台共享真实密码。

用户管理 Metis Data 主解锁。

每个 Provider 自动生成独立随机密码：

- 至少 16 字符；
- 大写；
- 小写；
- 数字；
- 特殊字符；
- 安全随机；
- Provider 特定规则可覆盖。

普通日志和 UI 不显示密码。

### 17. 自动注册

用户必须先开启 Auto Registration。

执行：

```text
open registration
→ map Data Identity
→ generate provider password
→ fill
→ submit
→ classify result
```

结果至少：

```text
SUCCESS
VERIFY_EMAIL_REQUIRED
DUPLICATE_ACCOUNT
PASSWORD_RULE_FAILED
CAPTCHA_REQUIRED
MFA_REQUIRED
USER_INTERVENTION
FAILED
```

遇到 CAPTCHA、实名、受限协议等立即暂停。

### 18. 搜索

Requirement Parser 提取：

- research question；
- unit；
- population；
- geography；
- time；
- frequency；
- outcomes；
- exposures；
- mediators；
- moderators；
- controls；
- identifiers；
- source preference；
- license；
- format。

Provider Selector 应根据研究语境选平台。

例如中国宏观需求，官方源优先。

不要把 Kaggle 因搜索方便排在官方数据前面。

Search Orchestrator：

- 并发；
- timeout；
- retry；
- backoff；
- rate limit；
- circuit breaker；
- cancel；
- progress。

### 19. Dataset Candidate

统一 schema。

至少：

```text
title
description
provider
publisher/authors
source_ref
source_url
doi
version
license
access
time coverage
geography
unit of analysis
variable hints
files
raw metadata ref
```

Unknown 必须真实 unknown。

### 20. 候选推荐

不要只输出一个黑盒总分。

至少分别比较：

- topic；
- variables；
- unit；
- time；
- geography；
- source trust；
- DOI/publication；
- license；
- access；
- documentation；
- missing/quality if previewed。

输出：

```text
reasons
limitations
unknowns
```

### 21. DownloadJob

任何下载前必须：

```text
create DownloadJob
```

无 Job 的 downloader 禁止执行。

下载过程：

```text
.partial
→ stream
→ complete
→ type check
→ size
→ checksum
→ safe extract
→ atomic raw commit
→ DatasetArtifact
```

页面出现“download successful”不能代替真实文件事件。

### 22. Raw Immutable

Raw 数据只能读。

所有清洗输出：

```text
intermediate
```

最终输出：

```text
final
```

同 checksum 可以物理去重，但来源引用不得丢。

### 23. Parser

最低支持：

```text
CSV
TSV
XLS
XLSX
JSON
JSONL
Parquet
DTA
SAV
SAS
ZIP/TAR/GZ
GeoJSON
Shapefile
NetCDF
SQLite
HTML table
```

统计软件格式尽量保留：

- variable labels；
- value labels。

Geo/Science 格式至少可靠读取：

- schema；
- CRS/dimensions/variables；
- metadata。

### 24. Profile

自动生成：

```text
row count
column count
schema
type
sample
missing
unique
min/max
duplicate
likely key
likely ID
likely time
likely geography
labels
codebook
```

大文件必须 streaming/chunk/columnar。

不要为了 Profile 在内存中复制多个完整 DataFrame。

### 25. Variable Semantics

生成：

```text
canonical_name
original_name
definition
unit
scale
coding
frequency
geography_level
population
price_basis
currency
source
confidence
```

同名不等于同义。

重点处理：

- current price vs constant price；
- percentage vs fraction；
- nominal vs real；
- different base year；
- survey self-report vs administrative；
- category coding differences。

### 26. Build Plan

合成前必须先生成计划：

```text
inputs
target unit
keys
semantic mapping
unit conversion
entity mapping
time mapping
append/join sequence
missing policy
derived variables
validation
exports
```

计划在 UI 中可见。

危险行为突出：

- m:m；
- aggregation；
- drop；
- imputation；
- low-confidence entity match。

### 27. Entity Resolution

至少实现：

```text
ISO2
ISO3
country names
country aliases
China province names/codes
China prefecture names/codes
```

行政区表必须可版本化。

历史变化不能用现代名称静默覆盖。

Fuzzy match：

- confidence；
- threshold；
- low confidence = block/review。

### 28. Time Alignment

支持：

```text
year
quarter
month
day
```

不同频率默认不直接 Join。

任何：

- aggregation；
- annualization；
- interpolation；
- forward fill；

必须记录 provenance。

### 29. Join

执行前：

```text
key validation
duplicate check
cardinality check
estimated output rows
coverage estimate
```

支持：

```text
1:1
1:m
m:1
```

m:m 默认阻止。

执行后：

```text
matched
unmatched left
unmatched right
coverage
row before/after
```

### 30. Missing

默认：

```text
NONE
```

支持：

- drop；
- ffill；
- bfill；
- linear interpolation；
- group interpolation；
- statistical/model imputation。

任何生成值：

- 标记；
- operation id；
- method；
- params；
- source；
- report。

### 31. Derived Variables

只能通过明确受控公式生成。

记录：

```text
formula
input fields
output field
operation id
code version
```

处理除零、缺失、类型异常。

### 32. Validation

至少：

```text
key uniqueness
duplicate
missing
range
impossible values
outliers
unit anomaly
temporal gaps
join coverage
unmatched entity
constant column
type drift
row count drift
```

统一：

```text
INFO
WARNING
ERROR
BLOCKING
```

### 33. Provenance

强制从 v1 第一版实现，不得延期。

Source：

```text
provider
URL
DOI
dataset id
version
license
download time
access
checksum
```

Transformation：

```text
operation id
type
params
input
output
row before/after
column before/after
warning
code version
```

Field Lineage：

```text
final field
→ transform
→ source field
→ raw artifact
→ provider dataset
→ URL/DOI
```

### 34. Final Data Package

至少：

```text
final/
metadata/
provenance/
reports/
scripts/
```

包含：

```text
dataset.parquet
dataset.csv
dataset.xlsx
dataset.json
variables.json
sources.json
lineage.json
transformations.json
checksums.json
quality_report.html
methodology.md
reproduce.py
```

Raw 可内含或以可靠 manifest 引用。

### 35. UI

主工作区：

左：

- Requirement；
- Sources；
- Candidates；
- Downloads；
- Builds；
- Provenance。

中：

- Live Browser；
- Data Preview；
- Schema/Profile。

右：

- Agent tool events；
- recommendation rationale；
- warning；
- user intervention。

不要展示私有 chain-of-thought。

只显示用户需要理解的执行摘要。

### 36. 测试要求

每个 Task 运行单项验收。

必须有：

```text
unit
integration
provider contract
browser E2E
auth E2E
registration E2E
download E2E
build E2E
security
recovery
performance
golden scenario
```

CI 主要使用 fixture。

真实 Provider 使用 smoke，并记录日期。

不要让 CI 完全依赖实时外网。

### 37. Provider Contract Test

每个平台至少验证：

- search output schema；
- metadata schema；
- capability；
- timeout；
- cancel；
- access classification；
- download content validation（适用时）；
- auth required（适用时）；
- error normalization。

### 38. 崩溃恢复

状态必须持久化。

重启：

- Search 可重新调度未完成 Provider；
- Download 可安全重试/恢复；
- Profile 可重跑；
- Build 从 checkpoint；
- 外部不可重复 Browser 提交进入 NEEDS_REVIEW。

绝不能重启后重复：

- 注册；
- 购买；
- 协议提交；
- 高风险表单。

### 39. 性能

大文件：

- streaming download；
- chunk parse；
- Parquet/Arrow/Polars/DuckDB 等根据现有栈选最适合方案；
- Preview 虚拟化；
- Build worker 不阻塞 UI。

记录性能测试。

### 40. 不允许通过以下方式“完成”

严禁：

- 静态假 Candidate；
- 静态假 Browser；
- 假下载；
- mock 永久代替 production；
- TODO；
- pass；
- hardcoded success；
- hardcoded Provider capability；
- 为通过测试改测试使错误消失；
- 捕获所有 exception 后返回 success；
- 吞掉 Validation ERROR；
- 跳过 provenance；
- 跳过 reproduce；
- 用 AI 猜测值补数据。

### 41. 每 Phase 完成后

必须：

```text
unit PASS
integration PASS
contract PASS
relevant E2E PASS
lint PASS
typecheck PASS
format PASS
secrets scan PASS
progress updated
test report generated
```

然后进入下一 Phase。

### 42. 总体 Golden Scenario

最终必须实际执行：

> 构建 2015—2023 年国家层面的青年失业、人均 GDP 和教育水平面板，优先官方或国际组织数据。

要求：

- 至少 4 Provider 搜索；
- 至少 2 Source 被实际获取；
- Raw 可查；
- Profile 可查；
- Variable Semantics 可查；
- 国家实体统一；
- 时间统一；
- Join 可查；
- coverage 可查；
- missing 可查；
- QA 可查；
- Source Provenance 可查；
- Field Lineage 可查；
- Final CSV/Parquet/XLSX；
- Quality Report；
- Methodology；
- Reproduce；
- Reproduce 实际 PASS。

### 43. 最终验收

完整执行 `Metis_Data_Acceptance_and_Agent_Prompt.md` Part A。

生成：

```text
Metis_Data_v1_Final_Acceptance_Report.md
```

报告必须逐项 PASS/FAIL。

任何 P0 FAIL：

```text
Final Verdict = FAIL
```

不得写：

- “基本完成”；
- “主体完成”；
- “后续优化”；

来规避 P0。

### 44. 最终输出给我的内容

只有完成当前可完成的全部任务后，再给我汇报：

1. 当前 commit；
2. 已完成 Task 数；
3. 未完成 Task；
4. 外部阻塞 Provider；
5. Golden Test；
6. Final Acceptance；
7. 关键输出文件；
8. 真实 Known Limitations。

在执行过程中继续自己推进，不要每一个技术细节都停下来等我确认。

现在开始：

**第一步先递归遍历整个工作区，完成 P00-001。不要先写 UI，不要先实现某个 Provider。**

## [PROMPT END]

---

# Part C · 使用建议

将本文件与另外两份文档放入同一个 Agent 工作空间。

建议文件名保持：

```text
Metis_Data_PRD.md
Metis_Data_Build_Task_List.md
Metis_Data_Acceptance_and_Agent_Prompt.md
```

然后把 Part B 整段发送给 Coding Agent。

不要只发 Prompt 而不提供另外两份文档，因为最细的 263 个任务和逐项验收位于 `Metis_Data_Build_Task_List.md` 中。
