"""SecretStore: Windows Credential Manager via DPAPI (CryptProtectData). No plaintext fallback.

Secrets never touch the database, logs, or git. Vault registers every secret value
with the log-redaction registry so it is masked everywhere automatically.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

from app.auth.secret_store import SecretStore
from app.core.errors import MetisError
from app.core.logging import get_logger
from app.core.paths import vault_dir

log = get_logger("vault")

_DOMAIN = "MetisData"

# 64-bit safe prototypes
if sys.platform == "win32":
    _crypt = ctypes.windll.crypt32
    _crypt.CryptProtectData.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
    _crypt.CryptProtectData.restype = wintypes.BOOL
    _crypt.CryptUnprotectData.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
    _crypt.CryptUnprotectData.restype = wintypes.BOOL
    _kernel32 = ctypes.windll.kernel32
    _kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    _kernel32.LocalFree.restype = wintypes.HLOCAL
else:  # non-Windows: import-safe; call raises VAULT_UNAVAILABLE (no plaintext fallback)
    def _crypt():  # noqa: F811 — accessed only via _dpapi_or_fail
        raise MetisError("VAULT_UNAVAILABLE", f"DPAPI unavailable on {sys.platform}")
    _kernel32 = None



class Vault(SecretStore):
    """key -> secret storage backed by Windows DPAPI (user scope, machine-bound)."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise MetisError("VAULT_UNAVAILABLE", f"DPAPI vault requires Windows, got {sys.platform}")
        self._blob_dir = vault_dir()
        self._blob_dir.mkdir(parents=True, exist_ok=True)
        (self._blob_dir / ".gitkeep").touch(exist_ok=True)

    # ---------- DPAPI ----------
    @staticmethod
    def _protect(data: bytes) -> bytes:
        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.c_void_p)]

        din = DATA_BLOB(len(data), ctypes.cast(ctypes.c_char_p(data), ctypes.c_void_p))
        dout = DATA_BLOB()
        ok = _crypt.CryptProtectData(ctypes.byref(din), "MetisData", None, None, None, 0, ctypes.byref(dout))
        if not ok:
            raise MetisError("VAULT_UNAVAILABLE", "CryptProtectData failed")
        try:
            return ctypes.string_at(dout.pbData, dout.cbData)
        finally:
            _kernel32.LocalFree(dout.pbData)

    @staticmethod
    def _unprotect(blob: bytes) -> bytes:
        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.c_void_p)]

        din = DATA_BLOB(len(blob), ctypes.cast(ctypes.c_char_p(blob), ctypes.c_void_p))
        dout = DATA_BLOB()
        ok = _crypt.CryptUnprotectData(ctypes.byref(din), None, None, None, None, 0, ctypes.byref(dout))
        if not ok:
            raise MetisError("VAULT_UNAVAILABLE", "CryptUnprotectData failed (wrong user or corrupted blob)")
        try:
            return ctypes.string_at(dout.pbData, dout.cbData)
        finally:
            _kernel32.LocalFree(dout.pbData)

    def _path(self, key: str) -> Path:
        safe = key.replace("/", "_").replace("\\", "_")
        return self._blob_dir / f"{safe}.dpapi"

    # ---------- API ----------
    def set_secret(self, key: str, value: str) -> None:
        if not value:
            raise MetisError("VAULT_UNAVAILABLE", "empty secret value")
        blob = self._protect(value.encode("utf-8"))
        self._path(key).write_bytes(blob)
        from app.core.logging import register_secret

        register_secret(value)  # masked in every log/error from now on
        log.info_ctx("secret stored", key=key)

    def get_secret(self, key: str) -> str:
        p = self._path(key)
        if not p.exists():
            raise MetisError("NOT_FOUND", f"secret '{key}' not in vault")
        return self._unprotect(p.read_bytes()).decode("utf-8")

    def delete_secret(self, key: str) -> bool:
        p = self._path(key)
        if p.exists():
            p.unlink()
            log.info_ctx("secret deleted", key=key)
            return True
        return False

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def list_keys(self) -> list[str]:
        return [p.name[: -len(".dpapi")] for p in self._blob_dir.glob("*.dpapi")]


_VAULT: Vault | None = None


def get_vault() -> Vault:
    global _VAULT
    if _VAULT is None:
        _VAULT = Vault()
    return _VAULT


def reset_vault() -> None:
    global _VAULT
    _VAULT = None
