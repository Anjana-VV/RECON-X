"""Tests for dataset/damage_engine.py."""

import hashlib
import io
import os
from pathlib import Path
import pytest
from PIL import Image

from dataset.damage_engine import damage, ALLOWED_MODES


@pytest.fixture
def sample_jpeg(tmp_path: Path) -> Path:
    """Create a minimal programmatic valid JPEG file."""
    jpeg_path = tmp_path / "test_sample.jpg"
    img = Image.new("RGB", (64, 64), color=(100, 150, 200))
    img.save(jpeg_path, format="JPEG")
    return jpeg_path


def test_intact_mode_returns_identical_bytes(sample_jpeg: Path):
    """Test 1: intact mode returns identical bytes and valid metadata."""
    original_bytes = sample_jpeg.read_bytes()
    damaged_bytes, meta = damage(str(sample_jpeg), "intact")

    assert damaged_bytes == original_bytes
    assert meta["damage_type"] == "intact"
    assert meta["recoverable"] is True
    assert meta["original_size_bytes"] == len(original_bytes)
    assert meta["chunks"] == []
    assert meta["deleted_bytes"] == 0
    assert meta["corrupted_bytes"] == 0


def test_split_mode_creates_correct_ordered_chunks(sample_jpeg: Path):
    """Test 2: split mode creates correct ordered chunks for 2 and 3 chunks."""
    original_bytes = sample_jpeg.read_bytes()
    orig_len = len(original_bytes)

    # 2-chunk split
    damaged_bytes_2, meta_2 = damage(str(sample_jpeg), "split", num_chunks=2)
    assert damaged_bytes_2 == original_bytes
    assert meta_2["damage_type"] == "split"
    assert meta_2["recoverable"] is True
    assert len(meta_2["chunks"]) == 2
    assert meta_2["chunks"][0]["original_offset_start"] == 0
    assert meta_2["chunks"][0]["original_offset_end"] == meta_2["chunks"][1]["original_offset_start"]
    assert meta_2["chunks"][1]["original_offset_end"] == orig_len
    assert meta_2["chunks"][0]["size_bytes"] + meta_2["chunks"][1]["size_bytes"] == orig_len

    # 3-chunk split
    damaged_bytes_3, meta_3 = damage(str(sample_jpeg), "split", num_chunks=3)
    assert damaged_bytes_3 == original_bytes
    assert len(meta_3["chunks"]) == 3
    assert meta_3["chunks"][0]["original_offset_start"] == 0
    assert meta_3["chunks"][1]["original_offset_start"] == meta_3["chunks"][0]["original_offset_end"]
    assert meta_3["chunks"][2]["original_offset_start"] == meta_3["chunks"][1]["original_offset_end"]
    assert meta_3["chunks"][2]["original_offset_end"] == orig_len


def test_corrupted_mode_changes_bytes_preserves_size(sample_jpeg: Path):
    """Test 3: corrupted mode changes bytes but preserves file size and markers."""
    original_bytes = sample_jpeg.read_bytes()
    damaged_bytes, meta = damage(str(sample_jpeg), "corrupted")

    assert len(damaged_bytes) == len(original_bytes)
    assert damaged_bytes != original_bytes
    assert meta["damage_type"] == "corrupted"
    assert meta["recoverable"] is True
    assert meta["corrupted_bytes"] > 0

    # SOI and EOI markers must remain intact
    assert damaged_bytes[:2] == b"\xff\xd8"
    assert damaged_bytes[-2:] == b"\xff\xd9"

    # Only corruption_range should differ
    c_start = meta["corruption_range"]["start"]
    c_end = meta["corruption_range"]["end"]
    assert damaged_bytes[:c_start] == original_bytes[:c_start]
    assert damaged_bytes[c_end:] == original_bytes[c_end:]
    assert damaged_bytes[c_start:c_end] != original_bytes[c_start:c_end]


def test_duplicated_mode_produces_duplication_metadata(sample_jpeg: Path):
    """Test 4: duplicated mode produces expected duplication metadata and expanded bytes."""
    original_bytes = sample_jpeg.read_bytes()
    damaged_bytes, meta = damage(str(sample_jpeg), "duplicated")

    assert len(damaged_bytes) > len(original_bytes)
    assert meta["damage_type"] == "duplicated"
    assert meta["recoverable"] is True
    assert meta["duplicated_bytes"] > 0
    assert "duplicate_range" in meta
    assert meta["duplicate_range"]["end"] - meta["duplicate_range"]["start"] == meta["duplicated_bytes"]


def test_deleted_unavailable_returns_no_bytes(sample_jpeg: Path):
    """Test 5: deleted_unavailable returns empty bytes and recoverable=False."""
    damaged_bytes, meta = damage(str(sample_jpeg), "deleted_unavailable")

    assert damaged_bytes == b""
    assert meta["damage_type"] == "deleted_unavailable"
    assert meta["recoverable"] is False
    assert meta["deleted_bytes"] == sample_jpeg.stat().st_size


def test_invalid_mode_raises_value_error(sample_jpeg: Path):
    """Test 6: invalid mode raises ValueError."""
    with pytest.raises(ValueError, match="Invalid mode 'unknown_mode'"):
        damage(str(sample_jpeg), "unknown_mode")


def test_missing_source_raises_file_not_found(tmp_path: Path):
    """Test 7: missing source file raises FileNotFoundError."""
    missing_path = tmp_path / "non_existent.jpg"
    with pytest.raises(FileNotFoundError, match="Original file not found"):
        damage(str(missing_path), "intact")


def test_original_sha256_is_correct(sample_jpeg: Path):
    """Test 8: original SHA-256 matches actual file hash."""
    expected_hash = hashlib.sha256(sample_jpeg.read_bytes()).hexdigest()
    _, meta = damage(str(sample_jpeg), "intact")

    assert meta["original_sha256"] == expected_hash


def test_non_jpeg_file_rejected(tmp_path: Path):
    """Verify non-JPEG binary files are rejected."""
    fake_file = tmp_path / "not_a_jpeg.txt"
    fake_file.write_bytes(b"This is just plain text, not a JPEG.")
    with pytest.raises(ValueError, match="File is not a valid JPEG"):
        damage(str(fake_file), "intact")
