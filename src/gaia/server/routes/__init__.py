"""FastAPI route modules."""

from . import (
    agents,
    audio,
    chat,
    dreaming,
    idle_cognition,
    memory,
    metacognition,
    models,
    security,
    self_model,
    tools,
    voice,
    workspaces,
)

ROUTERS = [
    chat.router,
    voice.router,
    audio.router,
    agents.router,
    memory.router,
    models.router,
    tools.router,
    workspaces.router,
    security.router,
    self_model.router,
    metacognition.router,
    dreaming.router,
    idle_cognition.router,
]

__all__ = ["ROUTERS"]
