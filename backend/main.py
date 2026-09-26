"""FastAPI application entrypoint for RECON-X."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routes.cases import router as cases_router
from backend.routes.artifacts import router as artifacts_router

app = FastAPI(
    title="RECON-X",
    description="AI-Assisted Intelligent Data Recovery and Digital Evidence Reconstruction",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cases_router)
app.include_router(artifacts_router)


@app.get("/health")
@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "RECON-X"}
