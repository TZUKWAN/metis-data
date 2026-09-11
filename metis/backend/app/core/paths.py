"""Workspace path规范 (PRD §17).

Layout:
  workspace/
    raw/<provider>/<dataset_id>/<version>/     # immutable
    intermediate/<build_id>/                    # transform outputs
    final/<build_id>/                           # final package
    downloads/                                  # .partial staging
    vault/                                      # DPAPI blobs (git-ignored)
    logs/
"""
from __future__ import annotations

from pathlib import Path

from .config import get_settings

RAW_IMMUTABLE_NOTICE = ".raw_immutable"


def workspace_root() -> Path:
    root = get_settings().workspace_dir
    root.mkdir(parents=True, exist_ok=True)
    return root


def ensure_workspace_layout(root: Path) -> None:
    for sub in ("raw", "intermediate", "final", "downloads", "vault", "logs", "tmp"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    marker = root / "raw" / RAW_IMMUTABLE_NOTICE
    if not marker.exists():
        marker.write_text(
            "raw/ is immutable. Transform outputs go to intermediate/, final outputs to final/.\n",
            encoding="utf-8",
        )


def raw_root() -> Path:
    p = workspace_root() / "raw"
    p.mkdir(parents=True, exist_ok=True)
    return p


def raw_dataset_dir(provider_id: str, dataset_id: str, version: str = "v1") -> Path:
    safe = lambda s: "".join(c if c.isalnum() or c in "-_." else "_" for c in s)  # noqa: E731
    p = raw_root() / safe(provider_id) / safe(dataset_id) / safe(version)
    p.mkdir(parents=True, exist_ok=True)
    return p


def intermediate_dir(build_id: str) -> Path:
    p = workspace_root() / "intermediate" / build_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def final_dir(build_id: str) -> Path:
    p = workspace_root() / "final" / build_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def downloads_tmp_dir() -> Path:
    p = workspace_root() / "downloads"
    p.mkdir(parents=True, exist_ok=True)
    return p


def vault_dir() -> Path:
    p = workspace_root() / "vault"
    p.mkdir(parents=True, exist_ok=True)
    return p


def is_under_raw(path: Path) -> bool:
    """True if path is inside the raw tree (write-guard target)."""
    try:
        path.resolve().relative_to(raw_root().resolve())
        return True
    except ValueError:
        return False
