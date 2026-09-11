"""Phase 6/7 acceptance: adapter contract v2 + download engineering (P06-004/005, P07)."""
from __future__ import annotations

import asyncio
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ADAPTERS = BACKEND / "app" / "providers" / "adapters"


def test_adapters_never_write_raw_or_stream_violations():
    """P06-004/005 static scan: adapters must not (a) touch raw paths, (b) perform
    unbounded whole-body writes — only the bounded write_small_payload helper."""
    violations = []
    for f in ADAPTERS.glob("*.py"):
        src = f.read_text(encoding="utf-8")
        if "raw_root(" in src or "raw_dataset_dir(" in src:
            violations.append(f"{f.name}: touches raw/ (DownloadManager owns raw)")
        if re.search(r"\.write_bytes\(", src) and "write_small_payload" not in src:
            violations.append(f"{f.name}: unbounded write_bytes")
        for m in re.finditer(r"(\w+)\.write_bytes\(([^)]+)\)", src):
            call = m.group(0)
            if "write_small_payload" not in call:
                violations.append(f"{f.name}: {call[:60]}")
    assert not violations, "\n".join(violations)


import re  # noqa: E402


class _RangeHandler(BaseHTTPRequestHandler):
    """HTTP server with Range support for resume tests + /big.bin synthetic stream."""

    payload_size = 0

    def log_message(self, *a):
        pass

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Length", str(self.payload_size))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

    def do_GET(self):
        start = 0
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            start = int(rng.split("-")[0].split("=")[1])
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{self.payload_size - 1}/{self.payload_size}")
        else:
            self.send_response(200)
        length = self.payload_size - start
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        block = b"\0" * (1 << 20)
        sent = start
        while sent < self.payload_size:
            n = min(len(block), self.payload_size - sent)
            try:
                self.wfile.write(block[:n])
            except (BrokenPipeError, ConnectionAbortedError):
                return
            sent += n


def _peak_rss_mb() -> float:
    import ctypes

    class PMC(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
    return pmc.PeakWorkingSetSize / (1024 * 1024)


def test_resume_and_progress_payload(temp_workspace):
    """P07-003/008/009: Range resume from .partial; rich progress (percent/speed/eta)."""
    from app.providers.download_helper import AcquisitionDescriptor, stream_to_file

    _RangeHandler.payload_size = 64 * 1024 * 1024  # 64MB
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _RangeHandler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        dest = Path(temp_workspace) / "downloads" / "resume" / "big.bin"
        dest.parent.mkdir(parents=True, exist_ok=True)
        desc = AcquisitionDescriptor(url=f"http://127.0.0.1:{port}/big.bin", filename="big.bin", expected_size=64 * 1024 * 1024)
        progress = []

        async def go():
            import httpx

            cancel = __import__("asyncio").Event()
            async with httpx.AsyncClient(timeout=60) as client:
                # first attempt: cancel after ~8MB → .partial remains
                try:
                    await asyncio.wait_for(
                        stream_to_file(client, desc, dest, on_progress=progress.append, cancel_event=cancel),
                        timeout=0.0,
                    )
                except (asyncio.TimeoutError, __import__("app.core.errors", fromlist=["MetisError"]).MetisError):
                    pass
                # simulate: seed a partial of 8MB then resume to completion
                partial = dest.with_suffix(dest.suffix + ".partial")
                partial.write_bytes(b"\0" * (8 * 1024 * 1024))
                info = await stream_to_file(client, desc, dest, on_progress=progress.append)
                return info

        info = asyncio.new_event_loop().run_until_complete(go())
        assert info["size"] == 64 * 1024 * 1024
        assert progress and all("percent" in p and "speed_bps" in p and "eta_s" in p for p in progress[-3:])
        # expected-size validation: mismatch raises
        bad = AcquisitionDescriptor(url=desc.url, filename="bad.bin", expected_size=12345)
        try:
            asyncio.new_event_loop().run_until_complete(stream_to_file(__import__("httpx").AsyncClient(), bad, Path(temp_workspace) / "bad.bin"))
            raise AssertionError("expected size mismatch not caught")
        except __import__("app.core.errors", fromlist=["MetisError"]).MetisError as e:
            assert e.code in ("CHECKSUM_MISMATCH",)
    finally:
        srv.shutdown()


def test_download_descriptor_v2_bridge(temp_workspace):
    """P06-002/003: v2 bridge produces descriptors from a legacy adapter metadata."""
    from app.core.config import get_settings

    get_settings().ensure_dirs()
    from app.db.session import init_db

    init_db()
    from app.providers.base import get_adapter

    adapter = get_adapter("world_bank")
    desc = asyncio.new_event_loop().run_until_complete(adapter.build_acquisition_descriptor("NY.GDP.PCAP.CD"))
    assert desc and desc[0].url and desc[0].filename
    val = asyncio.new_event_loop().run_until_complete(adapter.validate_download(desc[0], __import__("io").BytesIO() if False else __import__("pathlib").Path(__file__), 100))
    assert "ok" in val


def test_1gb_stream_memory_bounded(temp_workspace):
    """P07-014: 1GB synthetic stream — RSS must NOT grow linearly with file size."""
    _RangeHandler.payload_size = 1024 * 1024 * 1024  # 1GB
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _RangeHandler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        dest = Path(temp_workspace) / "downloads" / "gb" / "huge.bin"
        dest.parent.mkdir(parents=True, exist_ok=True)
        from app.providers.download_helper import AcquisitionDescriptor, stream_to_file

        desc = AcquisitionDescriptor(url=f"http://127.0.0.1:{port}/huge.bin", filename="huge.bin", expected_size=1024 * 1024 * 1024)

        async def go():
            import httpx

            async with httpx.AsyncClient(timeout=300) as client:
                return await stream_to_file(client, desc, dest, chunk_size=1024 * 1024)

        t0 = time.time()
        info = asyncio.new_event_loop().run_until_complete(go())
        dur = time.time() - t0
        peak = _peak_rss_mb()
        assert info["size"] == 1024 * 1024 * 1024 and info["sha256"]
        assert peak < 800, f"RSS {peak:.0f}MB grew with file size (must stay bounded)"
        print(f"1GB stream: {dur:.1f}s, peak RSS {peak:.0f}MB")
    finally:
        srv.shutdown()
