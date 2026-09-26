"""Tests for core/reconstruction.py."""

import hashlib
import io
from pathlib import Path
import pytest
from PIL import Image

from core.reconstruction import reconstruct_artifact


@pytest.fixture
def make_jpeg():
    """Create valid programmatic JPEG bytes."""
    def _create(size=(40, 40), color=(120, 80, 220)) -> bytes:
        img = Image.new("RGB", size, color=color)
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()
    return _create


def test_reconstruction_module_imported():
    """Verify reconstruct_artifact is importable."""
    assert callable(reconstruct_artifact)


def test_two_ordered_fragments_reconstruction(tmp_path: Path, make_jpeg):
    """Test 1, 8, 9, 10, 12, 13, 14: Two ordered fragments reconstruct correctly."""
    jpeg_bytes = make_jpeg()
    orig_hash = hashlib.sha256(jpeg_bytes).hexdigest().lower()
    split_pt = len(jpeg_bytes) // 2

    chunk0_path = tmp_path / "frag_0.bin"
    chunk1_path = tmp_path / "frag_1.bin"
    chunk0_path.write_bytes(jpeg_bytes[:split_pt])
    chunk1_path.write_bytes(jpeg_bytes[split_pt:])

    fragments = [
        {"fragment_id": "FRAG-001", "chunk_index": 0, "output_path": str(chunk0_path)},
        {"fragment_id": "FRAG-002", "chunk_index": 1, "output_path": str(chunk1_path)},
    ]
    out_file = tmp_path / "reconstructed.jpg"

    res = reconstruct_artifact(fragments, str(out_file))

    # Test 1 & 14: Correct reconstruction and SHA-256 match
    assert res["status"] == "RECONSTRUCTED"
    assert res["sha256"] == orig_hash
    assert res["recovered_size_bytes"] == len(jpeg_bytes)
    assert out_file.exists()
    assert out_file.read_bytes() == jpeg_bytes

    # Test 10: Validation
    assert res["header_valid"] is True
    assert res["footer_valid"] is True
    assert res["decodable"] is True
    assert res["structural_integrity"] is True

    # Test 12 & 13: Evidence state and method
    assert res["reconstruction_method"] == "ORDERED_CONCATENATION"
    assert res["evidence_state"] == "RECONSTRUCTED"
    assert res["fragment_ids"] == ["FRAG-001", "FRAG-002"]


def test_three_ordered_fragments_reconstruction(tmp_path: Path, make_jpeg):
    """Test 2: Three ordered fragments reconstruct correctly."""
    jpeg_bytes = make_jpeg()
    orig_hash = hashlib.sha256(jpeg_bytes).hexdigest().lower()
    p1 = len(jpeg_bytes) // 3
    p2 = 2 * len(jpeg_bytes) // 3

    c0 = tmp_path / "c0.bin"
    c1 = tmp_path / "c1.bin"
    c2 = tmp_path / "c2.bin"
    c0.write_bytes(jpeg_bytes[:p1])
    c1.write_bytes(jpeg_bytes[p1:p2])
    c2.write_bytes(jpeg_bytes[p2:])

    fragments = [
        {"fragment_id": "F-0", "chunk_index": 0, "output_path": str(c0)},
        {"fragment_id": "F-1", "chunk_index": 1, "output_path": str(c1)},
        {"fragment_id": "F-2", "chunk_index": 2, "output_path": str(c2)},
    ]
    out_file = tmp_path / "three_recon.jpg"

    res = reconstruct_artifact(fragments, str(out_file))

    assert res["status"] == "RECONSTRUCTED"
    assert res["sha256"] == orig_hash
    assert res["structural_integrity"] is True
    assert res["fragment_count"] == 3


