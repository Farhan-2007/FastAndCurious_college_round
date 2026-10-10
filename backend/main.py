from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.pdf_utils import PDFValidationError, extract_pdf, validate_answer


app = FastAPI(title="Second Opinion API")

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
    # Read the uploaded PDF.
    pdf_bytes = await pdf.read()

    # Validate the answer and PDF, then extract text page by page.
    try:
        validate_answer(answer)
        pdf_result = extract_pdf(pdf_bytes, pdf.filename or "")
    except PDFValidationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": exc.message},
        )

    # These are now available for the real AI pipeline:
    pdf_chunks = pdf_result["chunks"]
    total_pages = pdf_result["total_pages"]
    pages_without_text = pdf_result["pages_without_text"]

    # Temporary response until the AI claim-verification pipeline is connected.
    # The PDF is validated and extracted, but the claims are NOT verified yet.
    return {
        "audit_id": str(uuid4()),
        "demo_mode": True,
        "overall": {
            "score": 0,
            "summary": (
                "PDF validation and text extraction succeeded. "
                "Claim verification is not connected yet."
            ),
            "counts": {
                "supported": 0,
                "contradicted": 0,
                "insufficient": 0,
                "ambiguous": 0,
            },
            "source_coverage": {
                "pages_referenced": 0,
                "total_pages": total_pages,
                "claims_without_evidence": 0,
            },
        },
        "claims": [],
        "note": (
            f"{pages_without_text} page(s) with no extractable text were skipped."
        ),
    }


@app.get("/api/audit/{audit_id}/status")
def get_audit_status(audit_id: str):
    return {
        "step": "Demo result ready",
        "progress": 100,
    }