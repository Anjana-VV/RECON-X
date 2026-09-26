"""Tests for dataset/generator.py."""

import json
from pathlib import Path
import pytest
from PIL import Image

from dataset.generator import generate_dataset


@pytest.fixture
def mock_originals_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with programmatic genuine JPEGs."""
    orig_dir = tmp_path / "mock_originals"
    orig_dir.mkdir()

    for i in range(7):
        img_path = orig_dir / f"test_img_{i+1:02d}.jpg"
        img = Image.new("RGB", (32 + i * 8, 32 + i * 8), color=((i * 35) % 255, (i * 65) % 255, (i * 95) % 255))
        img.save(img_path, format="JPEG")

    return orig_dir


def test_generator_creates_image_and_ground_truth(mock_originals_dir: Path, tmp_path: Path):
    """Tests 9, 10, 11, 12, 13: generation creates files, offsets, nulls for deleted, leaves originals intact."""
    out_dir = tmp_path / "generated"
    gt_file = tmp_path / "ground_truth.json"

    # Snapshot originals before generation
    orig_hashes_before = {f.name: f.read_bytes() for f in mock_originals_dir.glob("*.jpg")}

    gt = generate_dataset(
        originals_dir=mock_originals_dir,
        output_dir=out_dir,
        ground_truth_path=gt_file,
    )

    # Test 9: incident_disk.img created
    img_path = out_dir / "incident_disk.img"
    assert img_path.exists()
    assert img_path.stat().st_size > 0

    # Test 10: ground_truth.json created
    assert gt_file.exists()
    with open(gt_file, "r", encoding="utf-8") as f:
        loaded_gt = json.load(f)
    assert loaded_gt["dataset_version"] == "1.0"
    assert loaded_gt["evidence_file"] == "incident_disk.img"
    assert len(loaded_gt["records"]) == 7

    # Test 11: absolute evidence offsets are present and valid
    records = loaded_gt["records"]
    for rec in records:
        if rec["damage_type"] != "deleted_unavailable":
            assert isinstance(rec["evidence_offset_start"], int)
            assert isinstance(rec["evidence_offset_end"], int)
            assert rec["evidence_offset_start"] < rec["evidence_offset_end"]
            assert rec["evidence_offset_start"] >= 4096  # Initial padding

            if rec["damage_type"] == "split":
                assert len(rec["chunks"]) in (2, 3)
                for chunk in rec["chunks"]:
                    assert rec["evidence_offset_start"] <= chunk["offset_start"] < chunk["offset_end"] <= rec["evidence_offset_end"]

        # Test 12: deleted_unavailable has null evidence offsets
        else:
            assert rec["evidence_offset_start"] is None
            assert rec["evidence_offset_end"] is None
            assert rec["recoverable"] is False

    # Test 13: generator does not modify originals
    orig_hashes_after = {f.name: f.read_bytes() for f in mock_originals_dir.glob("*.jpg")}
    assert orig_hashes_before == orig_hashes_after


def test_generator_output_is_deterministic(mock_originals_dir: Path, tmp_path: Path):
    """Test 14: Running generator twice on the same originals produces byte-identical output."""
    out_dir_1 = tmp_path / "gen_1"
    gt_file_1 = tmp_path / "gt_1.json"
    generate_dataset(mock_originals_dir, out_dir_1, gt_file_1)
    img_1_bytes = (out_dir_1 / "incident_disk.img").read_bytes()
    gt_1_text = gt_file_1.read_text(encoding="utf-8")

    out_dir_2 = tmp_path / "gen_2"
    gt_file_2 = tmp_path / "gt_2.json"
    generate_dataset(mock_originals_dir, out_dir_2, gt_file_2)
    img_2_bytes = (out_dir_2 / "incident_disk.img").read_bytes()
    gt_2_text = gt_file_2.read_text(encoding="utf-8")

    assert img_1_bytes == img_2_bytes
    assert gt_1_text == gt_2_text


def test_generator_raises_on_empty_originals(tmp_path: Path):
    """Verify generator raises RuntimeError if originals directory has no JPEGs."""
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    with pytest.raises(RuntimeError, match="No JPEG files found"):
        generate_dataset(originals_dir=empty_dir, output_dir=tmp_path / "gen")
