# Acquisition Flow（唯一生产下载路径）

```
ACQUISITION.acquire(access_job, download_job, staging_dir)
1 adapter = get_adapter(provider_id)
2 descriptors = adapter.build_acquisition_descriptor(ref, ctx)   # v2
3 每个 descriptor：
    stream_to_file(client, desc, dest)   # 流式 / Range 续传 / 大小校验 / 进度
    （auth_context cookies 经 httpx 注入；BrowserAuthBridge 提供）
4 MANAGER._verify_and_commit(file, download_job, size)
    content sniff（64KB head，防登录页伪装）→ SHA256 → raw/ 原子提交 → artifact 注册
5 全部完成 → download job COMPLETED；v2 失败 → legacy acquire_dataset 兜底（记事件）
```

约束（静态扫描 + 测试守护）：
- Adapter 禁止触碰 raw/、禁止无界 write_bytes（小 payload ≤32MB 走 write_small_payload）
- 大文件路径禁止 read_bytes()（content sniff 只读 64KB 头）
- 1GB 下载+验证 raw commit：内存有界（CI performance job）
