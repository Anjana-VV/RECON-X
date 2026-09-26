"""Focused tests for the offline evidence-honesty evaluator."""

from dataset.evaluate import build_report, calculate_metrics


def _audit(damage, status=None, byte_match=None, artifact_id=None):
    return {
        "ground_truth_id": damage,
        "expected_damage": damage,
        "expected_original": f"{damage}.jpg",
        "expected_size_bytes": 10,
        "runtime_status": status,
        "runtime_artifact_id": artifact_id,
        "predicted_type": "JPEG" if artifact_id else None,
        "recovered_size_bytes": 10 if artifact_id else None,
        "byte_match": byte_match,
        "sha256_match": byte_match,
        "validation_result": None,
        "evaluation_result": "NOT_ESTABLISHED",
    }


def test_metrics_calculate_exact_matches_and_false_reconstructions():
    audits = [
        _audit("intact", "RECOVERED", True, "ART-1"),
        _audit("duplicated", "RECOVERED", False, "ART-2"),
        _audit("corrupted", "UNRELIABLE", None, "ART-3"),
        _audit("deleted_unavailable"),
    ]
    metrics = calculate_metrics(audits, 3, {"supported": 1, "rejected": 2, "partial": 0, "contradictions": 1})

    assert metrics["classification_accuracy"] == 1.0
    assert metrics["recovery_success_rate"] == 1.0
    assert metrics["correct_partial_rate"] == 1.0
    assert metrics["false_reconstruction_rate"] == 0.5
    assert metrics["deleted_correctly_flagged_rate"] == 1.0
    assert metrics["supporting_statistics"]["exact_byte_matches"] == 1
    assert metrics["supporting_statistics"]["exact_byte_mismatches"] == 1


def test_zero_denominators_are_not_established():
    metrics = calculate_metrics([], 0, {"supported": 0, "rejected": 0, "partial": 0, "contradictions": 0})

    assert metrics["classification_accuracy"] is None
    assert metrics["recovery_success_rate"] is None
    assert metrics["correct_partial_rate"] is None
    assert metrics["false_reconstruction_rate"] is None
    assert metrics["deleted_correctly_flagged_rate"] is None


def test_build_report_preserves_offline_boundary_and_audit():
    ground_truth = {"evidence_file": "incident_disk.img"}
    audits = [_audit("deleted_unavailable")]
    report = build_report(ground_truth, audits, 0, {"supported": 0, "rejected": 0, "partial": 0, "contradictions": 0}, timestamp="fixed")

    assert report["evaluation"]["runtime_ground_truth_dependency"] is False
    assert report["evaluation"]["timestamp"] == "fixed"
    assert report["per_artifact"] == audits
    assert report["metrics"]["deleted_correctly_flagged_rate"] == 1.0
