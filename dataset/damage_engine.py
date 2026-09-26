"""Damage simulation engine for controlled evidence generation."""

import hashlib
import os
from pathlib import Path

ALLOWED_MODES = {"intact", "split", "corrupted", "duplicated", "deleted_unavailable"}


def damage(original_path: str, mode: str, num_chunks: int = 2) -> tuple[bytes, dict]:
    """Apply controlled damage mode to an original JPEG file.

    Args:
        original_path: Path to the original JPEG file.
        mode: Damage mode ('intact', 'split', 'corrupted', 'duplicated', 'deleted_unavailable').
        num_chunks: Number of ordered chunks if mode is 'split' (2 or 3).

    Returns:
        tuple[bytes, dict]: (damaged_bytes, ground_truth_metadata)

    Raises:
        ValueError: If mode is unsupported or file is not a valid JPEG.
        FileNotFoundError: If original_path does not exist.
    """
    if mode not in ALLOWED_MODES:
        raise ValueError(f"Invalid mode '{mode}'. Supported modes: {sorted(ALLOWED_MODES)}")

    path = Path(original_path)
    if not path.is_file():
        raise FileNotFoundError(f"Original file not found: {original_path}")

    with open(path, "rb") as f:
        data = f.read()

    # Validate JPEG SOI (FF D8) and EOI (FF D9)
    if len(data) < 4 or not (data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9")):
        raise ValueError(f"File is not a valid JPEG: {original_path}")

    orig_sha256 = hashlib.sha256(data).hexdigest()
    orig_size = len(data)
    orig_filename = path.name

    base_meta = {
        "original_file": orig_filename,
        "original_sha256": orig_sha256,
        "original_size_bytes": orig_size,
        "chunks": [],
        "deleted_bytes": 0,
        "corrupted_bytes": 0,
        "duplicated_bytes": 0,
    }

    if mode == "intact":
        meta = {
            **base_meta,
            "damage_type": "intact",
            "recoverable": True,
        }
        return data, meta

    elif mode == "split":
        if num_chunks not in (2, 3):
            raise ValueError(f"Split mode supports only 2 or 3 chunks, got {num_chunks}")

        chunks = []
        if num_chunks == 2:
            split_pt = orig_size // 2
            boundaries = [(0, split_pt), (split_pt, orig_size)]
        else:
            p1 = orig_size // 3
            p2 = 2 * orig_size // 3
            boundaries = [(0, p1), (p1, p2), (p2, orig_size)]

        for idx, (c_start, c_end) in enumerate(boundaries):
            chunks.append({
                "chunk_index": idx,
                "original_offset_start": c_start,
                "original_offset_end": c_end,
                "size_bytes": c_end - c_start,
            })

        meta = {
            **base_meta,
            "damage_type": "split",
            "recoverable": True,
            "chunks": chunks,
        }
        return data, meta

    elif mode == "corrupted":
        # Modify a deterministic middle range, preserving SOI and EOI markers
        corrupt_len = max(8, int(orig_size * 0.05))
        # Ensure we stay well away from header and footer
        start = max(16, (orig_size // 2) - (corrupt_len // 2))
        end = min(orig_size - 16, start + corrupt_len)
        actual_corrupt_len = end - start

        # Deterministic byte perturbation (XOR with fixed pattern 0x5A)
        corrupted_slice = bytes(b ^ 0x5a for b in data[start:end])
        corrupted_data = data[:start] + corrupted_slice + data[end:]

        meta = {
            **base_meta,
            "damage_type": "corrupted",
            "recoverable": True,
            "corrupted_bytes": actual_corrupt_len,
            "corruption_range": {
                "start": start,
                "end": end,
            },
        }
        return corrupted_data, meta

    elif mode == "duplicated":
        # Create a controlled duplicate region inserted after its source location
        dup_len = max(16, int(orig_size * 0.10))
        dup_start = max(16, orig_size // 3)
        dup_end = min(orig_size - 16, dup_start + dup_len)
        actual_dup_len = dup_end - dup_start

        dup_slice = data[dup_start:dup_end]
        # Insert duplicate slice right after dup_end
        duplicated_data = data[:dup_end] + dup_slice + data[dup_end:]

        meta = {
            **base_meta,
            "damage_type": "duplicated",
            "recoverable": True,
            "duplicated_bytes": actual_dup_len,
            "duplicate_range": {
                "start": dup_end,
                "end": dup_end + actual_dup_len,
            },
        }
        return duplicated_data, meta

    elif mode == "deleted_unavailable":
        meta = {
            **base_meta,
            "damage_type": "deleted_unavailable",
            "recoverable": False,
            "deleted_bytes": orig_size,
        }
        return b"", meta

    raise ValueError(f"Unhandled mode: {mode}")
