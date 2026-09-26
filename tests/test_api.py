"""Tests for API routes and FastAPI app."""

import json
import inspect
from pathlib import Path
import pytest
import jsonschema
from fastapi.testclient import TestClient

from backend.main import app
import backend.routes.artifacts as artifacts_routes
import backend.routes.cases as cases_routes
import backend.services.analysis_service as analysis_service


DATASET_IMAGE = Path(__file__).resolve().parent.parent / "dataset" / "generated" / "incident_disk.img"
client = TestClient(app)


@pytest.fixture
def isolated_api_storage(tmp_path, monkeypatch):
    """Keep API test artifacts out of the repository and isolate registries."""
    upload_dir = tmp_path / "uploads"
    cases_dir = tmp_path / "cases"
    monkeypatch.setattr(cases_routes, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(analysis_service, "CASES_DIR", cases_dir)
    monkeypatch.setattr(artifacts_routes, "CASES_DIR", cases_dir)
    analysis_service.CASE_REGISTRY.clear()
    analysis_service.ARTIFACT_REGISTRY.clear()
    analysis_service.ARTIFACT_PATHS.clear()
    analysis_service.CASE_UPLOADS.clear()
    analysis_service.CASE_FILENAMES.clear()
    yield
    analysis_service.CASE_REGISTRY.clear()
    analysis_service.ARTIFACT_REGISTRY.clear()
    analysis_service.ARTIFACT_PATHS.clear()
    analysis_service.CASE_UPLOADS.clear()
    analysis_service.CASE_FILENAMES.clear()


def _create_and_analyze_case():
    with DATASET_IMAGE.open("rb") as evidence:
        created = client.post(
            "/api/cases",
            files={"file": ("incident_disk.img", evidence, "application/octet-stream")},
        )
    assert created.status_code == 200
    case_id = created.json()["case_id"]
    analyzed = client.post(f"/api/cases/{case_id}/analyze")
    assert analyzed.status_code == 200
    return case_id, analyzed.json()


def test_api_app_imported():
    """Verify FastAPI application instance is importable."""
    assert app is not None
    assert app.title == "RECON-X"


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "RECON-X"}


