"""Agent registry and capability router for GAIA agents."""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any

from .base_agent import AgentExecutionContext, AgentResult, BaseAgent


@dataclass(slots=True)
class AgentRegistry:
    """Registry for loading, discovering, and routing agents by capability."""

    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("gaia.agents.registry"))
    _agents: dict[str, BaseAgent] = field(default_factory=dict, init=False)
    _capability_index: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list), init=False)

    def register(self, agent: BaseAgent, replace: bool = False) -> BaseAgent:
        """Register an agent instance and index its advertised capabilities."""

        name = agent.metadata.name
        if not replace and name in self._agents:
            raise ValueError(f"Agent already registered: {name}")

        if replace and name in self._agents:
            self.unregister(name)

        self._agents[name] = agent
        for capability in sorted(agent.capabilities):
            if name not in self._capability_index[capability]:
                self._capability_index[capability].append(name)

        self.logger.info(
            "agent_registered",
            extra={
                "gaia_event": "agent_registered",
                "agent_name": name,
                "capabilities": tuple(sorted(agent.capabilities)),
            },
        )
        return agent

    def unregister(self, name: str) -> BaseAgent:
        """Remove an agent from the registry and capability index."""

        agent = self._agents.pop(name)
        for capability in agent.capabilities:
            names = self._capability_index.get(capability, [])
            if name in names:
                names.remove(name)
            if not names and capability in self._capability_index:
                del self._capability_index[capability]
        return agent

    def get(self, name: str) -> BaseAgent | None:
        """Return a registered agent by name, if present."""

        return self._agents.get(name)

    def list_agents(self) -> tuple[BaseAgent, ...]:
        """Return all registered agents sorted by name."""

        return tuple(self._agents[name] for name in sorted(self._agents))

    def capabilities(self) -> tuple[str, ...]:
        """Return all capabilities currently routable by this registry."""

        return tuple(sorted(self._capability_index))

    def agents_for_capability(self, capability: str) -> tuple[BaseAgent, ...]:
        """Return registered agents that advertise a capability."""

        return tuple(self._agents[name] for name in self._capability_index.get(capability, ()))

    def route(self, capability: str) -> BaseAgent | None:
        """Return the first registered agent that can handle a capability."""

        agents = self.agents_for_capability(capability)
        return agents[0] if agents else None

    async def execute(self, capability: str, context: AgentExecutionContext) -> AgentResult:
        """Route an execution request to the first agent matching ``capability``."""

        agent = self.route(capability)
        if agent is None:
            raise LookupError(f"No registered GAIA agent can handle capability: {capability}")
        return await agent.execute(context)

    def discover(self, package: str = "gaia.agents", replace: bool = False) -> tuple[BaseAgent, ...]:
        """Import a package and register every concrete ``BaseAgent`` subclass found."""

        module = importlib.import_module(package)
        modules = [module, *self._iter_submodules(module)]
        discovered: list[BaseAgent] = []

        for imported_module in modules:
            for agent_type in self._agent_types(imported_module):
                if agent_type.metadata.name in self._agents and not replace:
                    continue
                discovered.append(self.register(agent_type(), replace=replace))

        return tuple(discovered)

    def load(self, dotted_path: str, replace: bool = False, **kwargs: Any) -> BaseAgent:
        """Load and register an agent from ``module:ClassName`` or ``module.ClassName``."""

        module_name, _, class_name = dotted_path.partition(":")
        if not class_name:
            module_name, _, class_name = dotted_path.rpartition(".")
        if not module_name or not class_name:
            raise ValueError(f"Invalid agent dotted path: {dotted_path}")

        module = importlib.import_module(module_name)
        agent_type = getattr(module, class_name)
        if not inspect.isclass(agent_type) or not issubclass(agent_type, BaseAgent) or agent_type is BaseAgent:
            raise TypeError(f"Path does not point to a BaseAgent subclass: {dotted_path}")

        return self.register(agent_type(**kwargs), replace=replace)

    def _iter_submodules(self, module: ModuleType) -> Iterable[ModuleType]:
        if not hasattr(module, "__path__"):
            return ()
        return (
            importlib.import_module(module_info.name)
            for module_info in pkgutil.walk_packages(module.__path__, prefix=f"{module.__name__}.")
        )

    def _agent_types(self, module: ModuleType) -> tuple[type[BaseAgent], ...]:
        agent_types: list[type[BaseAgent]] = []
        for _, candidate in inspect.getmembers(module, inspect.isclass):
            if candidate is BaseAgent or not issubclass(candidate, BaseAgent):
                continue
            if inspect.isabstract(candidate):
                continue
            if candidate.__module__ != module.__name__:
                continue
            agent_types.append(candidate)
        return tuple(agent_types)


def create_default_registry() -> AgentRegistry:
    """Create a registry populated with all built-in GAIA agents."""

    registry = AgentRegistry()
    registry.discover()
    return registry
