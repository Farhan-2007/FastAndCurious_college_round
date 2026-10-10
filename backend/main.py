import asyncio
import logging

from backend.audit_pipeline import run_audit_pipeline
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.pdf_utils import PDFValidationError, extract_pdf, validate_answer

from ai_core.claim_extractor import decompose_claims
from ai_core.evidence_retriever import retrieve_evidence
from ai_core.verifier import verify_claims


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

<<<<<<< HEAD
    return {
        "audit_id": audit_id,
        "overall": result["overall"],
        "claims": result["claims"],
=======
        # Extract factual claims from the submitted answer.
    claims = decompose_claims(answer)

    # Retrieve relevant PDF passages for each claim.
    evidence_by_claim = {
        claim["id"]: retrieve_evidence(claim, pdf_chunks, top_k=5)
        for claim in claims
    }

    # Verify each claim against its retrieved evidence.
    verification = verify_claims(claims, evidence_by_claim)
    verified_claims = verification["claims"]

    # Count the verdicts.
    counts = {
        "supported": 0,
        "contradicted": 0,
        "insufficient": 0,
        "ambiguous": 0,
    }

    for claim in verified_claims:
        verdict = claim.get("verdict")
        if verdict in counts:
            counts[verdict] += 1

    # Calculate a simple score based on the proportion of supported claims.
    total_claims = len(verified_claims)
    score = round(
        100 * counts["supported"] / total_claims
    ) if total_claims else 0

    pages_referenced = {
        evidence["page"]
        for claim in verified_claims
        for evidence in claim.get("evidence", [])
        if evidence.get("page") is not None
    }

    claims_without_evidence = sum(
        1 for claim in verified_claims
        if not claim.get("evidence")
    )

    return {
        "audit_id": str(uuid4()),
        "demo_mode": False,
        "overall": {
            "score": score,
            "summary": (
                f"Verified {total_claims} claims: "
                f"{counts['supported']} supported, "
                f"{counts['contradicted']} contradicted, "
                f"{counts['insufficient']} insufficient, "
                f"{counts['ambiguous']} ambiguous."
            ),
            "counts": counts,
            "source_coverage": {
                "pages_referenced": len(pages_referenced),
                "total_pages": total_pages,
                "claims_without_evidence": claims_without_evidence,
            },
        },
        "claims": verified_claims,
        "note": (
            f"{pages_without_text} page(s) with no extractable text were skipped."
        ),
>>>>>>> c28876e315b0f906cce46a9f4880a4de312311fe
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