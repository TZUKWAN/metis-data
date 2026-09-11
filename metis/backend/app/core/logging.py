"""Secret redaction registry + structured JSON logging (PRD §31, A10).

Every value registered here is masked in ALL log output. The Vault registers
every secret it stores. Pattern-based rules additionally mask password=/token=/
api_key=/cookie=/Authorization=/otp= style assignments.
"""
from __future__ import annotations

import json
import logging
import re
import sys
import threading
from datetime import UTC, datetime

_LOCK = threading.Lock()
_SECRET_VALUES: set[str] = set()

# Attribute-name based patterns (case-insensitive): password=xxx, "api_key": "xxx"
_PATTERNS = [
    re.compile(r"(?i)(password\s*[=:]\s*)(\"?[^\s\"',;)&]+)"),
    re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)(\"?[^\s\"',;)&]+)"),
    re.compile(r"(?i)(access[_-]?token\s*[=:]\s*)(\"?[^\s\"',;)&]+)"),
    re.compile(r"(?i)(refresh[_-]?token\s*[=:]\s*)(\"?[^\s\"',;)&]+)"),
    re.compile(r"(?i)(authorization\s*[=:]\s*)(\"?[^\s\"',;)&]+)"),
    re.compile(r"(?i)(cookie\s*[=:]\s*)(\"?[^\s\"',;)&]+)"),
    re.compile(r"(?i)(\botp\s*[=:]\s*)(\"?[^\s\"',;)&]+)"),
    re.compile(r"(\"(?:password|api_?key|access_?token|refresh_?token|authorization|cookie|otp)\"\s*:\s*\")([^\"]+)"),
]


def register_secret(value: str) -> None:
    """Vault calls this for every stored secret so it is masked everywhere."""
    if not value or len(value) < 3:
        return
    with _LOCK:
        _SECRET_VALUES.add(value)


def clear_registered_secrets() -> None:
    with _LOCK:
        _SECRET_VALUES.clear()


def redact(text: str) -> str:
    if not text:
        return text
    with _LOCK:
        for value in _SECRET_VALUES:
            if value in text:
                text = text.replace(value, "***MASKED***")
    for pattern in _PATTERNS:
        text = pattern.sub(lambda m: f"{m.group(1)}***MASKED***", text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        try:
            # format first (args may carry %d etc.), then redact the final message
            record.msg = redact(str(record.getMessage()))
            record.args = ()
        except Exception:
            pass
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(str(record.getMessage())),
        }
        extra = getattr(record, "ctx", None)
        if isinstance(extra, dict):
            payload["ctx"] = {k: redact(str(v)) for k, v in extra.items()}
        if record.exc_info and record.exc_info[0] is not None:
            payload["exception"] = redact(self.formatException(record.exc_info))[-2000:]
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactingFilter())
    root.addHandler(handler)
    # Route uvicorn through the same formatter
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True


class _LoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):  # noqa: ANN001, ANN202
        # redact at emit-source so any handler (incl. test capture) sees masked text
        return redact(str(msg)), kwargs

    def ctx(self, level: int, message: str, **context) -> None:
        # redact at the adapter level so every handler (incl. test capture) sees masked text
        self.logger.log(level, redact(str(message)), extra={"ctx": {k: redact(str(v)) for k, v in context.items()}})

    def info_ctx(self, message: str, **context) -> None:
        self.ctx(logging.INFO, message, **context)

    def warning_ctx(self, message: str, **context) -> None:
        self.ctx(logging.WARNING, message, **context)

    def error_ctx(self, message: str, **context) -> None:
        self.ctx(logging.ERROR, message, **context)

    def debug_ctx(self, message: str, **context) -> None:
        self.ctx(logging.DEBUG, message, **context)


def get_logger(name: str) -> _LoggerAdapter:
    return _LoggerAdapter(logging.getLogger(name), {})
