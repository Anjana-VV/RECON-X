"""Analysis orchestration service."""

from datetime import datetime, timezone
from pathlib import Path

from backend.config import CASES_DIR
from core.carving import carve_jpeg
from core.confidence import calculate_confidence
from core.hashing import calculate_sha256
from core.integrity import validate_jpeg
from core.prioritization import calculate_priority
from core.scanner import scan_controlled_fragments, scan_evidence
from ml.hypotheses import generate_hypotheses
from ml.train import build_training_data, train_model


CASE_REGISTRY: dict[str, dict] = {}
ARTIFACT_REGISTRY: dict[str, dict] = {}
ARTIFACT_PATHS: dict[str, Path] = {}
CASE_UPLOADS: dict[str, Path] = {}
CASE_FILENAMES: dict[str, str] = {}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _artifact_status(carved_status: str) -> str:
    if carved_status == "VALIDATED":
        return "RECOVERED"
    if carved_status == "PARTIAL":
        return "PARTIAL"
    return "UNRELIABLE"


def _artifact_result(
    case_id: str,
    index: int,
    fragment: dict,
    hypotheses: list[dict] | None = None,
) -> tuple[dict, Path]:
    artifact_id = f"{case_id}-ART-{index:03d}"
    output_path = Path(fragment["output_path"]).resolve()
    integrity = validate_jpeg(str(output_path))
    status = _artifact_status(fragment["status"])

    observed = [
        f"JPEG SOI detected at offset {fragment['offset_start']}.",
        f"JPEG EOI marker detected at offset {fragment['offset_end'] - 2}.",
        f"Carved candidate size is {fragment['size_bytes']} bytes.",
        f"Detected type is {fragment['predicted_type']}.",
        f"Candidate SHA-256 is {fragment['sha256']}.",
    ]
    if integrity["decodable"]:
        observed.append("Pillow successfully decoded artifact.")
    else:
        observed.append("Pillow did not successfully decode artifact.")

    unknown = [
        "Expected original size is unavailable from the uploaded evidence.",
        "Recovery completeness is unavailable without an expected original size.",
        "Fragment consistency is unavailable because no explicit fragment ordering was supplied.",
    ]
    artifact = {
        "artifact_id": artifact_id,
        "filename_guess": f"recovered_{index:03d}.jpg",
        "status": status,
        "fragments": [fragment["fragment_id"]],
        "fragment_details": [{
            "fragment_id": fragment["fragment_id"],
            "chunk_index": None,
            "offset_start": fragment["offset_start"],
            "offset_end": fragment["offset_end"],
            "footer_offset": fragment["offset_end"] - 2,
            "size_bytes": fragment["size_bytes"],
            "predicted_type": fragment["predicted_type"],
            "status": fragment["status"],
        }],
        "evidence_offsets": {
            "start": fragment["offset_start"],
            "footer": fragment["offset_end"] - 2,
            "end": fragment["offset_end"],
        },
        "expected_size_bytes": None,
        "recovered_size_bytes": fragment["size_bytes"],
        "recovery_completeness": None,
        "structural_integrity": float(integrity["structure_valid"]),
        "classification_confidence": float(fragment["classifier_confidence"]),
        "fragment_consistency": None,
        "confidence_score": None,
        "priority": None,
        "validation": integrity,
        "reconstruction": {
            "performed": False,
            "method": None,
            "fragment_ids": [],
            "chunk_indexes": [],
            "output_size_bytes": None,
        },
        "hypotheses": hypotheses or [],
        "hypothesis_status": "AVAILABLE" if hypotheses else "NOT_ESTABLISHED",
        "hypothesis_note": "Evidence-derived controlled fragment hypotheses." if hypotheses else "No trained compatibility model and explicit ordered fragment set are available for this runtime candidate.",
        "evidence_state": {
            "observed": observed,
            "reconstructed": [],
            "inferred": [f"Artifact status classified as {status}."],
            "unknown": unknown,
        },
        "output_path": f"cases/{case_id}/carved/{output_path.name}",
    }

    # These calculations are intentionally gated: unavailable measurements must
    # remain unknown instead of being replaced with fabricated defaults.
    if artifact["recovery_completeness"] is not None and artifact["fragment_consistency"] is not None:
        confidence = calculate_confidence(
            artifact["classification_confidence"],
            artifact["structural_integrity"],
            artifact["recovery_completeness"],
            artifact["fragment_consistency"],
        )
        artifact["confidence_score"] = confidence["score"]
        artifact["evidence_state"]["inferred"].append(
            f"Confidence label is {confidence['label']}."
        )
        artifact["priority"] = calculate_priority(
            artifact["confidence_score"],
            artifact["recovery_completeness"],
            artifact["structural_integrity"],
            0.0,
        )

    return artifact, output_path


