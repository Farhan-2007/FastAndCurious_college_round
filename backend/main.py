import logging
import os
from uuid import uuid4

from dotenv import load_dotenv
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

from backend.audit_utils import compute_span, validate_quote
from ai_core.advanced_features import (
    assess_source_quality,
    build_heatmap,
    generate_corrected_answer,
)


# --------------------------------------------------
# Configuration
# --------------------------------------------------

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
log = logger

app = FastAPI(title="Second Opinion API")

# Stores the latest status of each audit in memory.
# Status entries reset when the server restarts.
AUDIT_STATUS = {}


# --------------------------------------------------
# CORS configuration
# --------------------------------------------------

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


# --------------------------------------------------
# Error handlers
# --------------------------------------------------

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Preserve structured API error details."""
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


@app.exception_handler(Exception)
async def unexpected_exception_handler(request, exc):
    """Return a safe message for unexpected server errors."""
    logger.exception("Unexpected API error")

    return JSONResponse(
        status_code=500,
        content={
            "error": "An unexpected server error occurred. Please try again."
        },
    )


# --------------------------------------------------
# Health check
# --------------------------------------------------

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        # Configuration presence does not prove provider availability.
        "llm": (
            "configured"
            if os.getenv("GROQ_API_KEY")
            and os.getenv("SO_LLM_MODEL")
            else "not_configured"
        ),
        "fallback": "check_required",
    }


# --------------------------------------------------
# Create audit
# --------------------------------------------------

@app.post("/api/audit")
async def create_audit(
    pdf: UploadFile = File(...),
    answer: str = Form(...),
    question: str = Form(""),
     include_corrected_answer: bool = Form(False),
):
    audit_id = str(uuid4())

    AUDIT_STATUS[audit_id] = {
        "step": "Starting audit",
        "progress": 5,
    }

    try:
        # Read and validate the uploaded PDF and answer.
        pdf_bytes = await pdf.read()

        validate_answer(answer)

        AUDIT_STATUS[audit_id] = {
            "step": "Extracting PDF text",
            "progress": 15,
        }

        pdf_result = extract_pdf(
            pdf_bytes,
            pdf.filename or "",
        )

    except PDFValidationError as exc:
        AUDIT_STATUS[audit_id] = {
            "step": "Audit failed",
            "progress": 100,
        }

        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": exc.message},
        )

    finally:
        await pdf.close()

    pdf_chunks = pdf_result["chunks"]
    total_pages = pdf_result["total_pages"]
    pages_without_text = pdf_result["pages_without_text"]

    # Extract verifiable claims from the submitted answer.
    AUDIT_STATUS[audit_id] = {
        "step": "Extracting claims",
        "progress": 25,
    }

    try:
        claims = decompose_claims(answer)
    except Exception:
        logger.exception(
            "Claim extraction failed. Audit ID: %s",
            audit_id,
        )

        AUDIT_STATUS[audit_id] = {
            "step": "Audit failed",
            "progress": 100,
        }

        raise HTTPException(
            status_code=503,
            detail={
                "error": "Claims could not be extracted. Please try again later.",
                "code": "CLAIM_EXTRACTION_FAILED",
                "retryable": True,
            },
        )

    log.info(
        "Extracted %s claims for audit %s",
        len(claims),
        audit_id,
    )

    if not claims:
        AUDIT_STATUS[audit_id] = {
            "step": "Audit failed",
            "progress": 100,
        }

        raise HTTPException(
            status_code=422,
            detail={
                "error": (
                    "No verifiable claims could be extracted "
                    "from the answer."
                ),
                "code": "NO_CLAIMS",
                "retryable": False,
            },
        )

    # Retrieve relevant PDF evidence for each claim.
    AUDIT_STATUS[audit_id] = {
        "step": "Retrieving evidence",
        "progress": 40,
    }

    try:
        evidence_by_claim = {
            claim["id"]: retrieve_evidence(
                claim,
                pdf_chunks,
                top_k=3,
            )
            for claim in claims
        }
    except Exception:
        logger.exception(
            "Evidence retrieval failed. Audit ID: %s",
            audit_id,
        )

        AUDIT_STATUS[audit_id] = {
            "step": "Audit failed",
            "progress": 100,
        }

        raise HTTPException(
            status_code=503,
            detail={
                "error": (
                    "Evidence retrieval could not be completed. "
                    "Please try again later."
                ),
                "code": "EVIDENCE_RETRIEVAL_FAILED",
                "retryable": True,
            },
        )

    # Verify claims against the retrieved evidence.
    AUDIT_STATUS[audit_id] = {
        "step": "Verifying claims",
        "progress": 60,
    }

    try:
        verification = verify_claims(
            claims,
            evidence_by_claim,
        )
        verified_claims = verification["claims"]

    except Exception:
        logger.exception(
            "Claim verification failed. Audit ID: %s",
            audit_id,
        )

        AUDIT_STATUS[audit_id] = {
            "step": "Audit failed",
            "progress": 100,
        }

        raise HTTPException(
            status_code=503,
            detail={
                "error": (
                    "Verification could not be completed because "
                    "the AI provider may be unavailable or its quota "
                    "may be exhausted. Please try again later."
                ),
                "code": "VERIFICATION_FAILED",
                "retryable": True,
            },
        )

    # A failed verification is not a valid verdict.
    failed_claims = [
        claim
        for claim in verified_claims
        if claim.get("error")
    ]

    if failed_claims:
        log.warning(
            "Verification failed for %s of %s claims. Audit ID: %s",
            len(failed_claims),
            len(verified_claims),
            audit_id,
        )

        AUDIT_STATUS[audit_id] = {
            "step": "Verification failed",
            "progress": 100,
        }

        raise HTTPException(
            status_code=503,
            detail={
                "error": (
                    "Verification could not be completed because "
                    "the AI provider failed or its quota is unavailable. "
                    "Please check the provider quota and try again later."
                ),
                "code": "VERIFICATION_FAILED",
                "retryable": True,
                "failed_claims": len(failed_claims),
                "total_claims": len(verified_claims),
            },
        )
    # Normalize claim fields for the API and frontend.
    # Compute answer spans and validate evidence against the uploaded PDF.
    for claim in verified_claims:
        claim_id = claim.get("id", claim.get("claim_id"))
        claim_text = claim.get("text", claim.get("claim_text", ""))

        claim["id"] = claim_id
        claim["text"] = claim_text

        span = compute_span(claim_text, answer)
        claim["span"] = (
            span
            if span is not None
            else {"start": 0, "end": 0}
        )

        # Member 3's current interface may not return importance.
        claim.setdefault("importance", 3)

        validated_evidence = []

        for item in claim.get("evidence", []):
            if not isinstance(item, dict):
                continue

            quote = item.get("quote")
            if not isinstance(quote, str) or not quote.strip():
                continue

            quote_is_valid, actual_page = validate_quote(
                quote,
                pdf_chunks,
            )

            if quote_is_valid and actual_page is not None:
                clean_evidence = {
                    "quote": quote,
                    "page": actual_page,
                }

                if item.get("source"):
                    clean_evidence["source"] = item["source"]

                validated_evidence.append(clean_evidence)

        # Only evidence found in the original PDF is kept.
        claim["evidence"] = validated_evidence

    # Count verdicts only after verification succeeds.
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
        # Ensure claims have the fields expected by the frontend.
    # Also recalculate spans and validate evidence quotes against the PDF.
    for claim in verified_claims:
        claim_id = claim.get("id", claim.get("claim_id"))
        claim_text = claim.get("text", claim.get("claim_text", ""))

        claim["id"] = claim_id
        claim["text"] = claim_text

        span = compute_span(claim_text, answer)
        claim["span"] = span if span is not None else {
            "start": 0,
            "end": 0,
        }

        # The current AI claim interface may not return importance.
        # Use the agreed temporary default if it is missing.
        claim.setdefault("importance", 3)

        valid_evidence = []

        for item in claim.get("evidence", []):
            if not isinstance(item, dict):
                continue

            quote = item.get("quote")
            if not isinstance(quote, str) or not quote.strip():
                continue

            quote_is_valid, actual_page = validate_quote(
                quote,
                pdf_chunks,
            )

            if quote_is_valid and actual_page is not None:
                clean_item = {
                    "quote": quote,
                    "page": actual_page,
                }

                if item.get("source"):
                    clean_item["source"] = item["source"]

                valid_evidence.append(clean_item)

        # Discard quotes that are not found in the uploaded PDF.
        claim["evidence"] = valid_evidence

    # Build a frontend-ready hallucination heatmap.
    try:
        heatmap = build_heatmap(verified_claims)
    except Exception:
        logger.exception("Could not build the hallucination heatmap")
        heatmap = []

    # Assess source/evidence coverage. This is a heuristic, not an
    # authenticity check.
    try:
        source_quality = assess_source_quality(
            verified_claims,
            pdf_chunks,
        )
    except Exception:
        logger.exception("Could not assess source quality")
        source_quality = {
            "assessment_type": "unavailable",
            "issues": ["Source-quality assessment failed."],
            "limitations": [],
        }

    # Do not spend an additional LLM call unless the client asks for this.
    corrected_answer_result = {
        "corrected_answer": None,
        "status": "not_requested",
        "message": "Corrected answer generation was not requested.",
    }

    if include_corrected_answer:
        try:
            corrected_answer_result = generate_corrected_answer(
                original_answer=answer,
                claims=verified_claims,
            )
        except Exception:
            logger.exception("Could not generate a corrected answer")
            corrected_answer_result = {
                "corrected_answer": None,
                "status": "failed",
                "message": "The corrected answer could not be generated.",
            }

    # Mark the audit complete only after all verification succeeds.
    AUDIT_STATUS[audit_id] = {
        "step": "Audit complete",
        "progress": 100,
    }

    return {
        "audit_id": audit_id,
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
        "heatmap": heatmap,
        "source_quality": source_quality,
        "corrected_answer": corrected_answer_result,
        "note": (
            f"{pages_without_text} page(s) with no extractable "
            "text were skipped."
        ),
    }


# --------------------------------------------------
# Audit status
# --------------------------------------------------

@app.get("/api/audit/{audit_id}/status")
def get_audit_status(audit_id: str):
    status = AUDIT_STATUS.get(audit_id)

    if status is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Audit not found"},
        )

    return status