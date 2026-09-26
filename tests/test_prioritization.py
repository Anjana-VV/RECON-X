"""Tests for the Evidence Priority score."""

import pytest

from core.prioritization import calculate_priority


def test_all_values_one_returns_one():
    assert calculate_priority(1.0, 1.0, 1.0, 1.0) == pytest.approx(1.0)


def test_all_values_zero_returns_zero():
    assert calculate_priority(0.0, 0.0, 0.0, 0.0) == pytest.approx(0.0)


def test_exact_weighted_formula():
    result = calculate_priority(0.9, 0.8, 0.7, 0.6)
    expected = 0.40 * 0.9 + 0.30 * 0.8 + 0.20 * 0.7 + 0.10 * 0.6

    assert result == pytest.approx(expected)


def test_inputs_above_one_are_clamped():
    result = calculate_priority(1.5, 2.0, 1.2, 5.0)

    assert result == pytest.approx(1.0)


def test_inputs_below_zero_are_clamped():
    result = calculate_priority(-0.5, -1.0, -0.2, -5.0)

    assert result == pytest.approx(0.0)


def test_final_result_is_clamped():
    result = calculate_priority(100.0, 100.0, 100.0, 100.0)

    assert 0.0 <= result <= 1.0
    assert result == pytest.approx(1.0)


def test_returned_value_is_float():
    assert isinstance(calculate_priority(0.5, 0.5, 0.5, 0.5), float)


def test_confidence_has_largest_weight():
    baseline = calculate_priority(0.2, 0.2, 0.2, 0.2)
    changed = calculate_priority(0.7, 0.2, 0.2, 0.2)

    assert changed - baseline == pytest.approx(0.40 * 0.5)


def test_recovery_completeness_has_second_largest_weight():
    baseline = calculate_priority(0.2, 0.2, 0.2, 0.2)
    changed = calculate_priority(0.2, 0.7, 0.2, 0.2)

    assert changed - baseline == pytest.approx(0.30 * 0.5)


def test_structural_integrity_has_third_largest_weight():
    baseline = calculate_priority(0.2, 0.2, 0.2, 0.2)
    changed = calculate_priority(0.2, 0.2, 0.7, 0.2)

    assert changed - baseline == pytest.approx(0.20 * 0.5)


def test_relevance_has_smallest_weight():
    baseline = calculate_priority(0.2, 0.2, 0.2, 0.2)
    changed = calculate_priority(0.2, 0.2, 0.2, 0.7)

    assert changed - baseline == pytest.approx(0.10 * 0.5)


def test_perfect_reconstruction_returns_one():
    assert calculate_priority(1.0, 1.0, 1.0, 1.0) == pytest.approx(1.0)


def test_poor_evidence():
    result = calculate_priority(0.2, 0.1, 0.1, 0.5)
    expected = 0.40 * 0.2 + 0.30 * 0.1 + 0.20 * 0.1 + 0.10 * 0.5

    assert result == pytest.approx(expected)


def test_high_relevance_does_not_override_poor_evidence():
    result = calculate_priority(0.1, 0.1, 0.1, 1.0)

    assert result == pytest.approx(0.19)
    assert result < 0.5


def test_strong_evidence_with_low_relevance():
    result = calculate_priority(1.0, 1.0, 1.0, 0.0)

    assert result == pytest.approx(0.90)
