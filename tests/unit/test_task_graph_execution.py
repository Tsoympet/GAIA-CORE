from gaia.orchestrator.task_graph import TaskGraph, TaskNode


def test_task_graph_execution_order_respects_dependencies() -> None:
    first = TaskNode(id="a", objective="first", required_capabilities=["reasoning"])
    second = TaskNode(id="b", objective="second", dependencies=["a"])
    graph = TaskGraph(objective="ordered", nodes=[second, first])

    assert [node.id for node in graph.execution_order()] == ["a", "b"]
