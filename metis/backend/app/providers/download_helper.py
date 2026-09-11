"""AcquisitionDescriptor + unified download helper (P06-001/002, P06-005, P07-001..009).

Adapters must NOT manage the file lifecycle: they return an AcquisitionDescriptor
(or a list), and all byte transfer goes through stream_to_file() — streaming,
cancellable, checksum-aware, memory-bounded. Writing into raw/ is forbidden in
adapters; DownloadManager owns verify + atomic commit.
"""
from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel

from app.core.errors import MetisError
from app.core.logging import get_logger

log = get_logger("download_helper")


class AcquisitionDescriptor(BaseModel):
    url: str
    method: str = "GET"
    headers: dict[str, str] = {}
    filename: str
    expected_type: str | None = None  # e.g. "csv" | "zip" | "json"
    expected_size: int | None = None
    auth_context: dict[str, Any] = {}  # e.g. basic auth tuple data, bearer token ref (never the secret itself)
    license: str = "UNKNOWN"
    metadata: dict[str, Any] = {}


async def stream_to_file(
    client: httpx.AsyncClient,
    descriptor: AcquisitionDescriptor,
    dest_path,
    *,
    chunk_size: int = 1024 * 1024,
    max_bytes: int | None = None,
    on_progress=None,
    cancel_event=None,
) -> dict:
    """Stream descriptor.url → dest_path with progress + hard caps. Returns {path,size,sha256}.

    Memory-bounded: never materializes the whole body. Resumable when the server
    supports Range and a .partial from a previous attempt exists.
    """
    import hashlib
    from pathlib import Path

    from app.core.config import get_settings

    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    max_bytes = max_bytes or get_settings().download_max_bytes
    partial = dest.with_suffix(dest.suffix + ".partial")

    headers = dict(descriptor.headers)
    offset = 0
    resume = False
    if partial.exists():
        probe = client.build_request("HEAD", descriptor.url, headers=headers)
        head = await client.send(probe)
        accept_ranges = head.headers.get("Accept-Ranges", "").lower() == "bytes" or "content-range" in {k.lower() for k in head.headers}
        if accept_ranges:
            offset = partial.stat().st_size
            headers["Range"] = f"bytes={offset}-"
            resume = True

    mode = "ab" if resume else "wb"
    h = hashlib.sha256()
    if resume:
        with partial.open("rb") as pf:
            for block in iter(lambda: pf.read(1 << 20), b""):
                h.update(block)
        offset = partial.stat().st_size
    received = offset
    started = __import__("time").monotonic()

    async with client.stream(descriptor.method, descriptor.url, headers=headers) as resp:
        if resume and resp.status_code == 200:
            # server ignored Range → restart clean
            received, offset = 0, 0
            mode = "wb"
        elif resp.status_code not in (200, 206):
            raise MetisError("PROVIDER_HTTP_ERROR", f"download HTTP {resp.status_code}", details={"url": descriptor.url})
        declared = int(resp.headers.get("Content-Length") or 0)
        total = declared + offset if declared else None
        if total and descriptor.expected_size and abs(total - descriptor.expected_size) > max(1024, descriptor.expected_size * 0.01):
            raise MetisError("CHECKSUM_MISMATCH", f"declared size {total} != expected {descriptor.expected_size}")
        with partial.open(mode) as f:
            async for chunk in resp.aiter_bytes(chunk_size):
                if cancel_event is not None and cancel_event.is_set():
                    raise MetisError("DOWNLOAD_CANCELLED", "cancelled", retryable=False)
                received += len(chunk)
                if received > max_bytes:
                    raise MetisError("DOWNLOAD_TOO_LARGE", f"exceeds {max_bytes}")
                f.write(chunk)
                h.update(chunk)
                if on_progress:
                    elapsed = max(__import__("time").monotonic() - started, 1e-6)
                    on_progress(
                        {
                            "received": received,
                            "total": total,
                            "percent": round(received / total, 4) if total else None,
                            "speed_bps": round(received / elapsed),
                            "eta_s": round((total - received) / (received / elapsed)) if total and received else None,
                        }
                    )

    final_size = partial.stat().st_size
    if descriptor.expected_size and abs(final_size - descriptor.expected_size) > max(1024, descriptor.expected_size * 0.01):
        partial.unlink(missing_ok=True)
        raise MetisError("CHECKSUM_MISMATCH", f"downloaded {final_size} != expected {descriptor.expected_size}")
    import os

    os.replace(partial, dest)
    return {"path": str(dest), "size": final_size, "sha256": h.hexdigest()}
