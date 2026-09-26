"""Reconstruction Confidence Score calculation engine."""

import math

# Defined threshold boundaries
LABEL_HIGH = "HIGH"
LABEL_MEDIUM = "MEDIUM"
LABEL_LOW = "LOW"
LABEL_UNRELIABLE = "UNRELIABLE"


def calculate_confidence(
    classification: float,
    structural_integrity: float,
    recovery_completeness: float,
    fragment_consistency: float
) -> dict:
    """Calculate the explainable Reconstruction Confidence Score.

    Combines 4 measured forensic dimensions into a transparent weighted score:
        overall = 0.30 * classification
                + 0.30 * structural_integrity
                + 0.25 * recovery_completeness
                + 0.15 * fragment_consistency

    Note:
        This is an engineering confidence score based on physical and structural
        evidence measurements, NOT a probability or statistical likelihood.

    Args:
        classification: Confidence in JPEG artifact identification [0.0, 1.0].
        structural_integrity: Assessment of decodability and marker validity [0.0, 1.0].
        recovery_completeness: Ratio of recovered bytes to expected bytes [0.0, 1.0].
        fragment_consistency: Alignment and non-conflict of constituent fragments [0.0, 1.0].

    Returns:
        dict: {"score": float, "label": "HIGH" | "MEDIUM" | "LOW" | "UNRELIABLE"}
    """
    # Clamp all inputs to [0.0, 1.0]
    c = max(0.0, min(1.0, float(classification)))
    s = max(0.0, min(1.0, float(structural_integrity)))
    r = max(0.0, min(1.0, float(recovery_completeness)))
    f = max(0.0, min(1.0, float(fragment_consistency)))

    # Exact weighted formula
    overall = math.fsum((0.30 * c, 0.30 * s, 0.25 * r, 0.15 * f))

    # Clamp final score
    overall = max(0.0, min(1.0, float(overall)))

    # Determine the label from the exact threshold boundaries.
    if overall >= 0.85:
        label = LABEL_HIGH
    elif overall >= 0.65:
        label = LABEL_MEDIUM
    elif overall >= 0.40:
        label = LABEL_LOW
    else:
        label = LABEL_UNRELIABLE

    return {
        "score": overall,
        "label": label,
    }
