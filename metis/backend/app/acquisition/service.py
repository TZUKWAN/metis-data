"""AcquisitionService (Phase E/F): the single download path — descriptor (v2) first, legacy fallback.

Every byte transfer goes through app.providers.download_helper.stream_to_file (memory-bounded,
resumable) or the adapter's legacy acquire_dataset (compatibility layer for pre-v2 adapters).
Commit into raw/ is exclusively DownloadManager._verify_and_commit (A15/A17/A19) — no adapter
and no service code writes into raw/ directly.
"""
from __future__ import annotations

from pathlib import Path

import httpx

from app.core import paths
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.repository import REPO
from app.downloads.service import MANAGER
from app.providers.base import get_adapter  # module-level import: tests monkeypatch app.acquisition.service.get_adapter
from app.providers.download_helper import AcquisitionDescriptor, stream_to_file

log = get_logger("acquisition")


class AcquisitionService:
    async def acquire(self, access_job: dict, download_job: dict, staging_dir: Path) -> list[str]:
        """Acquire all files for `download_job` into staging, then commit each via MANAGER.

        Order of preference:
        1. v2 descriptor path: adapter.build_acquisition_descriptor(ref, ctx) → direct URL(s)
           streamed to staging via stream_to_file (httpx; cookies injected when the access
           context carries resolved cookie values);
        2. legacy fallback: adapter.acquire_dataset(ref, staging_dir, ctx) — compatibility
           layer, emits UI event "acquisition.legacy_fallback".

        Returns the list of committed file paths (inside raw/). Raises when nothing could
        be acquired.
        """
        provider_id = str(access_job.get("provider_id") or download_job.get("provider_id") or "")
        dataset_ref = str(download_job.get("dataset_ref") or access_job.get("candidate_id") or "")
        adapter = get_adapter(provider_id)
        staging_dir = Path(staging_dir)
        staging_dir.mkdir(parents=True, exist_ok=True)

        auth_ctx = access_job.get("access_context") or {}
        if hasattr(auth_ctx, "model_dump"):
            auth_ctx = auth_ctx.model_dump()
        # Resolved cookie VALUES may only arrive transiently here (bridged upstream from a live
        # browser session); AuthorizedAccessContext itself stores only names/counts + vault refs.
        cookies = dict(auth_ctx.get("cookies") or {})
        headers = dict(auth_ctx.get("headers") or {})

        committed: list[str] = []
        v2_error: Exception | None = None

        descriptors: list[AcquisitionDescriptor] = []
        try:
            desc = await adapter.build_acquisition_descriptor(dataset_ref, dict(auth_ctx))
            descriptors = list(desc) if isinstance(desc, list) else [desc]
        except Exception as e:  # noqa: BLE001 - any v2 failure falls through to legacy
            v2_error = e
            descriptors = []
            log.info_ctx("descriptor build failed", provider_id=provider_id, error=str(e)[:160])

        if descriptors:
            try:
                cfg = get_settings()
                for d in descriptors:
                    if not d.url:
                        raise ValueError("descriptor has no direct url")
                    dest = staging_dir / d.filename
                    async with httpx.AsyncClient(
                        timeout=cfg.http_timeout_s,
                        follow_redirects=True,
                        cookies=cookies or None,
                        headers=headers or None,
                    ) as client:
                        result = await stream_to_file(client, d, dest)
                    size = int(result.get("size") or Path(dest).stat().st_size)
                    info = await MANAGER._verify_and_commit(Path(dest), download_job, size)
                    committed.append(_committed_path(info, dest))
            except Exception as e:  # noqa: BLE001 - partial descriptor success still allows legacy retry
                v2_error = e
                log.info_ctx("descriptor acquisition failed", provider_id=provider_id, error=str(e)[:160])

        if not committed:
            # legacy 兼容层: adapters predating the v2 descriptor contract download by themselves.
            REPO.add_ui_event(
                "acquisition.legacy_fallback",
                "WARNING",
                task_id=download_job.get("download_job_id"),
                provider_id=provider_id or None,
                payload={"reason": str(v2_error)[:200] if v2_error else "no descriptors produced", "dataset_ref": dataset_ref},
            )
            legacy_files = await adapter.acquire_dataset(dataset_ref, staging_dir, dict(auth_ctx))
            for f in legacy_files or []:
                p = Path(f)
                info = await MANAGER._verify_and_commit(p, download_job, p.stat().st_size)
                committed.append(_committed_path(info, p))

        if not committed:
            from app.core.errors import MetisError

            raise MetisError(
                "ACQUISITION_FAILED",
                f"no files acquired for {provider_id}/{dataset_ref}",
                provider_id=provider_id or None,
            )
        log.info_ctx("acquisition committed", provider_id=provider_id, files=len(committed), dataset_ref=dataset_ref)
        return committed


def _committed_path(info: dict, staged: Path) -> str:
    """Absolute path of the committed file (raw wins; staging path as defensive fallback)."""
    raw_rel = info.get("raw_path")
    if raw_rel:
        return str(paths.raw_root() / raw_rel)
    return str(staged)


ACQUISITION = AcquisitionService()
