"""Case management and analysis routes."""

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.config import UPLOAD_DIR
from backend.services.analysis_service import (
	CASE_FILENAMES,
	CASE_REGISTRY,
	CASE_UPLOADS,
	ARTIFACT_REGISTRY,
	analyze_evidence,
)
from core.hashing import calculate_sha256

router = APIRouter(prefix="/api/cases", tags=["cases"])


def _new_case_id() -> str:
	sequence = len(CASE_UPLOADS) + 1
	case_id = f"CASE-{sequence:03d}"
	while case_id in CASE_UPLOADS:
		sequence += 1
		case_id = f"CASE-{sequence:03d}"
	return case_id


@router.post("")
async def create_case(file: UploadFile = File(...)):
	"""Store uploaded evidence under a server-generated path."""
	case_id = _new_case_id()
	case_dir = UPLOAD_DIR / case_id
	case_dir.mkdir(parents=True, exist_ok=True)
	evidence_path = case_dir / f"evidence-{uuid4().hex}.bin"

	size_bytes = 0
	try:
		with evidence_path.open("wb") as destination:
			while chunk := await file.read(1024 * 1024):
				destination.write(chunk)
				size_bytes += len(chunk)
	finally:
		await file.close()

	if size_bytes == 0:
		evidence_path.unlink(missing_ok=True)
		case_dir.rmdir()
		raise HTTPException(status_code=400, detail="Uploaded evidence file is empty")

	CASE_UPLOADS[case_id] = evidence_path.resolve()
	CASE_FILENAMES[case_id] = Path(file.filename or "evidence.bin").name
	return {
		"case_id": case_id,
		"filename": CASE_FILENAMES[case_id],
		"size_bytes": size_bytes,
		"sha256": calculate_sha256(str(evidence_path)),
		"status": "CREATED",
	}


@router.post("/{case_id}/analyze")
def analyze_case(case_id: str):
	evidence_path = CASE_UPLOADS.get(case_id)
	if evidence_path is None or not evidence_path.is_file():
		raise HTTPException(status_code=404, detail="Case not found")

	try:
		return analyze_evidence(
			str(evidence_path),
			case_id,
			source_filename=CASE_FILENAMES.get(case_id),
		)
	except (OSError, ValueError) as exc:
		raise HTTPException(status_code=500, detail=f"Evidence analysis failed: {exc}") from exc
	except Exception as exc:
		raise HTTPException(status_code=500, detail="Evidence analysis failed") from exc


@router.get("/{case_id}/artifacts")
def list_case_artifacts(case_id: str):
	case = CASE_REGISTRY.get(case_id)
	if case is None:
		raise HTTPException(status_code=404, detail="Case not found")

	return {
		"case_id": case_id,
		"artifacts": [ARTIFACT_REGISTRY[artifact_id] for artifact_id in case["artifacts"]],
	}


@router.get("/{case_id}")
def get_case(case_id: str):
	case = CASE_REGISTRY.get(case_id)
	if case is None:
		raise HTTPException(status_code=404, detail="Case not found")
	return case
