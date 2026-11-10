"""Cognitive Kernel — GAIA platform control plane for goals, budgets, and policy."""

from __future__ import annotations

import importlib

__all__ = [
    "BudgetExceededError",
    "BudgetSnapshot",
    "CognitiveKernel",
    "ContextItem",
    "ContextManager",
    "Goal",
    "GoalManager",
    "GoalStatus",
    "InterruptController",
    "InterruptRequest",
    "KernelConfig",
    "KernelEvent",
    "KernelEventLog",
    "KernelRunResult",
    "KernelState",
    "KernelStatus",
    "KernelStore",
    "PolicyCoordinator",
    "PolicyGateDecision",
    "ResourceBudget",
    "ResourceBudgetTracker",
    "VerificationCoordinator",
    "VerificationReport",
    "WorkingContext",
    "create_cognitive_kernel",
    "load_kernel_config",
]

_EXPORTS: dict[str, tuple[str, str]] = {
    "BudgetExceededError": ("gaia.kernel.resource_budget", "BudgetExceededError"),
    "BudgetSnapshot": ("gaia.kernel.resource_budget", "BudgetSnapshot"),
    "CognitiveKernel": ("gaia.kernel.kernel", "CognitiveKernel"),
    "ContextItem": ("gaia.kernel.context_manager", "ContextItem"),
    "ContextManager": ("gaia.kernel.context_manager", "ContextManager"),
    "Goal": ("gaia.kernel.goal_manager", "Goal"),
    "GoalManager": ("gaia.kernel.goal_manager", "GoalManager"),
    "GoalStatus": ("gaia.kernel.goal_manager", "GoalStatus"),
    "InterruptController": ("gaia.kernel.interrupt_controller", "InterruptController"),
    "InterruptRequest": ("gaia.kernel.interrupt_controller", "InterruptRequest"),
    "KernelConfig": ("gaia.kernel.config", "KernelConfig"),
    "KernelEvent": ("gaia.kernel.store", "KernelEvent"),
    "KernelEventLog": ("gaia.kernel.events", "KernelEventLog"),
    "KernelRunResult": ("gaia.kernel.kernel", "KernelRunResult"),
    "KernelState": ("gaia.kernel.state", "KernelState"),
    "KernelStatus": ("gaia.kernel.state", "KernelStatus"),
    "KernelStore": ("gaia.kernel.store", "KernelStore"),
    "PolicyCoordinator": ("gaia.kernel.policy_coordinator", "PolicyCoordinator"),
    "PolicyGateDecision": ("gaia.kernel.policy_coordinator", "PolicyGateDecision"),
    "ResourceBudget": ("gaia.kernel.resource_budget", "ResourceBudget"),
    "ResourceBudgetTracker": ("gaia.kernel.resource_budget", "ResourceBudgetTracker"),
    "VerificationCoordinator": (
        "gaia.kernel.verification_coordinator",
        "VerificationCoordinator",
    ),
    "VerificationReport": ("gaia.kernel.verification_coordinator", "VerificationReport"),
    "WorkingContext": ("gaia.kernel.context_manager", "WorkingContext"),
    "create_cognitive_kernel": ("gaia.kernel.kernel", "create_cognitive_kernel"),
    "load_kernel_config": ("gaia.kernel.config", "load_kernel_config"),
}


def __getattr__(name: str) -> object:
    """Load kernel exports without importing the runtime during package init."""
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    module = importlib.import_module(module_name)
    value = getattr(module, attribute)
    globals()[name] = value
    return value
