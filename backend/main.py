import asyncio
import logging

from backend.audit_pipeline import run_audit_pipeline
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.pdf_utils import PDFValidationError, extract_pdf, validate_answer


app = FastAPI(title="Second Opinion API")
logger = logging.getLogger(__name__)

AUDIT_STATUS = {}
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
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
    pdf_bytes = await pdf.read()

    try:
        validate_answer(answer)
        pdf_result = extract_pdf(pdf_bytes, pdf.filename or "")
    except PDFValidationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": exc.message},
        )

    audit_id = str(uuid4())

    AUDIT_STATUS[audit_id] = {
        "step": "Starting audit",
        "progress": 5,
    }

    def update_status(step, progress):
        AUDIT_STATUS[audit_id] = {
            "step": step,
            "progress": progress,
        }

    try:
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
            detail={"error": "The audit could not be completed. Please try again."},
        )

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