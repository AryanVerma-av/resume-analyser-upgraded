import os
import logging
from pathlib import Path
from typing import List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

import backend.config as cfg

from backend.models import (
    ROLE_DISPLAY_MAP,
    JobD,
    BatchAnalysisResponse,
)
from backend.matcher import ResumeAnalyzerPipeline
from backend.groq_client import GroqMatcherClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("resume_analyzer.api")

app = FastAPI(
    title="Resume Analyzer (TypeSafe Stage 1 + Groq Stage 2)",
    version="1.0.0",
    description="Clean two-stage Resume Analyzer utilizing TypeSafe System One for screening and Groq for detailed matching.",
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = ResumeAnalyzerPipeline()
groq_client = GroqMatcherClient()

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/api/config")
async def get_system_config():
    """Return non-sensitive public configuration for the UI."""
    return {
        "roles": list(ROLE_DISPLAY_MAP.keys()),
        "default_role": "Junior Backend Developer",
        "role_confidence_threshold": cfg.ROLE_CONFIDENCE_THRESHOLD,
        "basic_fit_threshold": cfg.BASIC_FIT_THRESHOLD,
        "experience_threshold": cfg.EXPERIENCE_THRESHOLD,
        "typesafe_model": cfg.TYPESAFE_MODEL,
        "groq_model": cfg.GROQ_MODEL,
    }


@app.post("/api/analyze-job", response_model=JobD)
async def analyze_job_description(
    job_description: str = Form(...),
    target_role: str = Form("Junior Backend Developer"),
):
    """Parse raw job description into structured JobD model using Groq."""
    if not job_description.strip():
        raise HTTPException(status_code=400, detail="Job description cannot be empty")
    try:
        return groq_client.parse_job_description(job_description, fallback_role=target_role)
    except Exception as e:
        logger.error(f"Error parsing job description: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze", response_model=BatchAnalysisResponse)
async def analyze_resumes(
    files: List[UploadFile] = File(...),
    target_role: str = Form("Junior Backend Developer"),
    job_description: str = Form(...),
):
    """
    Main Batch Analysis Endpoint.
    1. Extracts text from each uploaded PDF/DOCX resume.
    2. Runs Stage 1 TypeSafe System One (Choice, Noul, Score) screening.
    3. Executes deterministic Python filtering (Stage 1 Gate).
    4. Runs Groq Stage 2 detailed matching ONLY for Stage 1 passed candidates.
    5. Returns structured BatchAnalysisResponse.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No resume files uploaded")
    if not job_description.strip():
        raise HTTPException(status_code=400, detail="Job description is required")

    logger.info(f"Received {len(files)} files for role: '{target_role}'")

    # Read all uploaded file contents into memory
    file_tuples = []
    for file in files:
        try:
            content = await file.read()
            file_tuples.append((file.filename, content))
        except Exception as e:
            logger.error(f"Failed to read upload {file.filename}: {e}")
            file_tuples.append((file.filename, b""))

    try:
        response = pipeline.analyze_batch(
            files=file_tuples,
            job_description_text=job_description,
            target_role_display=target_role,
        )
        return response
    except Exception as e:
        logger.error(f"Fatal error in batch analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch analysis failure: {str(e)}")


# Serve static frontend files
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(str(FRONTEND_DIR / "index.html"))
