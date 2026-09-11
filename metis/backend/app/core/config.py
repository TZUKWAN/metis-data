"""Metis Data core configuration. Values come from environment / .env (never commit .env)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[3]  # metis/backend


def _load_dotenv() -> None:
    """Minimal .env loader (no external dependency). Does not override existing env."""
    candidate = APP_ROOT.parent / ".env"
    if not candidate.exists():
        return
    for line in candidate.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    env: str = field(default_factory=lambda: _env("METIS_ENV", "development"))
    host: str = field(default_factory=lambda: _env("METIS_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _env_int("METIS_PORT", 8300))

    workspace_dir: Path = field(default_factory=lambda: Path(_env("METIS_WORKSPACE_DIR", "./metis/workspace")).resolve())
    db_url: str = field(default_factory=lambda: _env("METIS_DB_URL", ""))

    log_level: str = field(default_factory=lambda: _env("METIS_LOG_LEVEL", "INFO"))
    log_dir: Path = field(default_factory=lambda: Path(_env("METIS_LOG_DIR", "./metis/workspace/logs")).resolve())

    browser_headless: bool = field(default_factory=lambda: _env_bool("METIS_BROWSER_HEADLESS", False))
    browser_download_dir: Path = field(default_factory=lambda: Path(_env("METIS_BROWSER_DOWNLOAD_DIR", "./metis/workspace/downloads/browser")).resolve())
    browser_user_data_dir: Path = field(default_factory=lambda: Path(_env("METIS_BROWSER_USER_DATA_DIR", "./metis/workspace/browser-profile")).resolve())

    vault_backend: str = field(default_factory=lambda: _env("METIS_VAULT_BACKEND", "wincred_dpapi"))

    http_timeout_s: int = field(default_factory=lambda: _env_int("METIS_HTTP_TIMEOUT_S", 30))
    http_max_retries: int = field(default_factory=lambda: _env_int("METIS_HTTP_MAX_RETRIES", 2))

    search_provider_timeout_s: int = field(default_factory=lambda: _env_int("METIS_SEARCH_PROVIDER_TIMEOUT_S", 45))
    search_max_concurrency: int = field(default_factory=lambda: _env_int("METIS_SEARCH_MAX_CONCURRENCY", 6))
    search_max_retries: int = field(default_factory=lambda: _env_int("METIS_SEARCH_MAX_RETRIES", 2))

    download_max_bytes: int = field(default_factory=lambda: _env_int("METIS_DOWNLOAD_MAX_BYTES", 5 * 1024 * 1024 * 1024))
    download_chunk: int = field(default_factory=lambda: _env_int("METIS_DOWNLOAD_CHUNK", 1024 * 1024))

    fixture_server: str = field(default_factory=lambda: _env("METIS_FIXTURE_SERVER", "http://127.0.0.1:8310"))

    def ensure_dirs(self) -> None:
        from .paths import ensure_workspace_layout

        ensure_workspace_layout(self.workspace_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.browser_download_dir.mkdir(parents=True, exist_ok=True)


_SETTINGS: Settings | None = None


def get_settings() -> Settings:
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = Settings()
        if not _SETTINGS.db_url:
            _SETTINGS.db_url = f"sqlite:///{(_SETTINGS.workspace_dir / 'metis.db').as_posix()}"
    return _SETTINGS


def reset_settings() -> None:
    global _SETTINGS
    _SETTINGS = None
