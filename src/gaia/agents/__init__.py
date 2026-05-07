"""Built-in GAIA agents and capability registry."""

from .agent_registry import AgentRegistry, create_default_registry
from .base_agent import (
    AgentExecutionContext,
    AgentMetadata,
    AgentPermissionError,
    AgentResult,
    AgentStatus,
    BaseAgent,
    Permission,
)
from .gaia_code_agent import GaiaCodeAgent
from .gaia_core_agent import GaiaCoreAgent
from .gaia_dreaming_agent import GaiaDreamingAgent
from .gaia_engineer_agent import GaiaEngineerAgent
from .gaia_memory_agent import GaiaMemoryAgent
from .gaia_metacognition_agent import GaiaMetacognitionAgent
from .gaia_research_agent import GaiaResearchAgent
from .gaia_security_agent import GaiaSecurityAgent
from .gaia_self_model_agent import GaiaSelfModelAgent

__all__ = (
    "AgentExecutionContext",
    "AgentMetadata",
    "AgentPermissionError",
    "AgentRegistry",
    "AgentResult",
    "AgentStatus",
    "BaseAgent",
    "GaiaCodeAgent",
    "GaiaCoreAgent",
    "GaiaDreamingAgent",
    "GaiaEngineerAgent",
    "GaiaMemoryAgent",
    "GaiaMetacognitionAgent",
    "GaiaResearchAgent",
    "GaiaSecurityAgent",
    "GaiaSelfModelAgent",
    "Permission",
    "create_default_registry",
)
