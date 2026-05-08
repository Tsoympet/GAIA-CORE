"""Result aggregation for GAIA orchestration reports."""

from __future__ import annotations

from pydantic import BaseModel, Field

from gaia.metacognition.reflection_loop import ReflectionReport
from gaia.orchestrator.executor import ExecutionReport


class AggregatedResponse(BaseModel):
    """Structured response returned by the GAIA runtime and API."""

    task_id: str
    status: str = "completed"
    answer: str
    confidence: float
    agents: list[str] = Field(default_factory=list)
    reflection: ReflectionReport | None = None
    artifacts: dict[str, object] = Field(default_factory=dict)


class ResultAggregator:
    """Combine node outputs into a single auditable response."""

    async def aggregate(self, objective: str, report: ExecutionReport) -> AggregatedResponse:
        """Aggregate all node results into one response."""
        if not report.node_results:
            return AggregatedResponse(
                task_id=report.graph_id,
                status="empty",
                answer=f"No execution results were produced for: {objective}",
                confidence=0.0,
            )
        answers = [node.result.content for node in report.node_results]
        confidences = [node.result.confidence for node in report.node_results]
        return AggregatedResponse(
            task_id=report.graph_id,
            answer="\n".join(answers),
            confidence=sum(confidences) / len(confidences),
            agents=[node.result.agent_name for node in report.node_results],
            artifacts={
                "node_count": len(report.node_results),
                "pipeline": [
                    "planner",
                    "task_graph",
                    "capability_router",
                    "agent_executor",
                    "result_aggregator",
                    "reflection_loop",
                ],
                "routes": [node.route.model_dump(mode="json") for node in report.node_results],
                "node_statuses": [
                    {
                        "node_id": node.node_id,
                        "agent": node.route.selected_agent,
                        "model": node.route.selected_model,
                        "tool": node.route.selected_tool,
                        "execution_mode": node.route.execution_mode,
                        "status": "completed",
                "node_results": [
                    {
                        "node_id": node.node_id,
                        "agent": node.result.agent_name,
                        "success": True,
                        "confidence": node.result.confidence,
                    }
                    for node in report.node_results
                ],
            },
        )
