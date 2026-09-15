"""P25-002: User-facing status mapper — internal states → Chinese user-friendly text."""

STATE_MAP = {
    "UNDERSTANDING": "正在理解你的需求…",
    "PLANNING": "正在规划数据方案…",
    "SEARCHING": "正在寻找数据…",
    "COLLECTING": "正在获取数据…",
    "PROCESSING": "正在整理数据…",
    "BUILDING": "正在合成数据集…",
    "WAITING_USER": "需要你的操作",
    "COMPLETE": "已完成",
    "FAILED": "遇到了问题",
    "CANCELLED": "已取消",
    "FOUND": "已找到",
    "ACQUIRING": "正在获取…",
    "READY": "可用",
    "FINAL": "最终数据集",
}

# result-card states (§9): WAITING_USER reads 需要登录 on a result, 需要你的操作 on a task
RESULT_STATE_MAP = {
    "FOUND": "已找到",
    "ACQUIRING": "正在获取",
    "WAITING_USER": "需要登录",
    "READY": "可用",
    "BUILDING": "正在整理",
    "FINAL": "最终数据集",
    "FAILED": "获取失败",
}

ERROR_MAP = {
    "LLM_TIMEOUT": "数据规划暂时较慢，请重试。",
    "PROVIDER_HTTP_ERROR": "该数据源暂时无法访问，我已继续搜索其他来源。",
    "PROVIDER_TIMEOUT": "数据源响应超时，请稍后重试。",
    "SESSION_EXPIRED": "登录已过期，请重新登录。",
    "ACQUISITION_FAILED": "未能从当前来源获取数据。",
    "INVALID_CREDENTIALS": "用户名或密码不正确。",
    "VAULT_UNAVAILABLE": "安全存储不可用，请检查系统设置。",
}


def user_facing_state(internal_state: str) -> str:
    return STATE_MAP.get(internal_state, internal_state)


def user_facing_error(error_code: str) -> str:
    return ERROR_MAP.get(error_code, "遇到了问题，请稍后重试。")
