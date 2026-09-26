"""Tests for core/hashing.py."""

import hashlib
from pathlib import Path
import pytest

from core.hashing import calculate_sha256


def test_hashing_module_imported():
    """Verify calculate_sha256 is importable."""
    assert callable(calculate_sha256)


def test_known_byte_content_sha256(tmp_path: Path):
    """Test 1: Known byte content produces expected SHA-256."""
    test_file = tmp_path / "known_content.bin"
    content = b"RECON-X Digital Evidence Test Content"
    test_file.write_bytes(content)

    expected = hashlib.sha256(content).hexdigest().lower()
    result = calculate_sha256(str(test_file))

    assert result == expected


def test_empty_file_sha256(tmp_path: Path):
    """Test 2: Empty file produces standard empty-string SHA-256."""
    empty_file = tmp_path / "empty.bin"
    empty_file.write_bytes(b"")

    expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    result = calculate_sha256(str(empty_file))

    assert result == expected


def test_larger_file_streaming_sha256(tmp_path: Path):
    """Test 3: Larger temporary file (> 1 MiB) produces correct streaming SHA-256."""
    large_file = tmp_path / "large_evidence.bin"
    # Create 2.5 MiB file to test multiple streaming chunk reads
    chunk_pattern = b"A" * (1024 * 1024) + b"B" * (1024 * 1024) + b"C" * (512 * 1024)
    large_file.write_bytes(chunk_pattern)

    expected = hashlib.sha256(chunk_pattern).hexdigest().lower()
    # Test with default and smaller chunk sizes to ensure buffer boundary integrity
    result_default = calculate_sha256(str(large_file))
    result_small_chunks = calculate_sha256(str(large_file), chunk_size=64 * 1024)

    assert result_default == expected
    assert result_small_chunks == expected


def test_missing_file_raises_file_not_found(tmp_path: Path):
    """Test 4: Missing file raises FileNotFoundError."""
    missing_file = tmp_path / "does_not_exist.bin"
    with pytest.raises(FileNotFoundError, match="Evidence file not found"):
        calculate_sha256(str(missing_file))


def test_hashing_does_not_modify_file(tmp_path: Path):
    """Test 5: Hashing does not modify file content, size, or mtime."""
    test_file = tmp_path / "unmodified.bin"
    test_data = b"Forensic Integrity Protection Buffer" * 50
    test_file.write_bytes(test_data)

    size_before = test_file.stat().st_size
    mtime_before = test_file.stat().st_mtime
    bytes_before = test_file.read_bytes()

    _ = calculate_sha256(str(test_file))

    assert test_file.stat().st_size == size_before
    assert test_file.stat().st_mtime == mtime_before
    assert test_file.read_bytes() == bytes_before
