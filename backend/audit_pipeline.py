import logging

from ai_core import decompose_claims, retrieve_evidence, verify_claims
from backend.audit_utils import compute_span, validate_quote
from backend.report_utils import build_overall_report
from ai_core.advanced_features import (
    assess_source_quality,
    build_heatmap,
    generate_corrected_answer,
)


logger = logging.getLogger(__name__)

VALID_VERDICTS = {
    "supported",
    "contradicted",
    "insufficient",
    "ambiguous",
}

VALID_CATEGORIES = {
    "hallucination",
    "unsupported",
    "logic",
    "unsafe",
    "none",
}


def run_audit_pipeline(
    answer,
    pdf_chunks,
    total_pages,
    progress_callback=None,
    include_corrected_answer=False,
):
    """
    Run claim decomposition, evidence retrieval, verification,
    evidence-quote validation, span calculation, and report calculation.

    progress_callback, when provided, is called as:
        progress_callback(step_text, percent_complete)
    """

    def update(step, progress):
        if progress_callback:
            progress_callback(step, progress)

    # Step 1: Decompose the answer into claims.
    update("Decomposing answer into claims", 15)
    claims = decompose_claims(answer)

    if not isinstance(claims, list):
        raise ValueError("Claim decomposition did not return a list")

    clean_claims = []

    for index, claim in enumerate(claims, start=1):
        if not isinstance(claim, dict):
            logger.warning(
                "Skipping malformed claim at position %s", index
            )
            continue

        claim_id = claim.get("id", index)
        claim_text = claim.get("text")

        if not isinstance(claim_id, int) or isinstance(claim_id, bool):
            logger.warning("Skipping claim with invalid ID: %r", claim_id)
            continue

        if not isinstance(claim_text, str) or not claim_text.strip():
            logger.warning(
                "Skipping claim %r with empty text", claim_id
            )
            continue

        clean_claims.append({
            "id": claim_id,
            "text": claim_text.strip(),
            "importance": claim.get("importance", 3),
        })

    # Step 2: Retrieve evidence for each claim.
    update("Retrieving evidence from PDF", 35)

    evidence_by_claim = {}

    for claim in clean_claims:
        passages = retrieve_evidence(
            claim=claim,
            chunks=pdf_chunks,
            top_k=5,
        )

        if not isinstance(passages, list):
            logger.warning(
                "Evidence retrieval returned a non-list for claim %s",
                claim["id"],
            )
            passages = []

        evidence_by_claim[claim["id"]] = passages

    # Step 3: Verify claims against the retrieved evidence.
    update("Verifying claims against evidence", 60)

    verification_response = verify_claims(
        claims=clean_claims,
        evidence_by_claim=evidence_by_claim,
    )

    if not isinstance(verification_response, dict):
        raise ValueError("Verification did not return a dictionary")

    verification_results = verification_response.get("claims", [])

    if not isinstance(verification_results, list):
        raise ValueError(
            "Verification response is missing its claims list"
        )

    results_by_id = {}

    for result in verification_results:
        if not isinstance(result, dict):
            continue

        result_id = result.get("id")

        if isinstance(result_id, int) and not isinstance(result_id, bool):
            results_by_id[result_id] = result

    # Step 4: Validate evidence and construct the final report.
    update("Validating evidence and building report", 80)

    final_claims = []

    for claim in clean_claims:
        claim_id = claim["id"]
        claim_text = claim["text"]
        result = results_by_id.get(claim_id, {})

        # Detect a failed or missing verification result.
        verification_error = result.get("error")

        if not result:
            verification_error = (
                "No verification result was returned for this claim."
            )

        verdict = result.get("verdict", "ambiguous")

        if verdict not in VALID_VERDICTS:
            logger.warning(
                "Invalid verdict %r for claim %s; using ambiguous",
                verdict,
                claim_id,
            )
            verdict = "ambiguous"

        category = result.get("category", "none")

        if category not in VALID_CATEGORIES:
            category = "none"

        try:
            confidence = float(result.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0

        # Keep confidence within the accepted range.
        confidence = max(0.0, min(0.95, confidence))

        explanation = str(
            result.get("explanation", "No explanation was returned.")
        )

        # Do not present a failed verification as a valid assessment.
        if verification_error:
            logger.warning(
                "Verification error for claim %s: %s",
                claim_id,
                verification_error,
            )

            verdict = "ambiguous"
            category = "none"
            confidence = 0.0
            explanation = (
                "Verification failed; this claim could not be checked. "
                "Please retry when the AI verification service is available."
            )

        # Validate the importance value.
        importance = claim.get("importance", 3)

        if isinstance(importance, bool) or not isinstance(importance, int):
            importance = 3

        importance = max(1, min(5, importance))

        # Validate evidence quotes against the actual extracted PDF.
        # Ignore proposed evidence when verification itself failed.
        validated_evidence = []
        raw_evidence = result.get("evidence", [])

        if not verification_error and isinstance(raw_evidence, list):
            for evidence_item in raw_evidence:
                if not isinstance(evidence_item, dict):
                    continue

                quote = evidence_item.get("quote")

                if not isinstance(quote, str) or not quote.strip():
                    continue

                quote_is_valid, actual_page = validate_quote(
                    quote,
                    pdf_chunks,
                )

                if quote_is_valid and actual_page is not None:
                    validated_evidence.append({
                        "quote": quote,
                        "page": actual_page,
                    })
                else:
                    logger.warning(
                        "Rejected unverified evidence quote for claim %s",
                        claim_id,
                    )

        # A firm verdict requires at least one verified source quote.
        if (
            not verification_error
            and verdict in {"supported", "contradicted"}
            and not validated_evidence
        ):
            logger.warning(
                "Downgrading claim %s because no evidence quote was verified",
                claim_id,
            )

            verdict = "ambiguous"
            category = "none"
            confidence = min(confidence, 0.3)

            explanation = (
                explanation
                + " (Downgraded because no evidence quote could be "
                "verified against the source PDF.)"
            )

        # Calculate the claim's span in the original answer.
        span = compute_span(claim_text, answer)

        if span is None:
            logger.warning(
                "Could not find a safe answer span for claim %s",
                claim_id,
            )
            span = {"start": 0, "end": 0}

        final_claim = {
            "id": claim_id,
            "text": claim_text,
            "span": span,
            "verdict": verdict,
            "category": category,
            "importance": importance,
            "confidence": confidence,
            "explanation": explanation,
            "evidence": validated_evidence,
        }

        # Preserve the error so downstream callers can detect the failure.
        if verification_error:
            final_claim["error"] = str(verification_error)

        final_claims.append(final_claim)

    # Step 5: Calculate the overall audit report.
    overall = build_overall_report(
        claims=final_claims,
        total_pages=total_pages,
    )

    update("Building additional audit insights", 90)

    # Build the hallucination heatmap.
    try:
        heatmap = build_heatmap(final_claims)
    except Exception:
        logger.exception("Could not build the hallucination heatmap")
        heatmap = []

    # Assess source quality.
    try:
        source_quality = assess_source_quality(
            final_claims,
            pdf_chunks,
        )
    except Exception:
        logger.exception("Could not assess source quality")
        source_quality = {
            "assessment_type": "unavailable",
            "issues": ["Source-quality assessment failed."],
            "limitations": [],
        }

    # Construct the final result.
    result = {
        "overall": overall,
        "claims": final_claims,
        "heatmap": heatmap,
        "source_quality": source_quality,
    }

    # Optionally generate a corrected answer.
    if include_corrected_answer:
        try:
            result["corrected_answer"] = generate_corrected_answer(
                original_answer=answer,
                claims=final_claims,
            )
        except Exception:
            logger.exception("Could not generate a corrected answer")
            result["corrected_answer"] = {
                "corrected_answer": None,
                "status": "failed",
                "message": "The corrected answer could not be generated.",
            }

    update("Audit complete", 100)

    return result