"""Cognitive Kernel execution errors."""


class KernelExecutionError(RuntimeError):
    """Base class for kernel execution failures."""


class KernelCancelledError(KernelExecutionError):
    """Raised when an operator or policy cancels an execution."""


class KernelTimeoutError(KernelExecutionError):
    """Raised when an execution exceeds its wall-clock budget."""


class KernelBudgetError(KernelExecutionError):
    """Raised when a planned or completed execution exceeds a budget."""
