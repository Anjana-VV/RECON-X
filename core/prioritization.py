"""Forensic evidence triage and prioritization engine."""

import math


def calculate_priority(
    confidence: float,
    recovery_completeness: float,
    structural_integrity: float,
    relevance: float
) -> float:
    """Calculate a transparent Evidence Priority score for an artifact."""
    confidence = max(0.0, min(1.0, float(confidence)))
    recovery_completeness = max(0.0, min(1.0, float(recovery_completeness)))
    structural_integrity = max(0.0, min(1.0, float(structural_integrity)))
    relevance = max(0.0, min(1.0, float(relevance)))

    priority = math.fsum(
        (
            0.40 * confidence,
            0.30 * recovery_completeness,
            0.20 * structural_integrity,
            0.10 * relevance,
        )
    )

    return float(max(0.0, min(1.0, priority)))
