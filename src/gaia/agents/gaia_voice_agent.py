"""GAIA voice agent for voice conversations and audio task routing."""
from __future__ import annotations

from gaia.agents.base_agent import AgentContext, AgentResult, BaseAgent
from gaia.voice.voice_manager import VoiceManager


class GaiaVoiceAgent(BaseAgent):
    name = "gaia_voice_agent"
    description = "Synthetic voice, speech, and audio conversation specialist."
    capabilities = ("voice", "speech", "audio")

    def __init__(self, voice_manager: VoiceManager | None = None) -> None:
        self.voice_manager = voice_manager or VoiceManager()

    async def run(self, task: str, context: AgentContext) -> AgentResult:
        status = self.voice_manager.status()
        return AgentResult(
            task_id=context.task_id,
            agent_name=self.name,
            content=f"Voice subsystem ready for synthetic profile {status.profile_id}: {task}",
            confidence=0.62,
            artifacts=status.model_dump(),
        )
