"""Controlled reconstruction for fragmented JPEG artifacts."""

import hashlib
from pathlib import Path
from typing import Optional

from core.integrity import validate_jpeg


def reconstruct_artifact(
    fragments: list[dict],
    output_path: str,
    total_expected_chunks: Optional[int] = None,
) -> dict:
    """Reconstruct a JPEG from controlled ordered fragments.

    Performs deterministic ordered concatenation of verified JPEG fragments.
    Strictly forbids guessing, byte interpolation, or hallucinating missing data.

    Args:
        fragments: List of fragment metadata dicts. Each must contain:
                   - "output_path": Path to fragment file on disk
                   - "chunk_index": Integer index indicating sequence position
                   - "fragment_id": String identifier
        output_path: Target path to write the reconstructed artifact.
        total_expected_chunks: Optional integer representing expected chunk count.

    Returns:
        dict: Forensic reconstruction summary:
              {
                  "status": "RECONSTRUCTED" | "PARTIAL" | "UNRELIABLE" | "UNRECOVERABLE",
                  "output_path": str,
                  "fragment_ids": list[str],
                  "fragment_count": int,
                  "recovered_size_bytes": int,
                  "sha256": str,
                  "header_valid": bool,
                  "footer_valid": bool,
                  "decodable": bool,
                  "structural_integrity": bool,
                  "reconstruction_method": "ORDERED_CONCATENATION",
                  "evidence_state": "RECONSTRUCTED",
              }

    Raises:
        ValueError: If fragments is empty, lacks required keys, or output_path is missing.
        FileNotFoundError: If any fragment file does not exist on disk.
    """
    if not fragments:
        raise ValueError("Fragment list cannot be empty")
    if not output_path:
        raise ValueError("output_path must be specified")

    # Validate each fragment contract
    for frag in fragments:
        if not isinstance(frag, dict):
            raise ValueError(f"Fragment must be a dictionary, got {type(frag).__name__}")
        frag_out = frag.get("output_path")
        if not frag_out:
            raise ValueError(f"Fragment {frag.get('fragment_id', 'UNKNOWN')} missing valid output_path")
        f_path = Path(frag_out)
        if not f_path.is_file():
            raise FileNotFoundError(f"Fragment file not found: {frag_out}")
        if "chunk_index" not in frag:
            raise ValueError(f"Fragment {frag.get('fragment_id', 'UNKNOWN')} missing chunk_index")

    # Check for duplicate fragments (by chunk_index or explicit duplicate flag)
    indices = [f["chunk_index"] for f in fragments]
    ids = [f.get("fragment_id") for f in fragments]
    has_duplicate_index = len(indices) != len(set(indices))
    has_duplicate_id = len(ids) != len(set(ids))
    has_duplicate_flag = any(f.get("is_duplicate", False) for f in fragments)
    duplicate_detected = bool(has_duplicate_index or has_duplicate_id or has_duplicate_flag)

    # Sort fragments deterministically by chunk_index
    sorted_frags = sorted(fragments, key=lambda f: f["chunk_index"])
    sorted_indices = [f["chunk_index"] for f in sorted_frags]

    # Check for missing chunks in ordered sequence
    if total_expected_chunks is not None:
        expected_indices = list(range(total_expected_chunks))
        has_missing = (sorted_indices != expected_indices)
    else:
        # Without total count, check if sequence begins at 0 and is contiguous
        expected_indices = list(range(len(sorted_indices)))
        has_missing = (sorted_indices != expected_indices)

    # Concatenate exact bytes in chunk_index order without fabricating missing bytes
    chunk_buffers = []
    seen_indices = set()
    for f in sorted_frags:
        idx = f["chunk_index"]
        if idx in seen_indices:
            # Avoid double-counting duplicate chunk in byte assembly
            continue
        seen_indices.add(idx)
        chunk_buffers.append(Path(f["output_path"]).read_bytes())

    reconstructed_bytes = b"".join(chunk_buffers)

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_bytes(reconstructed_bytes)

    recovered_size = len(reconstructed_bytes)
    reconstructed_sha256 = hashlib.sha256(reconstructed_bytes).hexdigest().lower()

    # Validate reconstructed artifact via integrity engine
    val = validate_jpeg(str(out_file))

    # Determine explainable reconstruction status
    if duplicate_detected:
        status = "UNRELIABLE"
        structural_integrity = False
    elif has_missing:
        status = "PARTIAL"
        structural_integrity = False
    elif val["structure_valid"] and val["decodable"]:
        status = "RECONSTRUCTED"
        structural_integrity = True
    else:
        status = "UNRELIABLE"
        structural_integrity = False

    return {
        "status": status,
        "output_path": str(out_file),
        "fragment_ids": [f.get("fragment_id", "") for f in sorted_frags],
        "fragment_count": len(sorted_frags),
        "recovered_size_bytes": recovered_size,
        "sha256": reconstructed_sha256,
        "header_valid": val["header_valid"],
        "footer_valid": val["footer_valid"],
        "decodable": val["decodable"],
        "structural_integrity": structural_integrity,
        "reconstruction_method": "ORDERED_CONCATENATION",
        "evidence_state": "RECONSTRUCTED",
    }
