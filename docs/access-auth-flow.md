# Access / Auth Flow

```
Download Request → AccessJob(ACCESS_PENDING)
→ INSPECTING（adapter.get_access_requirements 归一化）
→ PUBLIC → AUTHORIZED → ACQUISITION.acquire
→ UNKNOWN → 允许匿名尝试（失败在 acquire 暴露）
→ 需登录 → SESSION_CHECK（真实 storage_state 恢复 + logged_in_selector 探测）
    ├ SESSION_VALID → AUTHORIZED
    └ SESSION_EXPIRED → 账户？
        ├ 有 → LOGIN_REQUIRED → LOGGING_IN（Account Center 真实浏览器登录）
        │     login SUCCESS → storage_state 入 Vault
        │   → resume_after_user → AUTHORIZED
        │   → RESUME_COORDINATOR.resume_access_job（自动续原下载，无需二次点击）
        └ 无 → 用户开启 auto-register？ → REGISTERING（普通邮箱注册可自动）
              否则 WAITING_USER
CAPTCHA / MFA / Agreement / Payment → WAITING_* → WAITING_USER（用户接管，交还后 reprobe → resume）
```

登录态桥接：`BrowserAuthBridge.to_http_cookies(session)` 将 Playwright cookies 转 httpx
用于 HTTP 下载；仅页面按钮可下的走 Browser download event → 同一 verify/commit。

Auth Type：anonymous / browser_session / cookie / oauth / api_key / password_session
（AuthorizedAccessContext 只存 vault 引用，不存明文）。
