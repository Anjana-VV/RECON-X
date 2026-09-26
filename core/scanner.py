"""Binary evidence scanner for JPEG candidate markers."""

import hashlib
from pathlib import Path

SOI_MARKER = b"\xff\xd8"
EOI_MARKER = b"\xff\xd9"
CONTROLLED_GAP_SIZE = 4096


def scan_evidence(evidence_path: str) -> list[dict]:
    """Scan binary evidence and identify candidate JPEG regions.

    The scanner is a deterministic candidate detector: it locates JPEG SOI (FF D8)
    and EOI (FF D9) markers, records exact byte offsets, extracts candidate bytes,
    and computes candidate SHA-256 digests. It creates CANDIDATE or PARTIAL
    records without falsely claiming full forensic validation.

    Args:
        evidence_path: Path to the binary evidence disk image or file.

    Returns:
        list[dict]: Ordered list of candidate fragment dictionaries conforming to
                    fragment_schema.json.

    Raises:
        FileNotFoundError: If evidence_path does not exist.
        IsADirectoryError: If evidence_path is a directory.
    """
    path = Path(evidence_path)
    if not path.exists():
        raise FileNotFoundError(f"Evidence file not found: {evidence_path}")
    if path.is_dir():
        raise IsADirectoryError(f"Evidence path is a directory: {evidence_path}")

    with open(path, "rb") as f:
        data = f.read()

    candidates: list[dict] = []
    frag_counter = 1
    pos = 0
    data_len = len(data)

    while pos < data_len:
        soi_idx = data.find(SOI_MARKER, pos)
        if soi_idx == -1:
            break

        # Check for any subsequent SOI marker
        next_soi_idx = data.find(SOI_MARKER, soi_idx + 2)

        # Search for corresponding EOI marker after current SOI
        next_eoi_idx = data.find(EOI_MARKER, soi_idx + 2)

        if next_eoi_idx == -1:
            # SOI without any subsequent EOI -> PARTIAL candidate
            if next_soi_idx != -1:
                offset_start = soi_idx
                offset_end = next_soi_idx
                pos = next_soi_idx
            else:
                offset_start = soi_idx
                offset_end = data_len
                pos = data_len

            header_detected = True
            footer_detected = False
            status = "PARTIAL"

        elif next_soi_idx != -1 and next_soi_idx < next_eoi_idx:
            # Another SOI appears before any EOI -> Current SOI is truncated
            offset_start = soi_idx
            offset_end = next_soi_idx
            pos = next_soi_idx
            header_detected = True
            footer_detected = False
            status = "PARTIAL"

        else:
            # Valid SOI + EOI candidate pair
            offset_start = soi_idx
            offset_end = next_eoi_idx + 2  # Convention: one position after FF D9
            pos = offset_end
            header_detected = True
            footer_detected = True
            status = "CANDIDATE"

        size_bytes = offset_end - offset_start
        candidate_bytes = data[offset_start:offset_end]
        candidate_sha256 = hashlib.sha256(candidate_bytes).hexdigest().lower()

        fragment = {
            "fragment_id": f"FRAG-{frag_counter:03d}",
            "offset_start": offset_start,
            "offset_end": offset_end,
            "size_bytes": size_bytes,
            "predicted_type": "JPEG",
            "classifier_confidence": 1.0,
            "sha256": candidate_sha256,
            "header_detected": header_detected,
            "footer_detected": footer_detected,
            "status": status,
        }
        candidates.append(fragment)
        frag_counter += 1

    return candidates


def scan_controlled_fragments(
    evidence_path: str,
    minimum_gap_size: int = CONTROLLED_GAP_SIZE,
) -> dict[str, list[dict]]:
    """Detect physically separated candidate segments using observed zero gaps.

    This preserves the normal scanner output while exposing only boundaries that
    are directly visible in the evidence bytes. Chunk indexes are ordinal within
    each observed candidate segment group; no external metadata is consulted.
    """
    if minimum_gap_size <= 0:
        raise ValueError("minimum_gap_size must be positive")

    path = Path(evidence_path)
    data = path.read_bytes()
    segments_by_candidate: dict[str, list[dict]] = {}
    for candidate in scan_evidence(evidence_path):
        start = candidate["offset_start"]
        end = candidate["offset_end"]
        region = data[start:end]
        segments = []
        cursor = 0
        while cursor < len(region):
            gap_start = region.find(b"\x00" * minimum_gap_size, cursor)
            if gap_start == -1:
                segment_end = len(region)
            else:
                segment_end = gap_start
            if segment_end > cursor:
                segment_data = region[cursor:segment_end]
                segments.append({
                    "fragment_id": f"{candidate['fragment_id']}-CHUNK-{len(segments):03d}",
                    "chunk_index": len(segments),
                    "offset_start": start + cursor,
                    "offset_end": start + segment_end,
                    "size_bytes": len(segment_data),
                    "data": segment_data,
                })
            if gap_start == -1:
                break
            cursor = gap_start + minimum_gap_size
        if len(segments) > 1:
            segments_by_candidate[candidate["fragment_id"]] = segments
    return segments_by_candidate
