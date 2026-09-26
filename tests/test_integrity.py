"""Tests for core/integrity.py."""

import io
from pathlib import Path
import pytest
from PIL import Image

from core.integrity import validate_jpeg, calculate_recovery_completeness


@pytest.fixture
def make_jpeg():
    """Create valid programmatic JPEG bytes."""
    def _create(size=(32, 32), color=(70, 130, 180)) -> bytes:
        img = Image.new("RGB", size, color=color)
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()
    return _create


def test_integrity_module_imported():
    """Verify integrity functions are importable."""
    assert callable(validate_jpeg)
    assert callable(calculate_recovery_completeness)


def test_valid_jpeg_integrity(tmp_path: Path, make_jpeg):
    """Test 1: Valid JPEG has all true flags and corruption_detected = False."""
    jpeg_bytes = make_jpeg()
    file_path = tmp_path / "valid.jpg"
    file_path.write_bytes(jpeg_bytes)

    res = validate_jpeg(str(file_path))

    assert res["header_valid"] is True
    assert res["footer_valid"] is True
    assert res["decodable"] is True
    assert res["structure_valid"] is True
    assert res["corruption_detected"] is False


def test_random_bytes_not_valid(tmp_path: Path):
    """Test 2: Random bytes are not valid and not decodable."""
    file_path = tmp_path / "random.bin"
    file_path.write_bytes(b"\xaa\xbb\xcc\xdd" * 100)

    res = validate_jpeg(str(file_path))

    assert res["header_valid"] is False
    assert res["footer_valid"] is False
    assert res["decodable"] is False
    assert res["structure_valid"] is False
    assert res["corruption_detected"] is True


def test_missing_soi(tmp_path: Path, make_jpeg):
    """Test 3: Missing SOI marker produces header_valid = False."""
    jpeg_bytes = make_jpeg()
    # Replace initial FF D8 with 00 00
    no_soi = b"\x00\x00" + jpeg_bytes[2:]
    file_path = tmp_path / "no_soi.jpg"
    file_path.write_bytes(no_soi)

    res = validate_jpeg(str(file_path))

    assert res["header_valid"] is False
    assert res["structure_valid"] is False
    assert res["corruption_detected"] is True


def test_missing_eoi(tmp_path: Path, make_jpeg):
    """Test 4: Missing EOI marker produces footer_valid = False."""
    jpeg_bytes = make_jpeg()
    # Replace trailing FF D9 with 00 00
    no_eoi = jpeg_bytes[:-2] + b"\x00\x00"
    file_path = tmp_path / "no_eoi.jpg"
    file_path.write_bytes(no_eoi)

    res = validate_jpeg(str(file_path))

    assert res["header_valid"] is True
    assert res["footer_valid"] is False
    assert res["structure_valid"] is False
    assert res["corruption_detected"] is True


def test_corrupted_jpeg_not_fully_valid(tmp_path: Path, make_jpeg):
    """Test 5: Corrupted JPEG payload is not considered fully valid."""
    jpeg_bytes = make_jpeg()
    # Scramble internal payload while keeping markers
    corrupted = jpeg_bytes[:10] + b"\x00" * (len(jpeg_bytes) - 20) + jpeg_bytes[-10:]
    file_path = tmp_path / "corrupted.jpg"
    file_path.write_bytes(corrupted)

    res = validate_jpeg(str(file_path))

    assert res["structure_valid"] is False
    assert res["corruption_detected"] is True


def test_truncated_jpeg_not_structurally_valid(tmp_path: Path, make_jpeg):
    """Test 6: Truncated JPEG is not reported as structurally valid."""
    jpeg_bytes = make_jpeg()
    truncated = jpeg_bytes[:len(jpeg_bytes) // 2]
    file_path = tmp_path / "truncated.jpg"
    file_path.write_bytes(truncated)

    res = validate_jpeg(str(file_path))

    assert res["footer_valid"] is False
    assert res["structure_valid"] is False
    assert res["corruption_detected"] is True


def test_missing_file_raises_error():
    """Test 7: Missing file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="Evidence file not found"):
        validate_jpeg("non_existent_image.jpg")


def test_empty_file_invalid(tmp_path: Path):
    """Test 8: Empty file returns invalid result and corruption_detected = True."""
    file_path = tmp_path / "empty.jpg"
    file_path.write_bytes(b"")

    res = validate_jpeg(str(file_path))

    assert res["header_valid"] is False
    assert res["footer_valid"] is False
    assert res["decodable"] is False
    assert res["structure_valid"] is False
    assert res["corruption_detected"] is True


def test_recovery_completeness_calculation():
    """Test 9: Recovery completeness formulas and clamping."""
    assert calculate_recovery_completeness(100, 100) == 1.0
    assert calculate_recovery_completeness(50, 100) == 0.5
    assert calculate_recovery_completeness(0, 100) == 0.0
    assert calculate_recovery_completeness(150, 100) == 1.0
    assert calculate_recovery_completeness(-10, 100) == 0.0


def test_recovery_completeness_invalid_expected_size():
    """Test 10: expected_size <= 0 raises ValueError."""
    with pytest.raises(ValueError, match="expected_size must be positive"):
        calculate_recovery_completeness(100, 0)

    with pytest.raises(ValueError, match="expected_size must be positive"):
        calculate_recovery_completeness(100, -50)
