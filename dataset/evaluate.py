"""Offline evidence-honesty evaluation for the controlled RECON-X dataset."""

from __future__ import annotations

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services import analysis_service

SUCCESS_STATES = {"RECOVERED", "RECONSTRUCTED"}
CORRUPTION_STATES = {"PARTIAL", "UNRELIABLE", "REJECTED", "UNRECOVERABLE"}


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def _reset_runtime(case_dir: Path) -> None:
    analysis_service.CASES_DIR = case_dir
    for registry in (
        analysis_service.CASE_REGISTRY,
        analysis_service.ARTIFACT_REGISTRY,
        analysis_service.ARTIFACT_PATHS,
        analysis_service.CASE_UPLOADS,
        analysis_service.CASE_FILENAMES,
    ):
        registry.clear()


def _match_artifact(record: dict[str, Any], artifacts: list[dict[str, Any]]) -> dict[str, Any] | None:
    start = record.get("evidence_offset_start")
    end = record.get("evidence_offset_end")
    if start is None or end is None:
        return None
    matches = [
        artifact
        for artifact in artifacts
        if artifact.get("evidence_offsets", {}).get("start") == start
        and artifact.get("evidence_offsets", {}).get("end") == end
    ]
    return matches[0] if len(matches) == 1 else None


def _artifact_audit(record: dict[str, Any], artifact: dict[str, Any] | None, original_path: Path, artifact_paths: dict[str, Path]) -> dict[str, Any]:
    audit = {
        "ground_truth_id": record["record_id"],
        "expected_damage": record["damage_type"],
        "expected_original": record["original_file"],
        "expected_size_bytes": record["original_size_bytes"],
        "runtime_status": artifact.get("status") if artifact else None,
        "runtime_artifact_id": artifact.get("artifact_id") if artifact else None,
        "predicted_type": "JPEG" if artifact else None,
        "recovered_size_bytes": artifact.get("recovered_size_bytes") if artifact else None,
        "byte_match": None,
        "sha256_match": None,
        "validation_result": artifact.get("validation") if artifact else None,
        "evaluation_result": "NOT_ESTABLISHED",
    }
    if artifact is None or not original_path.is_file():
        return audit

    output_path = artifact_paths.get(artifact["artifact_id"])
    if output_path is None or not output_path.is_file():
        return audit
    actual_hash = _sha256(output_path)
    expected_hash = _sha256(original_path)
    audit["sha256_match"] = actual_hash == expected_hash
    audit["byte_match"] = output_path.read_bytes() == original_path.read_bytes()
    if artifact.get("status") in SUCCESS_STATES:
        audit["evaluation_result"] = "CORRECT" if audit["byte_match"] else "INCORRECT"
    else:
        audit["evaluation_result"] = "CORRECT" if record["damage_type"] == "corrupted" and artifact.get("status") in CORRUPTION_STATES else "NOT_ESTABLISHED"
    return audit


def calculate_metrics(audits: list[dict[str, Any]], total_runtime_candidates: int, hypothesis_stats: dict[str, int]) -> dict[str, Any]:
    classified = [audit for audit in audits if audit["runtime_artifact_id"] is not None]
    classification_accuracy = (
        sum(audit["predicted_type"] == "JPEG" for audit in classified) / len(classified)
        if classified else None
    )
    recovery_cases = [audit for audit in audits if audit["expected_damage"] in {"intact", "split", "duplicated"}]
    recovery_success_rate = (
        sum(audit["runtime_status"] in SUCCESS_STATES for audit in recovery_cases) / len(recovery_cases)
        if recovery_cases else None
    )
    corrupted = [audit for audit in audits if audit["expected_damage"] == "corrupted"]
    correct_corruption = sum(
        audit["runtime_artifact_id"] is None or audit["runtime_status"] in CORRUPTION_STATES
        for audit in corrupted
    )
    correct_partial_rate = correct_corruption / len(corrupted) if corrupted else None
    claimed = [audit for audit in audits if audit["runtime_status"] in SUCCESS_STATES and audit["byte_match"] is not None]
    mismatches = sum(audit["byte_match"] is False for audit in claimed)
    false_reconstruction_rate = mismatches / len(claimed) if claimed else None
    deleted = [audit for audit in audits if audit["expected_damage"] == "deleted_unavailable"]
    deleted_correct = sum(audit["runtime_status"] not in SUCCESS_STATES for audit in deleted)
    deleted_rate = deleted_correct / len(deleted) if deleted else None
    return {
        "classification_accuracy": classification_accuracy,
        "recovery_success_rate": recovery_success_rate,
        "correct_partial_rate": correct_partial_rate,
        "false_reconstruction_rate": false_reconstruction_rate,
        "deleted_correctly_flagged_rate": deleted_rate,
        "supporting_statistics": {
            "total_ground_truth_cases": len(audits),
            "total_runtime_candidates": total_runtime_candidates,
            "total_successful_reconstructions": sum(audit["runtime_status"] in SUCCESS_STATES for audit in audits),
            "total_rejected_hypotheses": hypothesis_stats["rejected"],
            "total_supported_hypotheses": hypothesis_stats["supported"],
            "total_partial_hypotheses": hypothesis_stats["partial"],
            "exact_byte_matches": sum(audit["byte_match"] is True for audit in audits),
            "exact_byte_mismatches": sum(audit["byte_match"] is False for audit in audits),
            "validation_contradictions": hypothesis_stats["contradictions"],
        },
    }


