"""Synthetic scenario generation for GAIA idle simulation."""

from __future__ import annotations


class SyntheticScenarioGenerator:
    """Creates internal-only test scenarios from goals or failures."""

    def generate(self, seed: str, count: int = 3) -> list[str]:
        """Generate deterministic synthetic scenarios without external actions."""
        return [f"Synthetic scenario {index + 1}: safely simulate {seed}" for index in range(count)]