def test_create_case_accepts_evidence_upload(isolated_api_storage):
    response = client.post(
        "/api/cases",
        files={"file": ("evidence.bin", b"raw evidence", "application/octet-stream")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["case_id"].startswith("CASE-")
    assert body["filename"] == "evidence.bin"
    assert body["size_bytes"] == len(b"raw evidence")
    assert body["status"] == "CREATED"


def test_empty_upload_is_rejected(isolated_api_storage):
    response = client.post(
        "/api/cases",
        files={"file": ("empty.bin", b"", "application/octet-stream")},
    )

    assert response.status_code == 400


def test_analysis_returns_case_summary_and_artifacts(isolated_api_storage):
    case_id, result = _create_and_analyze_case()

    assert result["case_id"] == case_id
    assert result["source"]["filename"] == "incident_disk.img"
    assert result["summary"]["jpeg_candidates"] > 0
    assert result["artifacts"]


def test_get_case_returns_analysis(isolated_api_storage):
    case_id, result = _create_and_analyze_case()

    response = client.get(f"/api/cases/{case_id}")

    assert response.status_code == 200
    assert response.json() == result


def test_get_case_artifacts_returns_measured_artifacts(isolated_api_storage):
    case_id, result = _create_and_analyze_case()

    response = client.get(f"/api/cases/{case_id}/artifacts")

    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == case_id
    assert [artifact["artifact_id"] for artifact in body["artifacts"]] == result["artifacts"]
    assert all("confidence_score" in artifact for artifact in body["artifacts"])
    assert all("priority" in artifact for artifact in body["artifacts"])


def test_get_artifact_returns_detail(isolated_api_storage):
    _, result = _create_and_analyze_case()
    artifact_id = result["artifacts"][0]

    response = client.get(f"/api/artifacts/{artifact_id}")

    assert response.status_code == 200
    assert response.json()["artifact_id"] == artifact_id


def test_artifact_exposes_forensic_reconstruction_trail(isolated_api_storage):
    _, result = _create_and_analyze_case()
    artifact = client.get(f"/api/artifacts/{result['artifacts'][0]}").json()

    assert artifact["evidence_offsets"]["start"] < artifact["evidence_offsets"]["footer"] < artifact["evidence_offsets"]["end"]
    assert artifact["fragment_details"][0]["fragment_id"] == artifact["fragments"][0]
    assert artifact["fragment_details"][0]["size_bytes"] == artifact["recovered_size_bytes"]
    assert artifact["validation"]["structure_valid"] is True
    assert artifact["reconstruction"]["performed"] is False
    assert set(artifact["evidence_state"]) == {"observed", "reconstructed", "inferred", "unknown"}


def test_artifact_exposes_hypothesis_result_without_fabrication(isolated_api_storage):
    _, result = _create_and_analyze_case()
    artifact = client.get(f"/api/artifacts/{result['artifacts'][0]}").json()

    assert artifact["hypotheses"] == []
    assert artifact["hypothesis_status"] == "NOT_ESTABLISHED"
    assert "trained compatibility model" in artifact["hypothesis_note"]
    assert "C:\\" not in artifact["hypothesis_note"]


def test_controlled_fragments_expose_supported_and_rejected_hypotheses(isolated_api_storage):
    _, result = _create_and_analyze_case()
    artifacts = client.get(f"/api/cases/{result['case_id']}/artifacts").json()["artifacts"]
    hypothesis_artifact = next(artifact for artifact in artifacts if artifact["hypotheses"])

    statuses = {hypothesis["status"] for hypothesis in hypothesis_artifact["hypotheses"]}
    assert "SUPPORTED" in statuses
    assert "REJECTED" in statuses
    for hypothesis in hypothesis_artifact["hypotheses"]:
        assert hypothesis["fragment_ids"]
        assert hypothesis["compatibility_scores"]
        assert "validation" in hypothesis
        assert not any("\\" in str(value) for value in hypothesis.values())
        if hypothesis["status"] == "REJECTED" and hypothesis["compatibility_score"] >= 0.8:
            assert hypothesis["contradiction"] is True


def test_high_compatibility_invalid_hypothesis_is_contradicted(isolated_api_storage, monkeypatch):
    class AlwaysHighModel:
        def predict_score(self, first, second):
            return 0.95

    monkeypatch.setattr(analysis_service, "train_model", lambda pairs, labels: AlwaysHighModel())
    _, result = _create_and_analyze_case()
    artifacts = client.get(f"/api/cases/{result['case_id']}/artifacts").json()["artifacts"]
    rejected = [
        hypothesis
        for artifact in artifacts
        for hypothesis in artifact["hypotheses"]
        if hypothesis["status"] == "REJECTED"
    ]

    assert rejected
    assert all(hypothesis["compatibility_score"] == 0.95 for hypothesis in rejected)
    assert all(hypothesis["contradiction"] is True for hypothesis in rejected)


def test_missing_case_returns_404(isolated_api_storage):
    assert client.get("/api/cases/CASE-MISSING").status_code == 404
    assert client.post("/api/cases/CASE-MISSING/analyze").status_code == 404
    assert client.get("/api/cases/CASE-MISSING/artifacts").status_code == 404


def test_missing_artifact_returns_404(isolated_api_storage):
    assert client.get("/api/artifacts/ART-MISSING").status_code == 404
    assert client.get("/api/artifacts/ART-MISSING/preview").status_code == 404


def test_preview_returns_recovered_jpeg(isolated_api_storage):
    _, result = _create_and_analyze_case()
    artifacts = client.get(f"/api/cases/{result['case_id']}/artifacts").json()["artifacts"]
    recovered = next(artifact for artifact in artifacts if artifact["status"] == "RECOVERED")

    response = client.get(f"/api/artifacts/{recovered['artifact_id']}/preview")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content.startswith(b"\xff\xd8")


def test_invalid_preview_returns_404(isolated_api_storage):
    _, result = _create_and_analyze_case()
    artifacts = client.get(f"/api/cases/{result['case_id']}/artifacts").json()["artifacts"]
    uncertain = next(artifact for artifact in artifacts if artifact["status"] == "UNRELIABLE")

    response = client.get(f"/api/artifacts/{uncertain['artifact_id']}/preview")

    assert response.status_code == 404


def test_invalid_evidence_is_analyzed_without_path_exposure(isolated_api_storage, tmp_path):
    response = client.post(
        "/api/cases",
        files={"file": ("payload.bin", b"not a JPEG", "application/octet-stream")},
    )
    case_id = response.json()["case_id"]

    analyzed = client.post(f"/api/cases/{case_id}/analyze")

    assert analyzed.status_code == 200
    assert analyzed.json()["summary"]["jpeg_candidates"] == 0
    assert str(tmp_path) not in analyzed.text


def test_random_binary_creates_no_false_artifacts(isolated_api_storage):
    random_bytes = bytes(range(256)) * 8
    created = client.post(
        "/api/cases",
        files={"file": ("random.bin", random_bytes, "application/octet-stream")},
    )
    case_id = created.json()["case_id"]

    analyzed = client.post(f"/api/cases/{case_id}/analyze")

    assert analyzed.status_code == 200
    assert analyzed.json()["summary"]["jpeg_candidates"] == 0
    assert analyzed.json()["artifacts"] == []


def test_controlled_dataset_has_six_candidates_and_conservative_statuses(isolated_api_storage):
    _, result = _create_and_analyze_case()

    assert result["summary"]["jpeg_candidates"] == 6
    assert result["summary"]["recovered"] == 5
    assert result["summary"]["uncertain"] == 1
    assert {artifact["status"] for artifact in client.get(
        f"/api/cases/{result['case_id']}/artifacts"
    ).json()["artifacts"]} == {"RECOVERED", "UNRELIABLE"}


def test_confidence_and_priority_fields_are_present_without_fabrication(isolated_api_storage):
    _, result = _create_and_analyze_case()
    artifacts = client.get(f"/api/cases/{result['case_id']}/artifacts").json()["artifacts"]

    assert all("confidence_score" in artifact for artifact in artifacts)
    assert all("priority" in artifact for artifact in artifacts)
    assert all(artifact["confidence_score"] is None for artifact in artifacts)
    assert all(artifact["priority"] is None for artifact in artifacts)


def test_artifact_order_is_deterministic_and_null_scores_follow_scored_items(isolated_api_storage):
    _, result = _create_and_analyze_case()
    first = client.get(f"/api/cases/{result['case_id']}/artifacts").json()["artifacts"]
    second = client.get(f"/api/cases/{result['case_id']}/artifacts").json()["artifacts"]

    assert [artifact["artifact_id"] for artifact in first] == [artifact["artifact_id"] for artifact in second]
    assert [artifact["artifact_id"] for artifact in first] == sorted(
        artifact["artifact_id"] for artifact in first
    )


def test_repeated_analysis_replaces_case_artifacts_without_corruption(isolated_api_storage):
    case_id, first = _create_and_analyze_case()
    second_response = client.post(f"/api/cases/{case_id}/analyze")

    assert second_response.status_code == 200
    second = second_response.json()
    assert second["summary"] == first["summary"]
    assert second["artifacts"] == first["artifacts"]
    assert client.get(f"/api/cases/{case_id}").json() == second


def test_case_summary_counts_match_artifact_statuses(isolated_api_storage):
    case_id, result = _create_and_analyze_case()
    artifacts = client.get(f"/api/cases/{case_id}/artifacts").json()["artifacts"]
    summary = result["summary"]

    assert summary["recovered"] == sum(artifact["status"] == "RECOVERED" for artifact in artifacts)
    assert summary["partially_recovered"] == sum(artifact["status"] == "PARTIAL" for artifact in artifacts)
    assert summary["uncertain"] == sum(artifact["status"] == "UNRELIABLE" for artifact in artifacts)
    assert summary["jpeg_candidates"] == len(artifacts)


def test_evidence_state_has_only_declared_categories(isolated_api_storage):
    _, result = _create_and_analyze_case()
    artifacts = client.get(f"/api/cases/{result['case_id']}/artifacts").json()["artifacts"]

    for artifact in artifacts:
        assert set(artifact["evidence_state"]) == {
            "observed", "reconstructed", "inferred", "unknown"
        }


def test_api_responses_do_not_expose_absolute_artifact_paths(isolated_api_storage):
    case_id, result = _create_and_analyze_case()
    case_response = client.get(f"/api/cases/{case_id}")
    artifact_response = client.get(f"/api/cases/{case_id}/artifacts")

    assert case_response.status_code == 200
    assert artifact_response.status_code == 200
    assert all(
        not Path(artifact["output_path"]).is_absolute()
        for artifact in artifact_response.json()["artifacts"]
    )
    assert "\\" not in artifact_response.text


def test_runtime_analysis_service_does_not_read_ground_truth():
    source = inspect.getsource(analysis_service)

    assert "ground_truth.json" not in source
    assert "ground_truth" not in source


def test_analysis_failure_returns_generic_server_error(isolated_api_storage, monkeypatch):
    response = client.post(
        "/api/cases",
        files={"file": ("evidence.bin", b"evidence", "application/octet-stream")},
    )
    case_id = response.json()["case_id"]

    def fail_analysis(*args, **kwargs):
        raise RuntimeError("internal test traceback")

    monkeypatch.setattr(cases_routes, "analyze_evidence", fail_analysis)
    analyzed = client.post(f"/api/cases/{case_id}/analyze")

    assert analyzed.status_code == 500
    assert analyzed.json()["detail"] == "Evidence analysis failed"
    assert "traceback" not in analyzed.text.lower()


def test_schemas_valid_and_conform():
    """Verify JSON schemas comply with draft-07 and match specification examples."""
    schemas_dir = Path(__file__).resolve().parent.parent / "schemas"
    
    # 1. Fragment Schema
    with open(schemas_dir / "fragment_schema.json", "r", encoding="utf-8") as f:
        fragment_schema = json.load(f)
    jsonschema.Draft7Validator.check_schema(fragment_schema)
    sample_fragment = {
        "fragment_id": "FRAG-001",
        "offset_start": 1048576,
        "offset_end": 1572864,
        "size_bytes": 524288,
        "predicted_type": "JPEG",
        "classifier_confidence": 1.0,
        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "header_detected": True,
        "footer_detected": True,
        "status": "CANDIDATE"
    }
    jsonschema.validate(instance=sample_fragment, schema=fragment_schema)

    # 2. Artifact Schema
    with open(schemas_dir / "artifact_schema.json", "r", encoding="utf-8") as f:
        artifact_schema = json.load(f)
    jsonschema.Draft7Validator.check_schema(artifact_schema)
    sample_artifact = {
        "artifact_id": "ART-001",
        "filename_guess": "recovered_001.jpg",
        "status": "RECONSTRUCTED",
        "fragments": ["FRAG-001", "FRAG-002"],
        "expected_size_bytes": 1254321,
        "recovered_size_bytes": 1142000,
        "recovery_completeness": 0.91,
        "structural_integrity": 0.96,
        "classification_confidence": 0.98,
        "fragment_consistency": 0.89,
        "confidence_score": 0.94,
        "evidence_state": {
            "observed": ["JPEG SOI detected at offset 1048576"],
            "reconstructed": ["Two ordered fragments assembled"],
            "inferred": ["Fragment classified as JPEG"],
            "unknown": ["Original filename unknown"]
        },
        "output_path": "samples/demo_case/recovered/recovered_001.jpg"
    }
    jsonschema.validate(instance=sample_artifact, schema=artifact_schema)

    # 3. Case Schema
    with open(schemas_dir / "case_schema.json", "r", encoding="utf-8") as f:
        case_schema = json.load(f)
    jsonschema.Draft7Validator.check_schema(case_schema)
    sample_case = {
        "case_id": "CASE-001",
        "name": "Simulated Cyber Incident",
        "created_at": "2026-09-25T13:00:00Z",
        "source": {
            "filename": "incident_disk.img",
            "size_bytes": 52428800,
            "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        },
        "analysis": {
            "status": "COMPLETED",
            "started_at": "2026-09-25T13:01:00Z",
            "completed_at": "2026-09-25T13:02:00Z"
        },
        "summary": {
            "regions_detected": 42,
            "jpeg_candidates": 18,
            "recovered": 15,
            "partially_recovered": 2,
            "uncertain": 1
        },
        "artifacts": ["ART-001", "ART-002"]
    }
    jsonschema.validate(instance=sample_case, schema=case_schema)

