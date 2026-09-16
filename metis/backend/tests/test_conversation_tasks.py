"""Conversation TaskManager unit tests: concurrency gate + failure convergence."""
from __future__ import annotations

import asyncio

import pytest


@pytest.fixture()
def fresh_manager(temp_workspace, monkeypatch):
    monkeypatch.setenv("METIS_CONVERSATION_MAX_CONCURRENCY", "1")
    from app.agent.conversation_tasks import ConversationTaskManager

    return ConversationTaskManager()


def test_concurrency_gate_queues_and_serializes(fresh_manager):
    """MAX_CONCURRENT=1 → the second pipeline waits (QUEUED persisted) and runs after."""
    from app.ui.conversation_store import STORE

    running: list[str] = []
    order: list[str] = []

    async def pipeline(name: str) -> None:
        running.append(name)
        order.append(name)
        await asyncio.sleep(0.15)
        running.remove(name)

    async def main():
        cid = STORE.create_conversation("c")
        t1 = STORE.create_task(cid, "x")
        t2 = STORE.create_task(cid, "x")
        fresh_manager.start(t1, pipeline("p1"))
        for _ in range(200):  # p1 actually holds the only slot (timing-robust)
            if "p1" in running:
                break
            await asyncio.sleep(0.01)
        fresh_manager.start(t2, pipeline("p2"))
        await asyncio.sleep(0.02)  # let the supervisor's first step observe the full slot
        state2 = STORE.get_task(t2)
        assert state2["state"] == "QUEUED", f"second task should be QUEUED, got {state2['state']}"
        assert state2["stage_label"].startswith("排队中")
        for tid in (t1, t2):
            for _ in range(300):
                t = fresh_manager._tasks.get(tid)
                if t is None or t.done():
                    break
                await asyncio.sleep(0.02)
        assert order == ["p1", "p2"], f"serial execution expected, got {order}"

    asyncio.run(main())


def test_failure_convergence_persists_failed_and_copy(fresh_manager):
    """Any pipeline exception → task FAILED + a friendly assistant message."""
    from app.ui.conversation_store import STORE

    async def boom() -> None:
        raise RuntimeError("exploded with key 1")

    async def main():
        cid = STORE.create_conversation("c")
        tid = STORE.create_task(cid, "x")
        fresh_manager.start(tid, boom())
        t = fresh_manager._tasks[tid]
        for _ in range(100):
            if t.done():
                break
            await asyncio.sleep(0.02)
        task = STORE.get_task(tid)
        assert task["state"] == "FAILED"
        assert task["error_code"] == "PIPELINE_ERROR"
        msgs = STORE.list_messages(cid)
        assert any(m["role"] == "assistant" for m in msgs), "failure copy missing"
        assert all("Traceback" not in m["content"] for m in msgs)

    asyncio.run(main())