def analyze_evidence(
    evidence_path: str,
    case_id: str,
    case_name: str = "RECON-X Case",
    source_filename: str | None = None,
) -> dict:
    """Run the existing evidence pipeline and return a JSON-safe case result."""
    path = Path(evidence_path).resolve()
    started_at = _timestamp()
    source_size = path.stat().st_size
    source_hash = calculate_sha256(str(path))
    scanned_regions = scan_evidence(str(path))

    case_dir = (CASES_DIR / case_id).resolve()
    carved_dir = case_dir / "carved"
    carved_dir.mkdir(parents=True, exist_ok=True)
    carved_fragments = carve_jpeg(str(path), str(carved_dir))
    controlled_groups = scan_controlled_fragments(str(path))

    compatibility_model = None
    if controlled_groups:
        source_fragments = {
            candidate_id: [segment["data"] for segment in segments]
            for candidate_id, segments in controlled_groups.items()
        }
        pairs, labels, _ = build_training_data(source_fragments)
        compatibility_model = train_model(pairs, labels)

    previous_case = CASE_REGISTRY.get(case_id)
    if previous_case is not None:
        for artifact_id in previous_case["artifacts"]:
            ARTIFACT_REGISTRY.pop(artifact_id, None)
            ARTIFACT_PATHS.pop(artifact_id, None)

    artifacts = []
    for index, fragment in enumerate(carved_fragments, start=1):
        hypotheses = []
        segments = controlled_groups.get(fragment["fragment_id"], [])
        if compatibility_model is not None and len(segments) > 1:
            hypothesis_fragments = []
            fragment_dir = case_dir / "hypothesis_fragments"
            fragment_dir.mkdir(parents=True, exist_ok=True)
            for segment in segments:
                segment_file = fragment_dir / f"{fragment['fragment_id']}-{segment['chunk_index']}.bin"
                segment_file.write_bytes(segment["data"])
                hypothesis_fragments.append({
                    "fragment_id": segment["fragment_id"],
                    "chunk_index": segment["chunk_index"],
                    "output_path": str(segment_file),
                    "data": segment["data"],
                })
            raw_hypotheses = generate_hypotheses(
                hypothesis_fragments,
                compatibility_model,
                case_dir / "hypotheses",
                total_expected_chunks=len(segments),
            )
            hypotheses = [{
                "hypothesis_id": item["hypothesis_id"],
                "fragment_ids": item["fragment_ids"],
                "compatibility_scores": item["compatibility_scores"],
                "compatibility_score": item["compatibility_score"],
                "validation": item["validation"],
                "status": item["status"],
                "contradiction": bool(item["status"] == "REJECTED" and item["compatibility_score"] >= 0.8),
            } for item in raw_hypotheses]
        artifact, output_path = _artifact_result(case_id, index, fragment, hypotheses)
        artifacts.append(artifact)
        ARTIFACT_REGISTRY[artifact["artifact_id"]] = artifact
        ARTIFACT_PATHS[artifact["artifact_id"]] = output_path

    recovered = sum(artifact["status"] == "RECOVERED" for artifact in artifacts)
    partial = sum(artifact["status"] == "PARTIAL" for artifact in artifacts)
    uncertain = sum(artifact["status"] == "UNRELIABLE" for artifact in artifacts)
    completed_at = _timestamp()
    artifacts.sort(
        key=lambda artifact: (
            artifact["priority"] is None,
            -(artifact["priority"] or 0.0),
            artifact["artifact_id"],
        )
    )
    result = {
        "case_id": case_id,
        "name": case_name,
        "created_at": started_at,
        "source": {
            "filename": source_filename or path.name,
            "size_bytes": source_size,
            "sha256": source_hash,
        },
        "analysis": {
            "status": "COMPLETED",
            "started_at": started_at,
            "completed_at": completed_at,
        },
        "summary": {
            "regions_detected": len(scanned_regions),
            "jpeg_candidates": len(carved_fragments),
            "recovered": recovered,
            "partially_recovered": partial,
            "uncertain": uncertain,
        },
        "artifacts": [artifact["artifact_id"] for artifact in artifacts],
    }
    CASE_REGISTRY[case_id] = result
    return result
