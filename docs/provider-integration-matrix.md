# Provider Integration Matrix

等级定义：P0 Registered · P1 Discovery · P2 Metadata · P3 Access · P4 Acquire · P5 Full E2E

## 已实现 adapter（22）真实验证状态

| Provider | P1 搜索 | P2 元数据 | 下载 | 证据 |
|---|---|---|---|---|
| world_bank | ✅ | ✅ | ✅ | artifacts/providers/world_bank + golden GS-1 |
| eurostat | ✅ | ✅ | ✅ | smoke + GS-1（JSON-stat→长表） |
| ilostat | ✅ | ✅ | ✅（流式 37MB） | smoke |
| un_comtrade | ✅ | ✅ | ✅ | smoke |
| zenodo | ✅ | ✅ | ✅ | GS-3（DOI 获取） |
| harvard_dataverse | ✅ | ✅ | ✅ | provider 证据 |
| figshare / dryad / osf / opendata_swiss / data_gouv_fr / huggingface_datasets | ✅ | ✅/部分 | ✅/部分 | artifacts/providers/*.json |
| data_gov_uk / us_census / usgs / oecd / wikidata / uci_ml / un_databases / nasa_earthdata | ✅ | 部分 | 部分需凭据/特定格式 | artifacts/providers |
| kaggle | ✅ | ✅ | BLOCKED（需账号，CAPTCHA 不绕过） | recipes 就绪 |
| nbs_china | BLOCKED | — | — | 403 反爬（audit 2026-09-12） |

## 仅登记（无 HTTP API/adapter）

其余平台 P0，registry `blocking_reason` + homepage 探测证据。BROWSER_SEARCH_RECIPES
机制允许这些平台通过 Live Browser 搜索升级到 P1（fixture_catalog 为参考实现）。

完整 per-capability 记录：`metis/artifacts/providers/summary.json` 与各 `verification.json`
（search/metadata/access/download 四能力 PASS/FAIL/BLOCKED + blocker）。
