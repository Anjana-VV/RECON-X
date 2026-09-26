"""Tests for core/scanner.py."""

import hashlib
import json
from pathlib import Path
import pytest
from PIL import Image
import jsonschema

from core.scanner import scan_controlled_fragments, scan_evidence


@pytest.fixture
def make_jpeg():
    """Factory fixture to create programmatic valid JPEG bytes."""
    def _create(size=(32, 32), color=(200, 100, 50)) -> bytes:
        import io
        img = Image.new("RGB", size, color=color)
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()
    return _create


@pytest.fixture
def fragment_schema() -> dict:
    schema_path = Path(__file__).resolve().parent.parent / "schemas" / "fragment_schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_scanner_module_imported():
    """Verify scan_evidence is callable."""
    assert callable(scan_evidence)
    assert callable(scan_controlled_fragments)


def test_controlled_fragment_segments_are_derived_from_observed_gaps(tmp_path, make_jpeg):
    jpeg = make_jpeg()
    split = len(jpeg) // 2
    gap = b"\x00" * 4096
    path = tmp_path / "controlled.img"
    path.write_bytes(jpeg[:split] + gap + jpeg[split:])

    groups = scan_controlled_fragments(str(path))

    assert list(groups) == ["FRAG-001"]
    chunks = groups["FRAG-001"]
    assert [chunk["chunk_index"] for chunk in chunks] == [0, 1]
    assert chunks[0]["offset_end"] < chunks[1]["offset_start"]
    assert chunks[0]["data"] + chunks[1]["data"] == jpeg


def test_single_jpeg_embedded_in_random_binary(tmp_path: Path, make_jpeg, fragment_schema):
    """Test 1: One valid JPEG embedded in random binary yields one candidate."""
    jpeg_bytes = make_jpeg()
    noise_prefix = b"\x12\x34\x56\x78" * 16  # 64 bytes
    noise_suffix = b"\x9a\xbc\xde\xf0" * 16  # 64 bytes
    evidence = noise_prefix + jpeg_bytes + noise_suffix

    file_path = tmp_path / "single_embedded.bin"
    file_path.write_bytes(evidence)

    candidates = scan_evidence(str(file_path))

    assert len(candidates) == 1
    cand = candidates[0]
    jsonschema.validate(instance=cand, schema=fragment_schema)

    assert cand["fragment_id"] == "FRAG-001"
    assert cand["offset_start"] == 64
    assert cand["offset_end"] == 64 + len(jpeg_bytes)
    assert cand["size_bytes"] == len(jpeg_bytes)
    assert cand["sha256"] == hashlib.sha256(jpeg_bytes).hexdigest().lower()
    assert cand["header_detected"] is True
    assert cand["footer_detected"] is True
    assert cand["status"] == "CANDIDATE"


def test_multiple_jpegs_embedded_in_binary(tmp_path: Path, make_jpeg, fragment_schema):
    """Test 2 & 10: Multiple JPEGs in binary yield deterministic ordered candidates."""
    jpeg1 = make_jpeg(size=(30, 30), color=(10, 20, 30))
    jpeg2 = make_jpeg(size=(40, 40), color=(40, 50, 60))
    jpeg3 = make_jpeg(size=(50, 50), color=(70, 80, 90))

    padding = b"\x00" * 128
    evidence = padding + jpeg1 + padding + jpeg2 + padding + jpeg3 + padding

    file_path = tmp_path / "multi_embedded.bin"
    file_path.write_bytes(evidence)

    candidates = scan_evidence(str(file_path))

    assert len(candidates) == 3
    for cand in candidates:
        jsonschema.validate(instance=cand, schema=fragment_schema)

    assert [c["fragment_id"] for c in candidates] == ["FRAG-001", "FRAG-002", "FRAG-003"]

    # Offsets and sizes
    o1 = 128
    e1 = o1 + len(jpeg1)
    assert candidates[0]["offset_start"] == o1
    assert candidates[0]["offset_end"] == e1
    assert candidates[0]["size_bytes"] == len(jpeg1)

    o2 = e1 + 128
    e2 = o2 + len(jpeg2)
    assert candidates[1]["offset_start"] == o2
    assert candidates[1]["offset_end"] == e2
    assert candidates[1]["size_bytes"] == len(jpeg2)

    o3 = e2 + 128
    e3 = o3 + len(jpeg3)
    assert candidates[2]["offset_start"] == o3
    assert candidates[2]["offset_end"] == e3
    assert candidates[2]["size_bytes"] == len(jpeg3)