def test_fragment_order_respected_via_chunk_index(tmp_path: Path, make_jpeg):
    """Test 3: Fragments passed in reverse or scrambled order are sorted by chunk_index."""
    jpeg_bytes = make_jpeg()
    orig_hash = hashlib.sha256(jpeg_bytes).hexdigest().lower()
    p1 = len(jpeg_bytes) // 3
    p2 = 2 * len(jpeg_bytes) // 3

    c0 = tmp_path / "c0.bin"
    c1 = tmp_path / "c1.bin"
    c2 = tmp_path / "c2.bin"
    c0.write_bytes(jpeg_bytes[:p1])
    c1.write_bytes(jpeg_bytes[p1:p2])
    c2.write_bytes(jpeg_bytes[p2:])

    # Scrambled order: index 2, index 0, index 1
    scrambled = [
        {"fragment_id": "F-2", "chunk_index": 2, "output_path": str(c2)},
        {"fragment_id": "F-0", "chunk_index": 0, "output_path": str(c0)},
        {"fragment_id": "F-1", "chunk_index": 1, "output_path": str(c1)},
    ]
    out_file = tmp_path / "scrambled_recon.jpg"

    res = reconstruct_artifact(scrambled, str(out_file))

    assert res["status"] == "RECONSTRUCTED"
    assert res["sha256"] == orig_hash
    assert res["fragment_ids"] == ["F-0", "F-1", "F-2"]


def test_missing_fragment_produces_partial_status(tmp_path: Path, make_jpeg):
    """Test 4: Missing chunk produces PARTIAL status and does not falsely validate."""
    jpeg_bytes = make_jpeg()
    split_pt = len(jpeg_bytes) // 2

    c0 = tmp_path / "only_c0.bin"
    c0.write_bytes(jpeg_bytes[:split_pt])

    # Only chunk 0 is present, chunk 1 is missing
    fragments = [
        {"fragment_id": "F-0", "chunk_index": 0, "output_path": str(c0)},
    ]
    out_file = tmp_path / "partial_recon.jpg"

    # With total_expected_chunks=2 specified
    res = reconstruct_artifact(fragments, str(out_file), total_expected_chunks=2)

    assert res["status"] == "PARTIAL"
    assert res["structural_integrity"] is False
    assert res["footer_valid"] is False


def test_missing_output_path_rejected(tmp_path: Path):
    """Test 5: Missing or empty output_path in fragment metadata is rejected."""
    fragments = [
        {"fragment_id": "F-0", "chunk_index": 0, "output_path": ""},
    ]
    with pytest.raises(ValueError, match="missing valid output_path"):
        reconstruct_artifact(fragments, str(tmp_path / "out.jpg"))


def test_nonexistent_fragment_file_rejected(tmp_path: Path):
    """Test 6: Nonexistent fragment file raises FileNotFoundError."""
    fragments = [
        {"fragment_id": "F-0", "chunk_index": 0, "output_path": str(tmp_path / "nonexistent.bin")},
    ]
    with pytest.raises(FileNotFoundError, match="Fragment file not found"):
        reconstruct_artifact(fragments, str(tmp_path / "out.jpg"))


def test_empty_fragment_list_rejected(tmp_path: Path):
    """Test 7: Empty fragment list raises ValueError."""
    with pytest.raises(ValueError, match="Fragment list cannot be empty"):
        reconstruct_artifact([], str(tmp_path / "out.jpg"))


def test_duplicate_fragment_handled_conservatively(tmp_path: Path, make_jpeg):
    """Test 11: Duplicate fragment scenario results in UNRELIABLE status without double-counting."""
    jpeg_bytes = make_jpeg()
    split_pt = len(jpeg_bytes) // 2

    c0 = tmp_path / "dup_c0.bin"
    c1 = tmp_path / "dup_c1.bin"
    c0.write_bytes(jpeg_bytes[:split_pt])
    c1.write_bytes(jpeg_bytes[split_pt:])

    # Duplicate chunk 1 injected
    fragments = [
        {"fragment_id": "F-0", "chunk_index": 0, "output_path": str(c0)},
        {"fragment_id": "F-1A", "chunk_index": 1, "output_path": str(c1)},
        {"fragment_id": "F-1B", "chunk_index": 1, "output_path": str(c1)},
    ]
    out_file = tmp_path / "duplicate_recon.jpg"

    res = reconstruct_artifact(fragments, str(out_file))

    assert res["status"] == "UNRELIABLE"
    assert res["structural_integrity"] is False
