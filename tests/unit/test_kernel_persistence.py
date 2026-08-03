from pathlib import Path

import pytest

from gaia.core import TaskRequest, create_runtime
from gaia.kernel import (
    CognitiveKernel,
    ExecutionStatus,
    GoalStatus,
    ResourceBudget,
    SQLiteKernelStore,
)
from gaia.orchestrator.aggregator import AggregatedResponse


def test_sqlite_kernel_store_recovers_interrupted_execution(
    tmp_path: Path,
) -> None:
    database = tmp_path / "kernel.sqlite3"
    kernel = CognitiveKernel(store=SQLiteKernelStore(database))
    execution = kernel.begin_execution(
        objective="Persist an unfinished kernel task",
        session_id="session-1",
        capabilities=["reasoning"],
    )

    restarted = CognitiveKernel(store=SQLiteKernelStore(database))
    recovered = restarted.get_execution(execution.execution_id)
    goal = restarted.goals.get(execution.goal_id)

    assert recovered.status == ExecutionStatus.INTERRUPTED
    assert recovered.error == "execution interrupted by runtime restart"
    assert goal.status == GoalStatus.PAUSED
    assert restarted.status().recovered_interruptions == 1
    assert restarted.status().storage.durable is True


@pytest.mark.asyncio
async def test_completed_kernel_execution_survives_restart(
    tmp_path: Path,
) -> None:
    database = tmp_path / "kernel.sqlite3"
    kernel = CognitiveKernel(store=SQLiteKernelStore(database))
    execution = kernel.begin_execution(
        objective="Complete a persistent kernel task",
        session_id="session-1",
        capabilities=["reasoning"],
        budget=ResourceBudget(max_steps=1),
    )

    async def operation() -> AggregatedResponse:
        return AggregatedResponse(
            task_id="persistent-task",
            status="completed",
            answer="persistent result",
            confidence=1.0,
            artifacts={"node_count": 1},
        )

    await kernel.run_guarded(execution.execution_id, operation)
    restarted = CognitiveKernel(store=SQLiteKernelStore(database))

    assert (
        restarted.get_execution(execution.execution_id).status
        == ExecutionStatus.COMPLETED
    )
    assert restarted.goals.get(execution.goal_id).status == GoalStatus.COMPLETED
    assert restarted.status().recovered_interruptions == 0


def test_sqlite_kernel_store_backup_is_loadable(tmp_path: Path) -> None:
    database = tmp_path / "kernel.sqlite3"
    backup = tmp_path / "backups" / "kernel-backup.sqlite3"
    kernel = CognitiveKernel(store=SQLiteKernelStore(database))
    goal = kernel.goals.create("Back up kernel state")

    created = Path(kernel.backup_state(str(backup)))
    restored = CognitiveKernel(store=SQLiteKernelStore(created))

    assert created == backup.resolve()
    assert restored.goals.get(goal.goal_id).objective == "Back up kernel state"
    assert restored.status().storage.schema_version == 1


@pytest.mark.asyncio
async def test_runtime_can_use_durable_kernel_store(tmp_path: Path) -> None:
    database = tmp_path / "runtime-kernel.sqlite3"
    runtime = create_runtime(kernel_store_path=database)

    response = await runtime.submit_task(
        TaskRequest(
            task="Run a durable kernel task",
            capabilities=["reasoning"],
        )
    )
    restarted = create_runtime(kernel_store_path=database)

    execution_id = response.artifacts["kernel"]["execution_id"]
    assert (
        restarted.kernel.get_execution(execution_id).status
        == ExecutionStatus.COMPLETED
    )
    assert restarted.status().kernel.storage.backend == "sqlite"
    assert restarted.status().kernel.storage.executions == 1


def test_terminal_execution_and_goal_can_be_deleted(tmp_path: Path) -> None:
    database = tmp_path / "kernel.sqlite3"
    kernel = CognitiveKernel(store=SQLiteKernelStore(database))
    execution = kernel.begin_execution(
        objective="Delete completed records",
        session_id="session-1",
        capabilities=["reasoning"],
    )
    kernel.mark_failed(execution.execution_id, "test completion")

    assert kernel.delete_execution(execution.execution_id) is True
    assert kernel.goals.delete(execution.goal_id) is True
    assert kernel.status().storage.executions == 0
    assert kernel.status().storage.goals == 0
