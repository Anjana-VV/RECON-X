"""Tests for core/carving.py."""

import hashlib
import io
import json
from pathlib import Path
import pytest
from PIL import Image
import jsonschema

from core.carving import find_jpeg_markers, carve_jpeg


@pytest.fixture
def make_jpeg():
    """Create valid programmatic JPEG bytes."""
    def _create(size=(32, 32), color=(150, 75, 200)) -> bytes:
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


def test_carving_module_imported():
    """Verify carving functions are importable."""
    assert callable(find_jpeg_markers)
    assert callable(carve_jpeg)


def test_find_jpeg_markers_one_jpeg(make_jpeg):
    """Test 1: find_jpeg_markers with single embedded JPEG."""
    jpeg = make_jpeg()
    data = b"\x00" * 50 + jpeg + b"\x00" * 50
    ranges = find_jpeg_markers(data)

    assert len(ranges) == 1
    assert ranges[0] == (50, 50 + len(jpeg))


def test_find_jpeg_markers_multiple_jpegs(make_jpeg):
    """Test 2: find_jpeg_markers with multiple JPEGs in ascending order."""
    j1 = make_jpeg(size=(20, 20), color=(10, 10, 10))
    j2 = make_jpeg(size=(30, 30), color=(20, 20, 20))
    j3 = make_jpeg(size=(40, 40), color=(30, 30, 30))

    data = b"\xaa" * 20 + j1 + b"\xbb" * 30 + j2 + b"\xcc" * 40 + j3 + b"\xdd" * 50
    ranges = find_jpeg_markers(data)

    assert len(ranges) == 3
    # Check strict ascending order
    assert ranges[0][0] < ranges[0][1] < ranges[1][0] < ranges[1][1] < ranges[2][0] < ranges[2][1]
    assert ranges[0] == (20, 20 + len(j1))


def test_find_jpeg_markers_correct_offsets(make_jpeg):
    """Test 3: Start offset begins at FF D8, end offset is 1 byte after FF D9."""
    jpeg = make_jpeg()
    offset = 1024
    data = b"\x00" * offset + jpeg
    ranges = find_jpeg_markers(data)

    assert len(ranges) == 1
    start, end = ranges[0]
    assert data[start:start + 2] == b"\xff\xd8"
    assert data[end - 2:end] == b"\xff\xd9"
    assert end - start == len(jpeg)


def test_find_jpeg_markers_no_jpeg():
    """Test 4: Behavior when no JPEG markers exist."""
    data = b"\x12\x34\x56\x78" * 100
    ranges = find_jpeg_markers(data)
    assert ranges == []


def test_find_jpeg_markers_soi_without_eoi():
    """Test 5: Incomplete SOI without EOI is excluded from completed marker pairs."""
    data = b"\x00" * 20 + b"\xff\xd8" + b"incomplete data without footer"
    ranges = find_jpeg_markers(data)
    assert ranges == []


def test_carve_jpeg_extracts_correct_bytes(tmp_path: Path, make_jpeg):
    """Test 6: carve_jpeg extracts exact candidate bytes from evidence."""
    jpeg = make_jpeg()
    ev_file = tmp_path / "evidence.img"
    ev_file.write_bytes(b"\x00" * 128 + jpeg + b"\x00" * 128)

    out_dir = tmp_path / "carved"
    results = carve_jpeg(str(ev_file), str(out_dir))

    assert len(results) == 1
    carved_path = Path(results[0]["output_path"])
    assert carved_path.exists()
    assert carved_path.read_bytes() == jpeg


def test_output_jpeg_decodable_by_pillow(tmp_path: Path, make_jpeg):
    """Test 7: Output carved file can be opened and decoded by Pillow."""
    jpeg = make_jpeg(size=(50, 50), color=(100, 200, 50))
    ev_file = tmp_path / "evidence.img"
    ev_file.write_bytes(b"\x00" * 64 + jpeg)

    out_dir = tmp_path / "carved"
    results = carve_jpeg(str(ev_file), str(out_dir))

    carved_path = results[0]["output_path"]
    with Image.open(carved_path) as img:
        assert img.format == "JPEG"
        img.load()  # Decodes pixels without raising error


def test_valid_jpeg_receives_status_validated(tmp_path: Path, make_jpeg, fragment_schema):
    """Test 8: Valid JPEG candidate receives status VALIDATED and conforms to schema."""
    jpeg = make_jpeg()
    ev_file = tmp_path / "evidence.img"
    ev_file.write_bytes(b"\x00" * 100 + jpeg)

    out_dir = tmp_path / "carved"
    results = carve_jpeg(str(ev_file), str(out_dir))

    assert results[0]["status"] == "VALIDATED"
    jsonschema.validate(instance=results[0], schema=fragment_schema)


def test_invalid_marker_candidate_receives_rejected(tmp_path: Path, fragment_schema):
    """Test 9: Invalid candidate with SOI/EOI but invalid payload receives REJECTED."""
    # Construct candidate with valid markers but completely invalid JPEG structure
    fake_jpeg = b"\xff\xd8" + b"This is not a valid JPEG stream at all!" * 5 + b"\xff\xd9"
    ev_file = tmp_path / "fake_evidence.img"
    ev_file.write_bytes(b"\x00" * 50 + fake_jpeg + b"\x00" * 50)

    out_dir = tmp_path / "carved"
    results = carve_jpeg(str(ev_file), str(out_dir))

    assert len(results) == 1
    assert results[0]["status"] == "REJECTED"
    jsonschema.validate(instance=results[0], schema=fragment_schema)


def test_sha256_matches_carved_bytes(tmp_path: Path, make_jpeg):
    """Test 10: SHA-256 field in carved result matches extracted bytes exactly."""
    jpeg = make_jpeg()
    ev_file = tmp_path / "evidence.img"
    ev_file.write_bytes(b"\x00" * 40 + jpeg)

    out_dir = tmp_path / "carved"
    results = carve_jpeg(str(ev_file), str(out_dir))

    expected_hash = hashlib.sha256(jpeg).hexdigest().lower()
    assert results[0]["sha256"] == expected_hash


def test_multiple_candidates_deterministic_ids_and_names(tmp_path: Path, make_jpeg):
    """Test 11: Multiple candidates produce deterministic IDs and filenames."""
    j1 = make_jpeg(size=(25, 25), color=(1, 2, 3))
    j2 = make_jpeg(size=(35, 35), color=(4, 5, 6))

    ev_file = tmp_path / "evidence.img"
    ev_file.write_bytes(b"\x00" * 50 + j1 + b"\x00" * 50 + j2)

    out_dir = tmp_path / "carved"
    results = carve_jpeg(str(ev_file), str(out_dir))

    assert len(results) == 2
    assert results[0]["fragment_id"] == "FRAG-001"
    assert results[1]["fragment_id"] == "FRAG-002"
    assert Path(results[0]["output_path"]).name == "recovered_001.jpg"
    assert Path(results[1]["output_path"]).name == "recovered_002.jpg"


def test_output_directory_created_automatically(tmp_path: Path, make_jpeg):
    """Test 12: Output directory is automatically created if it does not exist."""
    jpeg = make_jpeg()
    ev_file = tmp_path / "evidence.img"
    ev_file.write_bytes(b"\x00" * 20 + jpeg)

    nested_out_dir = tmp_path / "deep" / "nested" / "output_dir"
    assert not nested_out_dir.exists()

    results = carve_jpeg(str(ev_file), str(nested_out_dir))

    assert nested_out_dir.exists()
    assert (nested_out_dir / "recovered_001.jpg").exists()
