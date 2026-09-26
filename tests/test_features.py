"""Tests for deterministic fragment feature extraction."""

import math

import pytest

from ml.features import extract_features, extract_pair_features


def test_features_are_deterministic():
    data = b"\xff\xd8abc\x00abc\xff\xd9"

    assert extract_features(data) == extract_features(data)
    assert extract_pair_features(data, b"xyz") == extract_pair_features(data, b"xyz")


def test_valid_jpeg_features():
    data = b"\xff\xd8\xff\xe0JPEG\xff\xd9"
    features = extract_features(data)

    assert features["size"] == len(data)
    assert features["header_present"] is True
    assert features["footer_present"] is True
    assert features["jpeg_marker_count"] == 3
    assert features["entropy"] > 0.0
    assert features["byte_mean"] == pytest.approx(sum(data) / len(data))
    assert features["byte_std"] > 0.0


def test_random_and_corrupt_bytes_are_measured_without_claims():
    random_features = extract_features(bytes(range(256)))
    corrupt_features = extract_features(b"\xff\xd8corrupt\x00\x00")

    assert random_features["size"] == 256
    assert random_features["header_present"] is False
    assert random_features["footer_present"] is False
    assert corrupt_features["header_present"] is True
    assert corrupt_features["footer_present"] is False
    assert corrupt_features["zero_byte_ratio"] > 0.0


def test_empty_bytes_have_zero_safe_statistics():
    features = extract_features(b"")

    assert features == {
        "size": 0,
        "entropy": 0.0,
        "zero_byte_ratio": 0.0,
        "unique_byte_ratio": 0.0,
        "byte_mean": 0.0,
        "byte_std": 0.0,
        "header_present": False,
        "footer_present": False,
        "jpeg_marker_count": 0,
    }


def test_pair_features_include_differences_and_boundary_statistics():
    first = bytes([0, 1, 2, 3, 4, 5])
    second = bytes([10, 10, 10, 10])
    features = extract_pair_features(first, second, window_size=2)

    assert features["size_difference"] == 2
    assert features["byte_mean_difference"] == pytest.approx(7.5)
    assert features["boundary_window_size"] == 2
    assert features["boundary_a_size"] == 2
    assert features["boundary_b_size"] == 2
    assert features["boundary_a_mean"] == pytest.approx(4.5)
    assert features["boundary_b_mean"] == pytest.approx(10.0)
    assert features["boundary_mean_difference"] == pytest.approx(5.5)
    assert features["boundary_a_zero_byte_ratio"] == 0.0
    assert features["boundary_b_zero_byte_ratio"] == 0.0
    assert features["entropy_difference"] == pytest.approx(math.log2(6))
    assert features["byte_std_difference"] == pytest.approx(
        abs((sum((value - 2.5) ** 2 for value in first) / len(first)) ** 0.5)
    )
    assert features["unique_byte_ratio_difference"] == pytest.approx(0.75)
    assert features["zero_byte_ratio_difference"] == pytest.approx(1 / 6)
    assert features["boundary_std_difference"] == pytest.approx(
        (sum((value - 4.5) ** 2 for value in first[-2:]) / 2) ** 0.5
    )


def test_fragment_mapping_with_embedded_bytes_is_supported():
    features = extract_features({"fragment_id": "FRAG-001", "data": b"abc"})

    assert features["size"] == 3
