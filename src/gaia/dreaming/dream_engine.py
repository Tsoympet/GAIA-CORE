"""Safe idle cognition engine for GAIA."""

from __future__ import annotations

from pydantic import BaseModel, Field

from gaia.dreaming.goal_rehearsal import GoalRehearsal
from gaia.dreaming.memory_consolidator import MemoryConsolidator
from gaia.dreaming.no_action_guard import NoActionGuard
from gaia.dreaming.problem_replay import ProblemReplay
from gaia.dreaming.synthetic_scenario_generator import SyntheticScenarioGenerator
from gaia.memory.memory_manager import MemoryManager


class DreamReport(BaseModel):
    """Idle cognition report containing only internal notes."""

    notes: list[str] = Field(default_factory=list)


class DreamEngine:
    """Coordinates safe analysis, replay, and simulation while idle."""

    def __init__(self, guard: NoActionGuard | None = None) -> None:
        self.guard = guard or NoActionGuard()
        self.consolidator = MemoryConsolidator()
        self.scenario_generator = SyntheticScenarioGenerator()
        self.problem_replay = ProblemReplay()
        self.goal_rehearsal = GoalRehearsal()

    async def run_idle_cycle(
        self,
        memory: MemoryManager,
        *,
        failed_task: str | None = None,
        future_goal: str | None = None,
    ) -> DreamReport:
        """Run safe idle cognition without executing external actions."""
        self.guard.require("simulate")
        report = DreamReport()
        record = await self.consolidator.consolidate(memory)
        report.notes.append(record.content)
        if failed_task:
            report.notes.append(self.problem_replay.replay(failed_task))
            report.notes.extend(self.scenario_generator.generate(failed_task))
        if future_goal:
            report.notes.extend(self.goal_rehearsal.rehearse(future_goal))
        await memory.remember("idle_report", "\n".join(report.notes), {"external_actions": False})
        return report