def test_jpeg_at_nonzero_offset(tmp_path: Path, make_jpeg):
    """Test 3: JPEG starts at non-zero offset has correct offset_start."""
    jpeg_bytes = make_jpeg()
    offset = 4096
    evidence = (b"\xaa" * offset) + jpeg_bytes

    file_path = tmp_path / "nonzero_offset.bin"
    file_path.write_bytes(evidence)

    candidates = scan_evidence(str(file_path))

    assert len(candidates) == 1
    assert candidates[0]["offset_start"] == 4096


def test_correct_offset_end_and_size(tmp_path: Path, make_jpeg):
    """Test 4 & 5: Correct offset_end (one byte after EOI) and size = end - start."""
    jpeg_bytes = make_jpeg()
    file_path = tmp_path / "exact_bounds.bin"
    file_path.write_bytes(b"\x55" * 100 + jpeg_bytes + b"\x55" * 100)

    candidates = scan_evidence(str(file_path))
    assert len(candidates) == 1
    cand = candidates[0]

    assert cand["offset_end"] == 100 + len(jpeg_bytes)
    assert cand["size_bytes"] == cand["offset_end"] - cand["offset_start"]
    assert cand["size_bytes"] == len(jpeg_bytes)


def test_candidate_sha256_correctness(tmp_path: Path, make_jpeg):
    """Test 6: Candidate sha256 matches exact hash of sliced candidate bytes."""
    jpeg_bytes = make_jpeg()
    file_path = tmp_path / "candidate_hash.bin"
    file_path.write_bytes(b"\x00" * 50 + jpeg_bytes + b"\x00" * 50)

    candidates = scan_evidence(str(file_path))
    assert len(candidates) == 1

    expected_hash = hashlib.sha256(jpeg_bytes).hexdigest().lower()
    assert candidates[0]["sha256"] == expected_hash


def test_random_binary_no_jpeg(tmp_path: Path):
    """Test 7: Random binary with no JPEG markers yields empty candidate list."""
    file_path = tmp_path / "random_binary.bin"
    file_path.write_bytes(bytes(i % 251 for i in range(10000)))  # No FF D8

    candidates = scan_evidence(str(file_path))
    assert candidates == []


def test_soi_without_eoi_partial_candidate(tmp_path: Path, make_jpeg, fragment_schema):
    """Test 8: SOI without EOI produces a PARTIAL candidate."""
    full_jpeg = make_jpeg()
    # Truncate before the last 2 bytes (strip EOI)
    truncated = full_jpeg[:-2]

    file_path = tmp_path / "truncated_soi.bin"
    file_path.write_bytes(b"\x00" * 32 + truncated)

    candidates = scan_evidence(str(file_path))

    assert len(candidates) == 1
    cand = candidates[0]
    jsonschema.validate(instance=cand, schema=fragment_schema)

    assert cand["header_detected"] is True
    assert cand["footer_detected"] is False
    assert cand["status"] == "PARTIAL"
    assert cand["offset_start"] == 32
    assert cand["offset_end"] == 32 + len(truncated)


def test_eoi_before_soi_ignored(tmp_path: Path, make_jpeg):
    """Test 9: EOI occurring before SOI does not produce a false candidate."""
    jpeg_bytes = make_jpeg()
    # Prepend an orphan EOI marker
    evidence = b"\x00" * 10 + b"\xff\xd9" + b"\x00" * 10 + jpeg_bytes

    file_path = tmp_path / "orphan_eoi.bin"
    file_path.write_bytes(evidence)

    candidates = scan_evidence(str(file_path))

    # Should detect only the valid JPEG that follows
    assert len(candidates) == 1
    assert candidates[0]["offset_start"] == 22
    assert candidates[0]["status"] == "CANDIDATE"


def test_missing_evidence_file_raises_error():
    """Verify scan_evidence raises FileNotFoundError for missing path."""
    with pytest.raises(FileNotFoundError, match="Evidence file not found"):
        scan_evidence("non_existent_disk_image.img")
