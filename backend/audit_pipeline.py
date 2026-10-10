import logging

from ai_core import decompose_claims, retrieve_evidence, verify_claims
from backend.audit_utils import compute_span, validate_quote
from backend.report_utils import build_overall_report


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


def run_audit_pipeline(answer, pdf_chunks, total_pages, progress_callback=None):
    """
    Run claim decomposition, evidence retrieval, verification,
    evidence-quote validation, span calculation, and report calculation.

    progress_callback, when provided, is called as:
        progress_callback(step_text, percent_complete)
    """

    def update(step, progress):
        if progress_callback:
            progress_callback(step, progress)

    update("Decomposing answer into claims", 15)
    claims = decompose_claims(answer)

    if not isinstance(claims, list):
        raise ValueError("Claim decomposition did not return a list")

    # Ensure each claim has an ID and text before passing it to retrieval.
    clean_claims = []

    for index, claim in enumerate(claims, start=1):
        if not isinstance(claim, dict):
            logger.warning("Skipping malformed claim at position %s", index)
            continue

        claim_id = claim.get("id", index)
        claim_text = claim.get("text")

        if not isinstance(claim_id, int) or isinstance(claim_id, bool):
            logger.warning("Skipping claim with invalid ID: %r", claim_id)
            continue

        if not isinstance(claim_text, str) or not claim_text.strip():
            logger.warning("Skipping claim %r with empty text", claim_id)
            continue

        clean_claims.append({
            "id": claim_id,
            "text": claim_text,
        })

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

    update("Verifying claims against evidence", 60)
    verification_response = verify_claims(
        claims=clean_claims,
        evidence_by_claim=evidence_by_claim,
    )

    if not isinstance(verification_response, dict):
        raise ValueError("Verification did not return a dictionary")

    verification_results = verification_response.get("claims", [])

    if not isinstance(verification_results, list):
        raise ValueError("Verification response is missing its claims list")

    results_by_id = {}

    for result in verification_results:
        if not isinstance(result, dict):
            continue

        result_id = result.get("id")
        if isinstance(result_id, int) and not isinstance(result_id, bool):
            results_by_id[result_id] = result

    update("Validating evidence and building report", 80)

    final_claims = []

    for claim in clean_claims:
        claim_id = claim["id"]
        claim_text = claim["text"]
        result = results_by_id.get(claim_id, {})

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

        # The project describes confidence as evidence strength and caps it
        # below 1.0 to avoid presenting it as certainty.
        confidence = max(0.0, min(0.95, confidence))

        explanation = str(
            result.get("explanation", "No explanation was returned.")
        )

        if result.get("error"):
            logger.warning(
                "Verification error for claim %s: %s",
                claim_id,
                result["error"],
            )

        # The current confirmed decomposition interface returns only id/text.
        # Use importance 3 until the team confirms how importance is supplied.
        importance = claim.get("importance", 3)
        if isinstance(importance, bool) or not isinstance(importance, int):
            importance = 3
        importance = max(1, min(5, importance))

        # Never trust an evidence page supplied by the model. Find the quote
        # in the extracted PDF and use the page returned by validate_quote().
        validated_evidence = []
        raw_evidence = result.get("evidence", [])

        if isinstance(raw_evidence, list):
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

        span = compute_span(claim_text, answer)

        # A zero-length span does not highlight unrelated answer text.
        # The frontend should ignore spans where start == end.
        if span is None:
            logger.warning("Could not find a safe answer span for claim %s", claim_id)
            span = {"start": 0, "end": 0}

        final_claims.append({
            "id": claim_id,
            "text": claim_text,
            "span": span,
            "verdict": verdict,
            "category": category,
            "importance": importance,
            "confidence": confidence,
            "explanation": explanation,
            "evidence": validated_evidence,
        })

    overall = build_overall_report(
        claims=final_claims,
        total_pages=total_pages,
    )

    update("Audit complete", 100)

    return {
        "overall": overall,
        "claims": final_claims,
    }