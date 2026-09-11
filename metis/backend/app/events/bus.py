"""Global UI event bus: modules publish, WS clients subscribe."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.db.repository import REPO

_SUBSCRIBERS: list[asyncio.Queue] = []


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=500)
    _SUBSCRIBERS.append(q)
    return q


def publish(kind: str, severity: str = "INFO", task_id: str | None = None, provider_id: str | None = None, payload: dict | None = None) -> None:
    event = {
        "ts": datetime.now(UTC).isoformat(),
        "kind": kind,
        "severity": severity,
        "task_id": task_id,
        "provider_id": provider_id,
        "payload": payload or {},
    }
    REPO.add_ui_event(kind, severity, task_id, provider_id, payload)
    for q in _SUBSCRIBERS:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass
