"""SecretStore abstraction (P03-001) — the ONLY vault interface business code may use.

P03-003: import-safe on every OS; non-Windows raises VAULT_UNAVAILABLE at call time
(never plaintext fallback, never import crash).
"""
from __future__ import annotations

import sys
from abc import ABC, abstractmethod


class SecretStore(ABC):
    @abstractmethod
    def set_secret(self, key: str, value: str) -> None: ...

    @abstractmethod
    def get_secret(self, key: str) -> str: ...

    @abstractmethod
    def delete_secret(self, key: str) -> bool: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def list_keys(self) -> list[str]: ...


class UnsupportedPlatformStore(SecretStore):
    """Non-Windows placeholder: every operation fails loudly, nothing is ever written in cleartext."""

    def _fail(self) -> None:
        raise __import__("app.core.errors", fromlist=["MetisError"]).MetisError(
            "VAULT_UNAVAILABLE",
            f"no OS secret store on {sys.platform}; install/enable a backend (Windows Credential Manager / macOS Keychain / libsecret). Cleartext fallback is disabled by policy.",
        )

    def set_secret(self, key: str, value: str) -> None:
        self._fail()

    def get_secret(self, key: str) -> str:
        self._fail()
        raise AssertionError  # unreachable

    def delete_secret(self, key: str) -> bool:
        self._fail()
        raise AssertionError

    def exists(self, key: str) -> bool:
        return False  # nothing is ever stored without a backend

    def list_keys(self) -> list[str]:
        return []


def get_secret_store() -> SecretStore:
    """Returns the OS-backed store. Windows → DPAPI vault; others → loud unsupported."""
    if sys.platform == "win32":
        from app.auth.vault import get_vault

        return get_vault()
    return UnsupportedPlatformStore()
