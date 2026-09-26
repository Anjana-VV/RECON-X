"""Evidence disk image generator and ground truth builder."""

import json
import os
from pathlib import Path
from typing import Optional

from dataset.damage_engine import damage

PADDING_SIZE = 4096
PADDING_PATTERN = b"\x00" * PADDING_SIZE

DEFAULT_SCENARIOS = [
    ("intact", 0),
    ("split", 2),
    ("split", 3),
    ("corrupted", 0),
    ("corrupted", 0),
    ("duplicated", 0),
    ("deleted_unavailable", 0),
]


def generate_dataset(
    originals_dir: Optional[Path | str] = None,
    output_dir: Optional[Path | str] = None,
    ground_truth_path: Optional[Path | str] = None,
) -> dict:
    """Generate controlled evidence image and ground truth metadata.

    Args:
        originals_dir: Directory containing original JPEG images.
        output_dir: Directory where incident_disk.img will be written.
        ground_truth_path: File path where ground_truth.json will be written.

    Returns:
        dict: The generated ground truth data dictionary.

    Raises:
        RuntimeError: If originals_dir has no valid JPEG images.
    """
    base_dir = Path(__file__).resolve().parent
    orig_dir = Path(originals_dir) if originals_dir else base_dir / "originals"
    out_dir = Path(output_dir) if output_dir else base_dir / "generated"
    gt_path = Path(ground_truth_path) if ground_truth_path else base_dir / "ground_truth.json"

    if not orig_dir.exists():
        raise RuntimeError(f"Originals directory does not exist: {orig_dir}")

    # Discover and sort JPEG originals for determinism
    valid_extensions = {".jpg", ".jpeg", ".JPG", ".JPEG"}
    jpeg_files = sorted([f for f in orig_dir.iterdir() if f.is_file() and f.suffix in valid_extensions])

    if not jpeg_files:
        raise RuntimeError(
            f"No JPEG files found in '{orig_dir}'. Please place at least 7 JPEG original images in this directory."
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    evidence_img_path = out_dir / "incident_disk.img"

    # Build scenario assignments
    scenarios = []
    num_originals = len(jpeg_files)

    for i, (mode, chunks_count) in enumerate(DEFAULT_SCENARIOS):
        orig_file = jpeg_files[i % num_originals]
        reused = i >= num_originals
        scenarios.append((orig_file, mode, chunks_count, reused))

    # If more than 7 originals exist, include extras as intact
    if num_originals > len(DEFAULT_SCENARIOS):
        for i in range(len(DEFAULT_SCENARIOS), num_originals):
            scenarios.append((jpeg_files[i], "intact", 0, False))

    records = []
    current_offset = PADDING_SIZE  # Initial 4096-byte padding so JPEGs don't start at offset 0

    with open(evidence_img_path, "wb") as img_file:
        # Write initial padding
        img_file.write(PADDING_PATTERN)

        for idx, (orig_file, mode, chunks_count, reused) in enumerate(scenarios):
            record_id = f"GT-{idx + 1:03d}"
            damaged_bytes, meta = damage(str(orig_file), mode, num_chunks=chunks_count if chunks_count else 2)

            if mode == "deleted_unavailable":
                ev_start = None
                ev_end = None
                chunks_info = []
                corr_range = None
                dup_range = None
            elif mode == "split":
                ev_start = current_offset
                chunks_info = []
                for chunk in meta.get("chunks", []):
                    c_orig_start = chunk["original_offset_start"]
                    c_orig_end = chunk["original_offset_end"]
                    chunk_bytes = damaged_bytes[c_orig_start:c_orig_end]

                    c_start = current_offset
                    c_end = current_offset + len(chunk_bytes)
                    img_file.write(chunk_bytes)
                    current_offset = c_end

                    chunks_info.append({
                        "chunk_index": chunk["chunk_index"],
                        "offset_start": c_start,
                        "offset_end": c_end,
                        "size_bytes": len(chunk_bytes),
                    })

                    # Inter-chunk deterministic padding (4096 bytes of non-JPEG zeros)
                    img_file.write(PADDING_PATTERN)
                    current_offset += PADDING_SIZE

                ev_end = chunks_info[-1]["offset_end"]
                corr_range = None
                dup_range = None
            else:
                ev_start = current_offset
                ev_end = current_offset + len(damaged_bytes)
                img_file.write(damaged_bytes)
                current_offset = ev_end

                # Inter-region padding
                img_file.write(PADDING_PATTERN)
                current_offset += PADDING_SIZE

                chunks_info = []
                corr_range = None
                if "corruption_range" in meta:
                    corr_range = {
                        "start": ev_start + meta["corruption_range"]["start"],
                        "end": ev_start + meta["corruption_range"]["end"],
                    }

                dup_range = None
                if "duplicate_range" in meta:
                    dup_range = {
                        "start": ev_start + meta["duplicate_range"]["start"],
                        "end": ev_start + meta["duplicate_range"]["end"],
                    }

            record = {
                "record_id": record_id,
                "original_file": meta["original_file"],
                "original_sha256": meta["original_sha256"],
                "original_size_bytes": meta["original_size_bytes"],
                "damage_type": meta["damage_type"],
                "recoverable": meta["recoverable"],
                "evidence_offset_start": ev_start,
                "evidence_offset_end": ev_end,
                "chunks": chunks_info,
                "corrupted_bytes": meta.get("corrupted_bytes", 0),
                "corruption_range": corr_range,
                "duplicated_bytes": meta.get("duplicated_bytes", 0),
                "duplicate_range": dup_range,
                "deleted_bytes": meta.get("deleted_bytes", 0),
                "reused_original": reused,
            }
            records.append(record)

    ground_truth = {
        "dataset_version": "1.0",
        "evidence_file": "incident_disk.img",
        "records": records,
    }

    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2)

    return ground_truth


def main() -> None:
    """CLI entrypoint for dataset generation."""
    print("Generating RECON-X evidence image and ground truth...")
    gt = generate_dataset()
    print(f"Generated {len(gt['records'])} scenario records successfully.")


if __name__ == "__main__":
    main()