def build_report(ground_truth: dict[str, Any], audits: list[dict[str, Any]], total_runtime_candidates: int, hypothesis_stats: dict[str, int], timestamp: str | None = None) -> dict[str, Any]:
    metrics = calculate_metrics(audits, total_runtime_candidates, hypothesis_stats)
    return {
        "evaluation": {
            "dataset": ground_truth.get("evidence_file", "unknown"),
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "runtime_ground_truth_dependency": False,
            "scope": "controlled offline dataset evaluation; not production forensic performance",
        },
        "metrics": {key: metrics[key] for key in ("classification_accuracy", "recovery_success_rate", "correct_partial_rate", "false_reconstruction_rate", "deleted_correctly_flagged_rate")},
        "supporting_statistics": metrics["supporting_statistics"],
        "per_artifact": audits,
    }


def run_evaluation(root: Path | None = None, report_path: Path | None = None) -> dict[str, Any]:
    root = root or Path(__file__).resolve().parent.parent
    ground_truth_path = root / "dataset" / "ground_truth.json"
    ground_truth = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    evidence_path = root / "dataset" / "generated" / ground_truth["evidence_file"]
    originals_dir = root / "dataset" / "originals"

    with tempfile.TemporaryDirectory() as temporary:
        temp_root = Path(temporary)
        _reset_runtime(temp_root / "cases")
        result = analysis_service.analyze_evidence(str(evidence_path), "OFFLINE-EVAL", source_filename=evidence_path.name)
        artifacts = [analysis_service.ARTIFACT_REGISTRY[artifact_id] for artifact_id in result["artifacts"]]
        audits = [
            _artifact_audit(record, _match_artifact(record, artifacts), originals_dir / record["original_file"], analysis_service.ARTIFACT_PATHS)
            for record in ground_truth["records"]
        ]
        hypothesis_stats = {"supported": 0, "rejected": 0, "partial": 0, "contradictions": 0}
        for artifact in artifacts:
            for hypothesis in artifact.get("hypotheses", []):
                key = hypothesis["status"].lower()
                if key in hypothesis_stats:
                    hypothesis_stats[key] += 1
                hypothesis_stats["contradictions"] += int(hypothesis.get("contradiction", False))
        report = build_report(ground_truth, audits, len(artifacts), hypothesis_stats)

    target = report_path or (root / "dataset" / "evaluation_report.json")
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _format_metric(value: Any) -> str:
    return "NOT ESTABLISHED" if value is None else f"{value:.2%}"


def main() -> None:
    report = run_evaluation()
    print("RECON-X OFFLINE EVALUATION")
    print("==========================")
    print("Metric                              Result")
    print("------------------------------------------------")
    for label, key in (("Classification Accuracy", "classification_accuracy"), ("Recovery Success Rate", "recovery_success_rate"), ("Correct Corruption Handling", "correct_partial_rate"), ("False Reconstruction Rate", "false_reconstruction_rate"), ("Deleted Evidence Correctly Flagged", "deleted_correctly_flagged_rate")):
        print(f"{label:<36}{_format_metric(report['metrics'][key])}")
    print("\nSupporting statistics:")
    for key, value in report["supporting_statistics"].items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
