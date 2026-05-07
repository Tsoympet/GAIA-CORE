"""GAIA orchestration package.

This package provides the request-planning, task-graph, capability-routing,
execution-state, executor, and aggregation primitives that implement GAIA's
orchestration loop.
"""

from .aggregator import FinalResponse, ResultAggregator
from .dependency_resolver import DependencyResolver
from .execution_state import ExecutionState, NodeExecutionRecord
from .executor import OrchestrationExecutor
from .planner import PlanningOptions, RequestPlanner
from .router import CapabilityRouter, RouteTarget
from .task_graph import TaskGraph
from .task_node import CapabilityRequirement, RetryPolicy, TaskNode, TaskStatus

__all__ = [
    "CapabilityRequirement",
    "CapabilityRouter",
    "DependencyResolver",
    "ExecutionState",
    "FinalResponse",
    "NodeExecutionRecord",
    "OrchestrationExecutor",
    "PlanningOptions",
    "RequestPlanner",
    "ResultAggregator",
    "RetryPolicy",
    "RouteTarget",
    "TaskGraph",
    "TaskNode",
    "TaskStatus",
]
"""Task graph orchestration, scheduling, routing, and reflection loops."""

from gaia.orchestrator.engine import Orchestrator, TaskGraph, create_orchestrator

__all__ = ["Orchestrator", "TaskGraph", "create_orchestrator"]
