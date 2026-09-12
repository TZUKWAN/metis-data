"""Download & Raw management (P11, A14–A19, A36).

Hard rules enforced here:
- no download without a DownloadJob (A14) — raw http/browser download entrypoints
  require `job=` and raise DOWNLOAD_JOB_REQUIRED otherwise;
- streaming to .partial + atomic rename; partial never enters raw/;
- content sniffing rejects HTML/login/error pages masquerading as data (A17);
- safe extraction: zip-slip, bomb ratio, file count, total size, workspace escape (A18);
- raw immutable: writes into raw are blocked; artifacts commit with SHA256 (A19);
- cancellation stops new network reads and cleans partial files (A36).
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import zipfile
from collections.abc import Callable
from pathlib import Path

from app.core import paths
from app.core.config import get_settings
from app.core.errors import MetisError
from app.core.logging import get_logger
from app.db.repository import REPO
from app.domain.enums import DownloadJobStatus
from app.domain.schemas import DatasetArtifact, DownloadJob
from app.providers.adapters.common import looks_like_html

log = get_logger("downloads")

MAX_ARCHIVE_FILES = 20000
MAX_BOMB_RATIO = 200
MAX_EXTRACT_TOTAL = 8 * 1024 * 1024 * 1024  # 8 GiB


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


class RawWriteBlocked(MetisError):
    def __init__(self, path: Path) -> None:
        super().__init__("RAW_WRITE_BLOCKED", f"write into immutable raw/ is blocked: {path}", details={"path": str(path)})


def guard_no_raw_write(path: Path) -> Path:
    """Every write path in downloads/transforms funnels through this check (A19)."""
    if paths.is_under_raw(path):
        raise RawWriteBlocked(path)
    return path


class DownloadManager:
    def __init__(self) -> None:
        self._cancel_flags: dict[str, asyncio.Event] = {}

    # ---------------- job gate (A14) ----------------
    def create_job(
        self,
        provider_id: str,
        dataset_ref: str,
        source_url: str,
        *,
        dataset_title: str = "",
        version: str | None = None,
        access_mode: str = "UNKNOWN",
        license: str = "UNKNOWN",
        expected_files: list[str] | None = None,
    ) -> DownloadJob:
        job = DownloadJob(
            provider_id=provider_id,
            dataset_ref=dataset_ref,
            dataset_title=dataset_title,
            source_url=source_url,
            version=version,
            access_mode=access_mode,
            license=license,
            expected_files=expected_files or [],
            status=DownloadJobStatus.CREATED,
        )
        REPO.save_download_job(job)
        REPO.add_ui_event("download.job_created", provider_id=provider_id, payload={"download_job_id": job.download_job_id, "source_url": source_url})
        return job

    @staticmethod
    def _require_job(job: DownloadJob | None) -> DownloadJob:
        if job is None:
            raise MetisError("DOWNLOAD_JOB_REQUIRED", "refusing to download without a DownloadJob (policy: every download must be auditable)")
        return job

    def cancel(self, job_id: str) -> None:
        flag = self._cancel_flags.get(job_id)
        if flag:
            flag.set()
        job = REPO.get_download_job(job_id)
        if job and job["status"] in (DownloadJobStatus.CREATED, DownloadJobStatus.RUNNING, DownloadJobStatus.VERIFYING):
            job["status"] = DownloadJobStatus.CANCELLED
            REPO.save_download_job(job)
            partials = list(paths.downloads_tmp_dir().glob(f"{job_id}*"))
            for p in partials:
                try:
                    p.unlink()
                except OSError:
                    pass
            log.info_ctx("download cancelled", job_id=job_id, partials_removed=len(partials))

    # ---------------- streaming HTTP download (A15) ----------------
    async def http_download(
        self,
        url: str,
        *,
        job: DownloadJob | None = None,
        suggested_name: str | None = None,
        on_progress: Callable[[int, int | None], None] | None = None,
        max_bytes: int | None = None,
    ) -> tuple[Path, dict]:
        job = self._require_job(job)
        if not isinstance(job, dict):
            job = REPO.get_download_job(job.download_job_id)
            if job is None:
                raise MetisError("DOWNLOAD_JOB_REQUIRED", "DownloadJob not persisted")
        cfg = get_settings()
        max_bytes = max_bytes or cfg.download_max_bytes
        cancel = self._cancel_flags.setdefault(job["download_job_id"], asyncio.Event())

        job["status"] = DownloadJobStatus.RUNNING
        job["started_at"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        REPO.save_download_job(job)

        import httpx

        tmp_dir = paths.downloads_tmp_dir()
        name = suggested_name or url.rsplit("/", 1)[-1].split("?")[0] or "download.bin"
        partial = guard_no_raw_write(tmp_dir / f"{job['download_job_id']}_{name}.partial")
        final_tmp = guard_no_raw_write(tmp_dir / f"{job['download_job_id']}_{name}")

        received = 0
        try:
            async with httpx.AsyncClient(timeout=cfg.http_timeout_s, follow_redirects=True) as client:
                async with client.stream("GET", url) as resp:
                    if resp.status_code >= 400:
                        raise MetisError("PROVIDER_HTTP_ERROR", f"download HTTP {resp.status_code}", provider_id=job.get("provider_id"))
                    total = int(resp.headers.get("Content-Length") or 0) or None
                    job["total_bytes"] = total
                    with partial.open("wb") as f:
                        async for chunk in resp.aiter_bytes(cfg.download_chunk):
                            if cancel.is_set():
                                raise MetisError("DOWNLOAD_CANCELLED", "download cancelled by user", retryable=False)
                            received += len(chunk)
                            if received > max_bytes:
                                raise MetisError("DOWNLOAD_TOO_LARGE", f"download exceeds limit {max_bytes}")
                            f.write(chunk)
                            if on_progress and (received % (cfg.download_chunk * 8) < len(chunk)):
                                on_progress(received, total)
        except MetisError:
            partial.unlink(missing_ok=True)
            job["status"] = DownloadJobStatus.FAILED if not cancel.is_set() else DownloadJobStatus.CANCELLED
            job["bytes_downloaded"] = received
            REPO.save_download_job(job)
            raise
        except Exception as e:  # noqa: BLE001
            partial.unlink(missing_ok=True)
            job["status"] = DownloadJobStatus.FAILED
            job["error_code"] = "DOWNLOAD_FAILED"
            job["error_message"] = str(e)[:300]
            REPO.save_download_job(job)
            raise MetisError("DOWNLOAD_FAILED", f"network interrupted: {e}", retryable=True) from e

        # atomic promote: .partial -> complete tmp file
        os.replace(partial, final_tmp)
        info = await self._verify_and_commit(final_tmp, job, received)
        return final_tmp, info

    # ---------------- verification + raw commit (A15/A17/A19) ----------------
    async def _verify_and_commit(self, file_path: Path, job: dict, received: int) -> dict:
        job["status"] = DownloadJobStatus.VERIFYING
        REPO.save_download_job(job)

        size = file_path.stat().st_size
        # memory fix (Phase D): sniff only the head of the file — never materialize the
        # whole (potentially multi-GB) body in memory just for content inspection
        with file_path.open("rb") as fh:
            content = fh.read(65536)
        # content sniffing (A17): HTML masquerading as data file
        suffix = file_path.suffix.lower()
        if suffix in (".csv", ".tsv", ".zip", ".xlsx", ".parquet", ".dta", ".sav", ".json") and looks_like_html(content):
            job["status"] = DownloadJobStatus.INVALID_CONTENT
            job["error_code"] = "INVALID_DOWNLOAD_CONTENT"
            job["error_message"] = "downloaded file looks like an HTML page (login/error), not the claimed data format"
            REPO.save_download_job(job)
            raise MetisError("INVALID_DOWNLOAD_CONTENT", job["error_message"], provider_id=job.get("provider_id"))
        if suffix == ".zip" and content[:2] != b"PK":
            job["status"] = DownloadJobStatus.INVALID_CONTENT
            job["error_code"] = "INVALID_DOWNLOAD_CONTENT"
            REPO.save_download_job(job)
            raise MetisError("INVALID_DOWNLOAD_CONTENT", "zip magic bytes missing", provider_id=job.get("provider_id"))

        checksum = sha256_file(file_path)
        # raw commit (atomic rename into raw tree)
        raw_dir = paths.raw_dataset_dir(job.get("provider_id", "unknown"), job.get("dataset_ref", "unknown"), job.get("version") or "v1")
        raw_path = raw_dir / file_path.name
        if raw_path.exists() and sha256_file(raw_path) == checksum:
            file_path.unlink(missing_ok=True)  # content-dedup, logical ref kept (PRD §17)
            raw_path = raw_path
        else:
            try:
                os.replace(file_path, raw_path)
            except OSError:
                # cross-volume rename is not atomic on Windows — copy+unlink
                import shutil

                shutil.copy2(file_path, raw_path)
                file_path.unlink(missing_ok=True)

        artifact = DatasetArtifact(
            download_job_id=job["download_job_id"],
            provider_id=job.get("provider_id", ""),
            dataset_ref=job.get("dataset_ref", ""),
            dataset_title=job.get("dataset_title", ""),
            version=job.get("version"),
            raw_path=str(raw_path.relative_to(paths.raw_root())),
            checksum_sha256=checksum,
            size_bytes=size,
            file_format=suffix.lstrip(".").upper() or "UNKNOWN",
            license=job.get("license", "UNKNOWN"),
            source_url=job.get("source_url", ""),
            status="REGISTERED",
        )
        REPO.save_artifact(artifact)

        job["status"] = DownloadJobStatus.COMPLETED
        job["completed_at"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        job["bytes_downloaded"] = received
        job["files"] = (job.get("files") or []) + [{"path": artifact.raw_path, "sha256": checksum, "size": size, "format": artifact.file_format, "artifact_id": artifact.artifact_id}]
        REPO.save_download_job(job)
        REPO.add_ui_event("download.completed", provider_id=job.get("provider_id"), payload={"download_job_id": job["download_job_id"], "sha256": checksum, "size": size})
        return {"artifact_id": artifact.artifact_id, "sha256": checksum, "size": size, "raw_path": artifact.raw_path, "format": artifact.file_format}

    # ---------------- browser download binding (A16) ----------------
    def attach_to_browser_session(self, job: DownloadJob, session) -> None:
        job = self._require_job(job)
        if not isinstance(job, dict):
            job = REPO.get_download_job(job.download_job_id)
            assert job
        session.download_job_id = job["download_job_id"]
        session.download_dir = guard_no_raw_write(paths.downloads_tmp_dir() / job["download_job_id"])
        session.download_dir.mkdir(parents=True, exist_ok=True)

    async def collect_browser_downloads(self, job: DownloadJob, session) -> list[dict]:
        """Wait for the session's captured downloads, verify, commit to raw under this job."""
        job = self._require_job(job)
        if not isinstance(job, dict):
            job = REPO.get_download_job(job.download_job_id)
            assert job
        results = []
        for dl in list(session.downloads):
            if dl.get("download_job_id") != job["download_job_id"]:
                continue
            p = Path(dl["path"])
            if not p.exists() or p.stat().st_size == 0:
                job["status"] = DownloadJobStatus.FAILED
                job["error_code"] = "INVALID_DOWNLOAD_CONTENT"
                job["error_message"] = "page showed success but no real file was captured; refusing to mark complete (A16)"
                REPO.save_download_job(job)
                raise MetisError("INVALID_DOWNLOAD_CONTENT", job["error_message"])
            results.append(await self._verify_and_commit(p, job, p.stat().st_size))
        job["browser_downloads"] = results
        REPO.save_download_job(job)
        return results

    # ---------------- safe extraction (A18) ----------------
    def safe_extract(self, archive_path: Path, dest_dir: Path, max_files: int = MAX_ARCHIVE_FILES) -> list[Path]:
        dest_dir = guard_no_raw_write(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        with open(archive_path, "rb") as fh:
            magic = fh.read(4)
        if magic[:2] != b"PK":
            raise MetisError("PARSE_UNSUPPORTED_FORMAT", f"archive type {archive_path.suffix} not supported for safe extraction")
        out: list[Path] = []
        with zipfile.ZipFile(archive_path) as z:
            names = z.namelist()
            if len(names) > max_files:
                raise MetisError("ARCHIVE_UNSAFE", f"archive has {len(names)} entries > limit {max_files}")
            total_uncompressed = sum(i.file_size for i in z.infolist())
            total_compressed = sum(i.compress_size for i in z.infolist()) or 1
            if total_uncompressed / total_compressed > MAX_BOMB_RATIO and total_uncompressed > 256 * 1024 * 1024:
                raise MetisError("ARCHIVE_UNSAFE", f"compression bomb suspected: ratio {total_uncompressed/total_compressed:.0f}")
            if total_uncompressed > MAX_EXTRACT_TOTAL:
                raise MetisError("ARCHIVE_UNSAFE", f"uncompressed size {total_uncompressed} exceeds cap")
            dest_root = dest_dir.resolve()
            for info in names:
                target = (dest_dir / info).resolve()
                if not (target == dest_root or dest_root in target.parents):
                    raise MetisError("ARCHIVE_UNSAFE", f"zip-slip attempt detected: {info}")
            for info in names:
                target = (dest_dir / info).resolve()
                if info.endswith("/"):
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                out.append(target)
        if not out:
            raise MetisError("ARCHIVE_UNSAFE", "archive extracted zero files")
        return out

    # ---------------- raw immutability verification (A19) ----------------
    def raw_checksum_snapshot(self) -> dict[str, str]:
        snap = {}
        for p in paths.raw_root().rglob("*"):
            if p.is_file() and p.name != paths.RAW_IMMUTABLE_NOTICE:
                rel = str(p.relative_to(paths.raw_root()))
                snap[rel] = sha256_file(p)
        return snap

    def verify_raw_unchanged(self, before: dict[str, str]) -> bool:
        after = self.raw_checksum_snapshot()
        changed = [k for k, v in before.items() if after.get(k) != v]
        if changed:
            raise MetisError("RAW_WRITE_BLOCKED", f"raw files changed during pipeline: {changed[:5]}")
        return True

    # ---------------- quota (P11-010) ----------------
    def check_disk_quota(self, needed_bytes: int) -> bool:
        usage = shutil.disk_usage(paths.workspace_root())
        if usage.free < needed_bytes * 2:
            raise MetisError("DOWNLOAD_FAILED", f"insufficient disk space: need {needed_bytes*2}, free {usage.free}", retryable=True)
        return True


MANAGER = DownloadManager()
