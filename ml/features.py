"""Deterministic statistical features for JPEG fragment analysis."""

import math
from collections.abc import Mapping

SOI_MARKER = b"\xff\xd8"
EOI_MARKER = b"\xff\xd9"
BOUNDARY_WINDOW_SIZE = 16


def _as_bytes(fragment: bytes | bytearray | memoryview | Mapping) -> bytes:
    if isinstance(fragment, Mapping):
        for key in ("data", "bytes", "content"):
            if key in fragment:
                fragment = fragment[key]
                break
        else:
            raise TypeError("fragment mapping must contain data, bytes, or content")
    if not isinstance(fragment, (bytes, bytearray, memoryview)):
        raise TypeError("fragment must be bytes-like or a mapping containing bytes")
    return bytes(fragment)


def _entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = [0] * 256
    for value in data:
        counts[value] += 1
    size = len(data)
    return -sum((count / size) * math.log2(count / size) for count in counts if count)


def _byte_statistics(data: bytes) -> tuple[float, float]:
    if not data:
        return 0.0, 0.0
    mean = sum(data) / len(data)
    variance = sum((value - mean) ** 2 for value in data) / len(data)
    return mean, math.sqrt(variance)


def _jpeg_marker_count(data: bytes) -> int:
    return sum(
        1
        for index in range(len(data) - 1)
        if data[index] == 0xFF and data[index + 1] not in (0x00, 0xFF)
    )


def extract_features(data: bytes | bytearray | memoryview | Mapping) -> dict[str, float | int | bool]:
    """Extract deterministic statistical and structural fragment features."""
    raw = _as_bytes(data)
    mean, standard_deviation = _byte_statistics(raw)
    size = len(raw)
    unique_ratio = len(set(raw)) / size if size else 0.0
    zero_ratio = raw.count(0) / size if size else 0.0

    return {
        "size": size,
        "entropy": _entropy(raw),
        "zero_byte_ratio": zero_ratio,
        "unique_byte_ratio": unique_ratio,
        "byte_mean": mean,
        "byte_std": standard_deviation,
        "header_present": raw.startswith(SOI_MARKER),
        "footer_present": raw.endswith(EOI_MARKER),
        "jpeg_marker_count": _jpeg_marker_count(raw),
    }


def _difference(first: float | int, second: float | int) -> float:
    return abs(float(first) - float(second))


def _boundary_features(first: bytes, second: bytes, window_size: int) -> dict[str, float | int]:
    first_boundary = first[-window_size:]
    second_boundary = second[:window_size]
    first_mean, first_std = _byte_statistics(first_boundary)
    second_mean, second_std = _byte_statistics(second_boundary)
    return {
        "boundary_window_size": window_size,
        "boundary_a_size": len(first_boundary),
        "boundary_b_size": len(second_boundary),
        "boundary_a_mean": first_mean,
        "boundary_b_mean": second_mean,
        "boundary_mean_difference": _difference(first_mean, second_mean),
        "boundary_a_std": first_std,
        "boundary_b_std": second_std,
        "boundary_std_difference": _difference(first_std, second_std),
        "boundary_a_zero_byte_ratio": first_boundary.count(0) / len(first_boundary) if first_boundary else 0.0,
        "boundary_b_zero_byte_ratio": second_boundary.count(0) / len(second_boundary) if second_boundary else 0.0,
    }


def extract_pair_features(
    fragment_a: bytes | bytearray | memoryview | Mapping,
    fragment_b: bytes | bytearray | memoryview | Mapping,
    window_size: int = BOUNDARY_WINDOW_SIZE,
) -> dict[str, float | int]:
    """Extract deterministic compatibility features for an A-to-B fragment pair."""
    if window_size <= 0:
        raise ValueError("window_size must be positive")
    first = _as_bytes(fragment_a)
    second = _as_bytes(fragment_b)
    first_features = extract_features(first)
    second_features = extract_features(second)

    return {
        "entropy_difference": _difference(first_features["entropy"], second_features["entropy"]),
        "byte_mean_difference": _difference(first_features["byte_mean"], second_features["byte_mean"]),
        "byte_std_difference": _difference(first_features["byte_std"], second_features["byte_std"]),
        "unique_byte_ratio_difference": _difference(first_features["unique_byte_ratio"], second_features["unique_byte_ratio"]),
        "zero_byte_ratio_difference": _difference(first_features["zero_byte_ratio"], second_features["zero_byte_ratio"]),
        "size_difference": abs(int(first_features["size"]) - int(second_features["size"])),
        **_boundary_features(first, second, window_size),
    }
