"""JPEG carving from binary evidence with structural validation."""

import hashlib
import os
from pathlib import Path
from PIL import Image

from core.scanner import scan_evidence, SOI_MARKER, EOI_MARKER


def find_jpeg_markers(data: bytes) -> list[tuple[int, int]]:
    """Find JPEG SOI/EOI candidate ranges.

    Args:
        data: Raw binary bytes to inspect.

    Returns:
        list[tuple[int, int]]: List of (start_offset, end_offset) tuples in
                               ascending order. start_offset points to FF D8,
                               end_offset is one position after FF D9.
                               Incomplete SOIs without EOIs are excluded.
    """
    ranges: list[tuple[int, int]] = []
    pos = 0
    data_len = len(data)

    while pos < data_len:
        soi_idx = data.find(SOI_MARKER, pos)
        if soi_idx == -1:
            break

        next_soi_idx = data.find(SOI_MARKER, soi_idx + 2)
        next_eoi_idx = data.find(EOI_MARKER, soi_idx + 2)

        if next_eoi_idx == -1:
            # SOI without subsequent EOI: incomplete marker pair, do not include
            if next_soi_idx != -1:
                pos = next_soi_idx
            else:
                break
        elif next_soi_idx != -1 and next_soi_idx < next_eoi_idx:
            # Another SOI appears before any EOI -> first SOI is truncated
            pos = next_soi_idx
        else:
            end_offset = next_eoi_idx + 2  # One position after FF D9
            ranges.append((soi_idx, end_offset))
            pos = end_offset

    return ranges


def _validate_jpeg_candidate(file_path: Path) -> tuple[bool, bool]:
    """Validate JPEG structure and decodability with Pillow.

    Args:
        file_path: Path to the carved JPEG file.

    Returns:
        tuple[bool, bool]: (structure_valid, decodable)
    """
    try:
        # Step 1: Open and verify structure (headers, markers)
        with Image.open(file_path) as img:
            if img.format != "JPEG":
                return False, False
            img.verify()

        # Step 2: Reopen and attempt pixel decoding (verify consumes image state)
        with Image.open(file_path) as img:
            img.load()

        return True, True
    except Exception:
        # Check if basic open succeeded but decode failed
        try:
            with Image.open(file_path) as img:
                if img.format == "JPEG":
                    return True, False
        except Exception:
            pass
        return False, False


def carve_jpeg(
    evidence_path: str,
    output_dir: str
) -> list[dict]:
    """Carve candidate JPEG artifacts from evidence.

    Extracts candidate byte regions, saves them as deterministic recovered files,
    validates structural integrity and decodability with Pillow, and assigns
    definitive forensic status (VALIDATED, REJECTED, or PARTIAL).

    Args:
        evidence_path: Path to the binary evidence image file.
        output_dir: Target directory to save carved JPEG files.

    Returns:
        list[dict]: List of carved fragment dictionaries conforming to fragment_schema.json.

    Raises:
        FileNotFoundError: If evidence_path does not exist.
        IsADirectoryError: If evidence_path is a directory.
    """
    ev_path = Path(evidence_path)
    if not ev_path.exists():
        raise FileNotFoundError(f"Evidence file not found: {evidence_path}")
    if ev_path.is_dir():
        raise IsADirectoryError(f"Evidence path is a directory: {evidence_path}")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(ev_path, "rb") as f:
        data = f.read()

    candidates = scan_evidence(evidence_path)
    carved_results: list[dict] = []

    for idx, cand in enumerate(candidates, start=1):
        cand_start = cand["offset_start"]
        cand_end = cand["offset_end"]
        cand_bytes = data[cand_start:cand_end]

        out_filename = f"recovered_{idx:03d}.jpg"
        out_filepath = out_dir / out_filename
        out_filepath.write_bytes(cand_bytes)

        actual_sha256 = hashlib.sha256(cand_bytes).hexdigest().lower()

        # Determine validation status
        if not cand.get("footer_detected", False) or cand.get("status") == "PARTIAL":
            status = "PARTIAL"
        else:
            structure_valid, decodable = _validate_jpeg_candidate(out_filepath)
            if structure_valid and decodable:
                status = "VALIDATED"
            else:
                status = "REJECTED"

        fragment = {
            "fragment_id": cand["fragment_id"],
            "offset_start": cand_start,
            "offset_end": cand_end,
            "size_bytes": len(cand_bytes),
            "predicted_type": cand["predicted_type"],
            "classifier_confidence": cand["classifier_confidence"],
            "sha256": actual_sha256,
            "header_detected": cand["header_detected"],
            "footer_detected": cand["footer_detected"],
            "status": status,
            "output_path": str(out_filepath),
        }
        carved_results.append(fragment)

    return carved_results
