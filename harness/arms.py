"""Shared, explicit treatment packages and original-step resource allowances."""
from __future__ import annotations

from dataclasses import dataclass

LEGACY_DESIGN = "model-stratified-v1"
BLOCKED_DESIGN = "model-blocked-v2"
MODELS = ("gpt-6.1-sol", "claude-sonnet-5.5", "gemini-4-argon")


@dataclass(frozen=True)
class Arm:
    """Describe a treatment, without giving candidates evaluator feedback."""

    label: str
    description: str
    post: str | None
    post_prompt: str | None
    feature_credit_multiplier: int = 1


ARMS = {
    "A": Arm("A", "Feature-only builder", None, None),
    "B": Arm("B", "Behavior-preserving consolidation, tests and DESIGN.md",
             "consolidation", "consolidation-step.prompt.md"),
    "C": Arm("C", "Read-only review; REVIEW.md may inform later feature sessions",
             "review", "review-only-step.prompt.md"),
    "D": Arm("D", "Matched-resource A+ builder; no scheduled post-step",
             None, None, feature_credit_multiplier=2),
    "E": Arm("E", "Visible-specification regression repair; not hidden feedback",
             "repair", "repair-step.prompt.md"),
}


def descriptor(arm: str) -> Arm:
    """Reject an unknown treatment instead of silently treating it as review."""
    if arm not in ARMS:
        raise ValueError(f"Unknown study arm: {arm}")
    return ARMS[arm]


def endpoint_kind(arm: str) -> str:
    """Return the final checkpoint kind of each feature cycle."""
    return descriptor(arm).post or "feature"


def cycle_kinds(arm: str) -> tuple[str, ...]:
    """Return scheduled kinds, excluding retries and the held-out change request."""
    post = descriptor(arm).post
    return ("feature", post) if post else ("feature",)


def planned_steps(arm: str, features: int, change_request: bool) -> int:
    """Count original scheduled sessions, never attempts or success observations."""
    return features * len(cycle_kinds(arm)) + int(change_request)


def step_kind(arm: str, step: str) -> str:
    """Validate a scheduled step before selecting its allowance."""
    kind = "change_request" if step.endswith("-change") else step.rsplit("-", 1)[-1]
    if kind not in (*cycle_kinds(arm), "change_request"):
        raise ValueError(f"{step} is not scheduled for arm {arm}")
    return kind


def credit_multiplier(arm: str, kind: str) -> int:
    """Only D's feature session can receive twice the base credit allowance."""
    if kind not in (*cycle_kinds(arm), "change_request"):
        raise ValueError(f"{kind} is not scheduled for arm {arm}")
    return descriptor(arm).feature_credit_multiplier if kind == "feature" else 1


def feature_seconds(arm: str, budgets: dict) -> int:
    """Give D the sum of the ordinary feature and post ceilings."""
    descriptor(arm)
    return budgets["feature"] + (budgets["post"] if arm == "D" else 0)


def descriptors() -> dict:
    """Export source-controlled treatment and nominal resource declarations."""
    return {
        name: {
            "description": arm.description, "post_kind": arm.post,
            "feature_seconds": feature_seconds(name, {"feature": 1800, "post": 900}),
            "post_seconds": 900 if arm.post else 0,
            "feature_nominal_credits": 300 * arm.feature_credit_multiplier,
            "feature_operational_soft_credits": 270 * arm.feature_credit_multiplier,
            "post_nominal_credits": 300 if arm.post else 0,
            "post_operational_soft_credits": 270 if arm.post else 0,
            "change_request_seconds": 2700, "change_request_nominal_credits": 300,
            "change_request_operational_soft_credits": 270,
        } for name, arm in ARMS.items()
    }
