from gaia.self_model import CapabilitySelfMap, LimitationRegistry, SimulatedSelfModel


def test_self_model_snapshot_uses_safe_simulation_language() -> None:
    capabilities = CapabilitySelfMap()
    capabilities.update("planning", "Create typed task plans.", 0.7)
    limitations = LimitationRegistry()
    limitations.add("bootstrap", "First version uses deterministic local agents.")

    snapshot = SimulatedSelfModel(capabilities, limitations).snapshot()

    assert "simulated" in snapshot.identity.lower()
    assert "not sentience" in snapshot.statement
    assert snapshot.capabilities == ["planning"]
