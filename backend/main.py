
import logging
import os
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.pdf_utils import (
    PDFValidationError,
    extract_pdf,
    validate_answer,
)
from ai_core.claim_extractor import decompose_claims
from ai_core.evidence_retriever import retrieve_evidence
from ai_core.verifier import verify_claims


log = logging.getLogger(__name__)

app = FastAPI(title="Second Opinion API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Preserve structured error details in HTTP responses."""
    detail = exc.detail

    if isinstance(detail, dict):
        content = detail
    else:
        content = {"error": str(detail)}

    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=getattr(exc, "headers", None),
    )


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        # This confirms configuration presence, not provider availability.
        "llm": (
            "configured"
            if os.getenv("GROQ_API_KEY")
            and os.getenv("SO_LLM_MODEL")
            else "not_configured"
        ),
        "fallback": "check_required",
    }


@app.post("/api/audit")
async def create_audit(
    pdf: UploadFile = File(...),
    answer: str = Form(...),
    question: str = Form(""),
):
    # Read the uploaded PDF.
    pdf_bytes = await pdf.read()

    # Validate the answer and extract PDF text.
    try:
        validate_answer(answer)
        pdf_result = extract_pdf(pdf_bytes, pdf.filename or "")
    except PDFValidationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": exc.message},
        )

    pdf_chunks = pdf_result["chunks"]
    total_pages = pdf_result["total_pages"]
    pages_without_text = pdf_result["pages_without_text"]

    # Extract claims from the submitted answer.
    claims = decompose_claims(answer)
    log.info("Extracted %s claims for audit", len(claims))

    if not claims:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "No verifiable claims could be extracted from the answer.",
                "code": "NO_CLAIMS",
                "retryable": False,
            },
        )

    # Retrieve relevant PDF passages for each claim.
    evidence_by_claim = {
        claim["id"]: retrieve_evidence(
            claim,
            pdf_chunks,
            top_k=3,
        )
        for claim in claims
    }

    # Verify claims against the retrieved evidence.
    verification = verify_claims(claims, evidence_by_claim)
    verified_claims = verification["claims"]

    # IMPORTANT:
    # An ambiguous verdict can be genuine. An attached error means
    # verification did not complete and must not be reported as a verdict.
    failed_claims = [
        claim
        for claim in verified_claims
        if claim.get("error")
    ]

    if failed_claims:
        log.warning(
            "Audit verification failed for %s of %s claims",
            len(failed_claims),
            len(verified_claims),
        )

        raise HTTPException(
            status_code=503,
            detail={
                "error": (
                    "Verification could not be completed because the AI "
                    "provider failed or its quota is unavailable. "
                    "Please check the provider quota and try again later."
                ),
                "code": "VERIFICATION_FAILED",
                "retryable": True,
                "failed_claims": len(failed_claims),
                "total_claims": len(verified_claims),
            },
        )

    # Count verdicts only after verification completed without errors.
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

    total_claims = len(verified_claims)

    score = (
        round(100 * counts["supported"] / total_claims)
        if total_claims
        else 0
    )

    pages_referenced = {
        evidence["page"]
        for claim in verified_claims
        for evidence in claim.get("evidence", [])
        if evidence.get("page") is not None
    }

    claims_without_evidence = sum(
        1
        for claim in verified_claims
        if not claim.get("evidence")
    )

    # Return success only when the verification pipeline completed.
    return {
        "audit_id": str(uuid4()),
        "success": True,
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
    }


@app.get("/api/audit/{audit_id}/status")
def get_audit_status(audit_id: str):
    return {
        "step": "Audit result ready",
        "progress": 100,
    }
