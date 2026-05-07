"""Security and autonomy policy bootstrap."""

from pydantic import BaseModel, Field


class SecurityDecision(BaseModel):
    """Result of evaluating an objective against safety policy."""

    allowed: bool
    requires_human_approval: bool = False
    reasons: list[str] = Field(default_factory=list)


class SecurityPolicy(BaseModel):
    """Secure-by-default policy for controlled autonomy."""

    sandbox_required: bool = True
    human_override_available: bool = True
    blocked_terms: list[str] = Field(default_factory=lambda: ["self-replicate", "bypass security"])

    def evaluate_objective(self, objective: str) -> SecurityDecision:
        """Evaluate high-level task objectives before orchestration."""
        lowered = objective.lower()
        reasons = [term for term in self.blocked_terms if term in lowered]
        if reasons:
            return SecurityDecision(allowed=False, requires_human_approval=True, reasons=reasons)
        return SecurityDecision(allowed=True)


def create_security_policy() -> SecurityPolicy:
    """Create the default secure policy."""
    return SecurityPolicy()
