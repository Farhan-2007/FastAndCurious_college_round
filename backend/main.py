import asyncio
import logging

import os
from dotenv import load_dotenv

from backend.audit_pipeline import run_audit_pipeline
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.pdf_utils import PDFValidationError, extract_pdf, validate_answer

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("audit_debug.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


app = FastAPI(title="Second Opinion API")
logger = logging.getLogger(__name__)

AUDIT_STATUS = {}
frontend_origins = os.getenv(
    "FRONTEND_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://localhost:5174",
)

allowed_origins = [
    origin.strip()
    for origin in frontend_origins.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    detail = exc.detail

    if isinstance(detail, dict) and "error" in detail:
        message = detail["error"]
    else:
        message = str(detail)

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": message},
    )
@app.exception_handler(Exception)
async def unexpected_exception_handler(request, exc):
    logger.exception("Unexpected API error")

    return JSONResponse(
        status_code=500,
        content={
            "error": "An unexpected server error occurred. Please try again."
        },
    )
    detail = exc.detail
    message = detail["error"] if isinstance(detail, dict) else str(detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": message},
    )


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "llm": "not_configured",
        "fallback": "not_configured",
    }


@app.post("/api/audit")
async def create_audit(
    pdf: UploadFile = File(...),
    answer: str = Form(...),
    question: str = Form(""),
):
    # Read and validate the uploaded file and answer.
    pdf_bytes = await pdf.read()

    try:
        validate_answer(answer)
        pdf_result = extract_pdf(pdf_bytes, pdf.filename or "")
    except PDFValidationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": exc.message},
        )

    # Create an ID and start tracking this request.
    audit_id = str(uuid4())
    AUDIT_STATUS[audit_id] = {
        "step": "Starting audit",
        "progress": 5,
    }

    # The pipeline calls this as it progresses.
    def update_status(step, progress):
        AUDIT_STATUS[audit_id] = {
            "step": step,
            "progress": progress,
        }

    try:
        # AI calls are synchronous, so run the pipeline in a worker thread.
        result = await asyncio.to_thread(
            run_audit_pipeline,
            answer,
            pdf_result["chunks"],
            pdf_result["total_pages"],
            update_status,
        )
    except Exception:
        logger.exception("Audit failed. Audit ID: %s", audit_id)

        AUDIT_STATUS[audit_id] = {
            "step": "Audit failed",
            "progress": 100,
        }

        raise HTTPException(
            status_code=500,
            detail={
                "error": "The audit could not be completed. Please try again."
            },
        )

    # Return the API response after the pipeline completes.
    return {
        "audit_id": audit_id,
        "overall": result["overall"],
        "claims": result["claims"],
    }

@app.get("/api/audit/{audit_id}/status")
def get_audit_status(audit_id: str):
    status = AUDIT_STATUS.get(audit_id)

    if status is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Audit not found"},
        )

    return status