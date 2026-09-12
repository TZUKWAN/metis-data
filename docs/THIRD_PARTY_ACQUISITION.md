# 第三方自主采集能力清单（THIRD_PARTY_ACQUISITION）

| 项目/服务 | 许可 | 集成方式 | 生产边界 |
|---|---|---|---|
| Agent-Reach | MIT | 可选 CLI 桥（backend） | 仅只读 search/read/transcript/feed；不自动安装 |
| OpenCLI | Apache-2.0 | 可选 CLI/Browser 桥 | 用户显式启用；页面内容只读 |
| bb-browser | MIT | 安全受限桥 | 仅 loopback；命令白名单（open/snapshot/click/type/screenshot） |
| web-access | MIT | 设计基线/可选桥 | 策略/经验/tab 生命周期思想已吸收进 Router/ExperienceStore |
| Agent-Paper-Digest | MIT | 工作流吸收 | PaperWatchPlan + Digest 增量 |
| wechat_articles_spider | MIT + Apache-2.0 upstream | 独立重写 WeChat adapter | 禁止明文凭据文件；禁止"封号换号"策略 |
| MediaCrawler | NON-COMMERCIAL LEARNING 1.1 | **REFERENCE_ONLY** | 生产代码 0 引用（CI 扫描强制） |
| Jina Reader | 商业条款 | 外部 Reader 后端 | 公开 URL；无 key 基础模式 |
| XCrawl | 商业条款 | 外部 Crawl 后端 | token 只进 Vault；未配置 → NOT_CONFIGURED |
| 6551 opennews/opentwitter | 服务条款 | 外部 API 后端 | token Vault；provider_supplied_derived 标记 |

规则：第三方工具只是可替换执行后端。Metis 始终掌握 Plan/Policy/Routing/State/Raw/Provenance/Validation/Export。
