"""Tests for the Reconstruction Confidence Score."""

import pytest

from core.confidence import calculate_confidence


def test_all_inputs_one_returns_high_score():
    result = calculate_confidence(1.0, 1.0, 1.0, 1.0)

    assert result["score"] == pytest.approx(1.0)
    assert result["label"] == "HIGH"


def test_all_inputs_zero_returns_unreliable_score():
    result = calculate_confidence(0.0, 0.0, 0.0, 0.0)

    assert result["score"] == pytest.approx(0.0)
    assert result["label"] == "UNRELIABLE"


def test_exact_weighted_formula():
    result = calculate_confidence(0.9, 0.8, 0.7, 0.6)
    expected = 0.30 * 0.9 + 0.30 * 0.8 + 0.25 * 0.7 + 0.15 * 0.6

    assert result["score"] == pytest.approx(expected)


def test_high_boundary():
    result = calculate_confidence(0.85, 0.85, 0.85, 0.85)

    assert result["score"] == pytest.approx(0.85)
    assert result["label"] == "HIGH"


def test_just_below_high_is_medium():
    result = calculate_confidence(0.849, 0.849, 0.849, 0.849)

    assert result["score"] < 0.85
    assert result["label"] == "MEDIUM"


def test_medium_boundary():
    result = calculate_confidence(0.65, 0.65, 0.65, 0.65)

    assert result["score"] == pytest.approx(0.65)
    assert result["label"] == "MEDIUM"


def test_low_boundary():
    result = calculate_confidence(0.40, 0.40, 0.40, 0.40)

    assert result["score"] == pytest.approx(0.40)
    assert result["label"] == "LOW"


def test_just_below_low_is_unreliable():
    result = calculate_confidence(0.399, 0.399, 0.399, 0.399)

    assert result["score"] < 0.40
    assert result["label"] == "UNRELIABLE"


def test_inputs_above_one_are_clamped():
    result = calculate_confidence(1.5, 2.0, 1.2, 5.0)

    assert result["score"] == pytest.approx(1.0)
    assert result["label"] == "HIGH"


def test_inputs_below_zero_are_clamped():
    result = calculate_confidence(-0.5, -1.0, -0.2, -5.0)

    assert result["score"] == pytest.approx(0.0)
    assert result["label"] == "UNRELIABLE"


def test_returned_score_is_float():
    result = calculate_confidence(0.5, 0.5, 0.5, 0.5)

    assert isinstance(result["score"], float)


def test_returned_label_is_allowed():
    result = calculate_confidence(0.5, 0.5, 0.5, 0.5)

    assert result["label"] in {"HIGH", "MEDIUM", "LOW", "UNRELIABLE"}


def test_perfect_controlled_reconstruction():
    result = calculate_confidence(1.0, 1.0, 1.0, 1.0)

    assert result["score"] == pytest.approx(1.0)
    assert result["label"] == "HIGH"


def test_structurally_invalid_artifact_is_not_high():
    result = calculate_confidence(1.0, 0.0, 1.0, 1.0)

    assert result["label"] != "HIGH"


def test_partial_reconstruction():
    result = calculate_confidence(1.0, 0.5, 0.5, 0.8)
    expected = 0.30 * 1.0 + 0.30 * 0.5 + 0.25 * 0.5 + 0.15 * 0.8

    assert result["score"] == pytest.approx(expected)


def test_conflicting_fragments():
    result = calculate_confidence(0.9, 0.8, 0.9, 0.0)
    expected = 0.30 * 0.9 + 0.30 * 0.8 + 0.25 * 0.9 + 0.15 * 0.0

    assert result["score"] == pytest.approx(expected)
