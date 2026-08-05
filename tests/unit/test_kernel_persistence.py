"""Unit tests for deepened R1 Cognitive Kernel persistence and resume."""

from __future__ import annotations

from pathlib import Path

import pytest

from gaia.core.event_bus import EventDomain
from gaia.core.runtime import create_runtime
from gaia.kernel.context_manager import ContextManager
from gaia.kernel.goal_manager import GoalStatus
from gaia.kernel.store import KernelEvent, KernelStore


def test_kernel_store_schema_and_status(tmp_path: Path) -> None:
    store = KernelStore(tmp_path / "kernel.sqlite3")
    assert store.schema_version() == 1
    assert store.status()["durable"] is True
    assert store.status()["goal_count"] == 0
    store.close()


@pytest.mark.asyncio
async def test_kernel_persists_goal_context_budget_and_events(tmp_path: Path) -> None:
    db_path = tmp_path / "kernel.sqlite3"
    runtime = create_runtime(kernel_db_path=db_path)
    result = await runtime.kernel.run(
        "Persist this kernel run",
        "session-persist",
        ["reasoning"],
    )
    goal_id = result.goal.id
    runtime.kernel.store.close()

    restored = create_runtime(kernel_db_path=db_path)
    loaded = restored.kernel.goals.get(goal_id)
    assert loaded is not None
    assert loaded.status is GoalStatus.COMPLETED
    assert restored.kernel.contexts.get(goal_id) is not None
    assert restored.kernel.get_budget(goal_id) is not None

    events = restored.kernel.events.list_events(goal_id=goal_id)
    names = [event.name for event in events]
    assert "goal.created" in names
    assert "goal.activated" in names
    assert "run.started" in names
    assert "goal.completed" in names


@pytest.mark.asyncio
async def test_kernel_resume_after_interrupt(tmp_path: Path) -> None:
    db_path = tmp_path / "kernel-resume.sqlite3"
    runtime = create_runtime(kernel_db_path=db_path)
    runtime.kernel.interrupts.request_global("pause for operator")

    interrupted = await runtime.kernel.run("Resume me later", "session-resume")
    assert interrupted.interrupted is True
    assert interrupted.goal.status is GoalStatus.INTERRUPTED

    runtime.kernel.interrupts.clear_global()
    resumed = await runtime.kernel.resume(interrupted.goal.id)
    assert resumed.resumed is True
    assert resumed.goal.status is GoalStatus.COMPLETED
    assert resumed.response.status == "completed"
    assert resumed.response.artifacts["resumed"] is True

    events = runtime.kernel.events.list_events(goal_id=interrupted.goal.id)
    assert any(event.name == "goal.resume_requested" for event in events)
    assert any(event.name == "goal.completed" for event in events)


@pytest.mark.asyncio
async def test_kernel_emits_event_bus_domain_events() -> None:
    runtime = create_runtime()
    seen: list[str] = []

    async def capture(event: object) -> None:
        name = getattr(event, "name", None)
        domain = getattr(event, "domain", None)
        if domain == EventDomain.KERNEL and isinstance(name, str):
            seen.append(name)

    await runtime.event_bus.subscribe(EventDomain.KERNEL, capture)
    await runtime.kernel.run("Emit kernel bus events", "session-bus")
    assert "goal.created" in seen
    assert "goal.completed" in seen


def test_context_manager_restore_roundtrip() -> None:
    manager = ContextManager(default_max_items=8)
    manager.bind("g1", "s1", max_items=4)
    manager.put("g1", "objective", "restore me", tags=["kernel"])
    snapshot = manager.snapshot("g1")

    other = ContextManager()
    restored = other.restore(snapshot)
    assert restored.goal_id == "g1"
    assert other.get_value("g1", "objective") == "restore me"


def test_kernel_store_event_pagination(tmp_path: Path) -> None:
    store = KernelStore(tmp_path / "events.sqlite3")
    first = store.append_event(KernelEvent(name="a", goal_id="g1"))
    store.append_event(KernelEvent(name="b", goal_id="g1"))
    store.append_event(KernelEvent(name="c", goal_id="g1"))

    page = store.list_events(goal_id="g1", after_id=first.id, limit=10)
    assert [event.name for event in page] == ["b", "c"]
