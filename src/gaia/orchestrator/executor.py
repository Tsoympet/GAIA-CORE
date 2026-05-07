"""Async orchestration executors with retry, timeout, and cancellation support."""

from __future__ import annotations

import asyncio
from inspect import isawaitable
from typing import Any

from .dependency_resolver import DependencyResolver
from .execution_state import ExecutionState
from .router import CapabilityRouter
from .task_graph import TaskGraph
from .task_node import TaskNode, TaskStatus


class OrchestrationExecutor:
    """Execute task graphs sequentially or in dependency-safe parallel layers."""

    def __init__(self, router: CapabilityRouter) -> None:
        self.router = router

    async def execute_sequential(
        self,
        graph: TaskGraph,
        *,
        context: dict[str, Any] | None = None,
        state: ExecutionState | None = None,
        stop_on_failure: bool = True,
    ) -> ExecutionState:
        graph.validate()
        execution_state = state or ExecutionState.from_nodes(list(graph))
        resolver = DependencyResolver(graph)
        context = context or {}

        for node in graph.topological_sort():
            if execution_state.cancelled:
                break
            failed_dependencies = node.dependencies & execution_state.failed_ids
            if failed_dependencies:
                execution_state.skip(node.id, f"failed dependencies: {sorted(failed_dependencies)}")
                if stop_on_failure:
                    break
                continue
            if node.id not in resolver.executable_nodes(execution_state.completed_ids):
                continue
            await self._execute_node(node, context, execution_state)
            if stop_on_failure and execution_state.records[node.id].status is TaskStatus.FAILED:
                break

        self._skip_unfinished(graph, execution_state)
        execution_state.mark_complete_if_terminal()
        return execution_state

    async def execute_parallel(
        self,
        graph: TaskGraph,
        *,
        context: dict[str, Any] | None = None,
        state: ExecutionState | None = None,
        stop_on_failure: bool = True,
    ) -> ExecutionState:
        graph.validate()
        execution_state = state or ExecutionState.from_nodes(list(graph))
        context = context or {}

        for layer in graph.traversal_layers():
            if execution_state.cancelled:
                break
            runnable = [node for node in layer if not (node.dependencies & execution_state.failed_ids)]
            skipped = [node for node in layer if node.dependencies & execution_state.failed_ids]
            for node in skipped:
                execution_state.skip(node.id, f"failed dependencies: {sorted(node.dependencies & execution_state.failed_ids)}")

            await asyncio.gather(
                *(self._execute_node(node, context, execution_state) for node in runnable)
            )
            if stop_on_failure and execution_state.failed_ids:
                break

        self._skip_unfinished(graph, execution_state)
        execution_state.mark_complete_if_terminal()
        return execution_state

    def cancel(self, state: ExecutionState, reason: str = "execution cancelled") -> None:
        state.cancel(reason)

    async def _execute_node(
        self,
        node: TaskNode,
        context: dict[str, Any],
        state: ExecutionState,
    ) -> None:
        record = state.ensure_node(node.id)
        if record.status in {TaskStatus.SUCCEEDED, TaskStatus.CANCELLED, TaskStatus.SKIPPED}:
            return

        delay = node.retry_policy.backoff_seconds
        for attempt_index in range(node.retry_policy.max_attempts):
            if state.cancelled:
                state.cancel()
                return
            state.start(node.id)
            try:
                result = await self._run_with_timeout(node, context)
                state.succeed(node.id, result)
                node.result = result
                node.status = TaskStatus.SUCCEEDED
                return
            except asyncio.CancelledError:
                state.cancel()
                raise
            except TimeoutError as exc:
                state.fail(node.id, exc)
                if not node.retry_policy.retry_on_timeout:
                    return
            except Exception as exc:  # noqa: BLE001 - captured into execution state by design.
                state.fail(node.id, exc)

            if attempt_index < node.retry_policy.max_attempts - 1 and delay > 0:
                await asyncio.sleep(delay)
                delay *= node.retry_policy.backoff_multiplier

    async def _run_with_timeout(self, node: TaskNode, context: dict[str, Any]) -> Any:
        target = self.router.select(node)
        result = target.runner(node, context)
        if isawaitable(result):
            if node.timeout_seconds is None:
                return await result
            return await asyncio.wait_for(result, timeout=node.timeout_seconds)
        return result

    def _skip_unfinished(self, graph: TaskGraph, state: ExecutionState) -> None:
        terminal = {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.SKIPPED}
        for node in graph:
            record = state.ensure_node(node.id)
            if record.status not in terminal:
                state.skip(node.id, "execution did not reach this node")
