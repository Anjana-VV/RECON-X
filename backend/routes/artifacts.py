"""Artifact retrieval routes."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.config import CASES_DIR
from backend.services.analysis_service import ARTIFACT_PATHS, ARTIFACT_REGISTRY

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


@router.get("/{artifact_id}/preview")
def preview_artifact(artifact_id: str):
	artifact = ARTIFACT_REGISTRY.get(artifact_id)
	output_path = ARTIFACT_PATHS.get(artifact_id)
	if artifact is None or output_path is None or artifact["status"] != "RECOVERED":
		raise HTTPException(status_code=404, detail="Valid artifact preview not found")

	try:
		resolved_path = output_path.resolve()
		resolved_path.relative_to(CASES_DIR.resolve())
	except (OSError, ValueError):
		raise HTTPException(status_code=404, detail="Valid artifact preview not found")
	if not resolved_path.is_file():
		raise HTTPException(status_code=404, detail="Valid artifact preview not found")

	return FileResponse(resolved_path, media_type="image/jpeg", filename=artifact["filename_guess"])


@router.get("/{artifact_id}")
def get_artifact(artifact_id: str):
	artifact = ARTIFACT_REGISTRY.get(artifact_id)
	if artifact is None:
		raise HTTPException(status_code=404, detail="Artifact not found")
	return artifact
