"""RECON-X application configuration."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = BASE_DIR / "dataset"
SAMPLES_DIR = BASE_DIR / "samples"
FRONTEND_DIR = BASE_DIR / "frontend"
SCHEMAS_DIR = BASE_DIR / "schemas"
UPLOAD_DIR = BASE_DIR / "samples" / "uploads"
CASES_DIR = BASE_DIR / "samples" / "cases"
ARTIFACTS_DIR = CASES_DIR

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CASES_DIR.mkdir(parents=True, exist_ok=True)
