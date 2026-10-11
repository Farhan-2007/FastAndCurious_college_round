
import os
import logging
from collections import Counter

try:
    from .llm_client import LLMClient, LLMError
except ImportError:
    from llm_client import LLMClient, LLMError

log = logging.getLogger(__name__)

VALID_VERDICTS = {
    "supported", "contradicted", "insufficient", "ambiguous"
}


# FEATURE 2: HALLUCINATION HEATMAP

def build_heatmap(claims):
    """
    Convert audited claims into frontend-ready heatmap data.
    Does not modify the original claims.
    """
    heatmap = []

    severity_map = {
        "supported": "low",
        "contradicted": "high",
        "insufficient": "medium",
        "ambiguous": "medium",
    }

    for claim in claims:
        verdict = str(claim.get("verdict", "insufficient")).lower()
        category = str(claim.get("category", "unsupported")).lower()

        try:
            confidence = float(claim.get("confidence", 0))
        except (TypeError, ValueError):
            confidence = 0.0

        confidence = max(0.0, min(1.0, confidence))

        # A failed verification must not be treated as a confirmed finding.
        if claim.get("error"):
            severity = "unknown"
        elif verdict not in VALID_VERDICTS:
            severity = "unknown"
        elif verdict == "contradicted":
            severity = "high"
        elif verdict == "supported":
            severity = "low"
        else:
            severity = "medium"

        heatmap.append({
            "claim_id": claim.get("id", claim.get("claim_id")),
            "text": claim.get("text", claim.get("claim_text", "")),
            "verdict": verdict,
            "category": category,
            "confidence": confidence,
            "severity": severity,
        })

    return heatmap


# FEATURE 3: CORRECTED ANSWER GENERATION

def generate_corrected_answer(
    original_answer,
    claims,
    client=None,
):
    """
    Generate a more evidence-grounded answer.

    Mock mode deliberately does not call an LLM.
    """
    if not isinstance(original_answer, str) or not original_answer.strip():
        raise ValueError("original_answer must be a non-empty string")

    if not isinstance(claims, list):
        raise ValueError("claims must be a list")

    # Only verified quotations returned by the existing verifier are used.
    verified_claims = []

    for claim in claims:
        verdict = str(claim.get("verdict", "")).lower()
        if verdict not in VALID_VERDICTS:
            continue

        evidence = claim.get("evidence") or []
        verified_evidence = []

        for item in evidence:
            if not isinstance(item, dict):
                continue

            quote = item.get("quote")
            if isinstance(quote, str) and quote.strip():
                verified_evidence.append({
                    "quote": quote,
                    "page": item.get("page"),
                    "source": item.get("source"),
                })

        verified_claims.append({
            "text": claim.get("text", claim.get("claim_text", "")),
            "verdict": verdict,
            "category": claim.get("category", "unsupported"),
            "explanation": claim.get("explanation", ""),
            "evidence": verified_evidence,
            "error": claim.get("error"),
        })

    # No API key or API credits are needed for this fallback.
    if os.getenv("SO_MOCK_VERIFICATION", "").lower() == "true":
        return {
            "corrected_answer": None,
            "status": "mock_mode",
            "message": (
                "Corrected answer generation requires an LLM. "
                "Mock mode did not generate or invent a replacement answer."
            ),
            "claim_review": verified_claims,
        }

    client = client or LLMClient()

    system = """
You revise AI-generated answers using audit results and verified evidence.

Rules:
1. Use only facts directly supported by the supplied verified evidence.
2. Do not invent facts, sources, quotations, dates, or page numbers.
3. Remove or qualify contradicted claims.
4. Explicitly state when important information is insufficient or ambiguous.
5. A claim marked with an error was not successfully verified; do not treat
   its verdict as reliable.
6. Do not treat a source quotation as proof of facts beyond what it states.
7. Return only a JSON object with this structure:
{
  "corrected_answer": "Revised answer",
  "changes": [
    {
      "original_claim": "Claim text",
      "action": "retained, corrected, removed, or qualified",
      "reason": "Short evidence-based reason"
    }
  ],
  "limitations": ["Any remaining evidence limitations"]
}
"""

    user = (
        "ORIGINAL ANSWER:\n"
        + original_answer
        + "\n\nAUDIT RESULTS WITH VERIFIED EVIDENCE:\n"
        + __import__("json").dumps(
            verified_claims, ensure_ascii=False
        )
        + "\n\nRevise the answer according to the system rules."
    )

    try:
        result = client.complete_json(system, user)
    except LLMError:
        log.exception("Corrected answer generation failed")
        return {
            "corrected_answer": None,
            "status": "failed",
            "message": "The corrected answer could not be generated.",
            "claim_review": verified_claims,
        }

    corrected = result.get("corrected_answer")
    if not isinstance(corrected, str) or not corrected.strip():
        return {
            "corrected_answer": None,
            "status": "failed",
            "message": "The model returned no usable corrected answer.",
            "claim_review": verified_claims,
        }

    changes = result.get("changes", [])
    limitations = result.get("limitations", [])

    return {
        "corrected_answer": corrected.strip(),
        "status": "success",
        "changes": changes if isinstance(changes, list) else [],
        "limitations": (
            limitations if isinstance(limitations, list) else []
        ),
    }


# FEATURE 6: SOURCE QUALITY ASSESSMENT

def assess_source_quality(claims, chunks=None):
    """
    Assess evidence coverage and source metadata.

    This is a transparent heuristic, not an authenticity checker.
    """
    chunks = chunks or []

    total = len(claims)
    verdict_counts = Counter()
    evidence_count = 0
    pages = set()
    sources = set()
    missing_source_metadata = 0
    verification_errors = 0

    for claim in claims:
        verdict = str(
            claim.get("verdict", "insufficient")
        ).lower()

        if claim.get("error"):
            verification_errors += 1
            continue

        if verdict in VALID_VERDICTS:
            verdict_counts[verdict] += 1

        evidence = claim.get("evidence") or []

        for item in evidence:
            if not isinstance(item, dict):
                continue

            quote = item.get("quote")
            if not isinstance(quote, str) or not quote.strip():
                continue

            evidence_count += 1

            page = item.get("page")
            if page is not None:
                pages.add(str(page))

            source = item.get("source")
            if isinstance(source, str) and source.strip():
                sources.add(source.strip())
            else:
                missing_source_metadata += 1

    covered = (
        verdict_counts["supported"]
        + verdict_counts["contradicted"]
    )
    coverage = (
        round(covered / total, 3) if total else 0.0
    )

    issues = []

    if total == 0:
        issues.append("No claims were supplied for assessment.")

    if verdict_counts["insufficient"]:
        issues.append(
            "Some claims lack enough evidence for a reliable verdict."
        )

    if verdict_counts["ambiguous"]:
        issues.append(
            "Some claims have conflicting or unclear evidence."
        )

    if verification_errors:
        issues.append(
            "Some claims failed verification; their verdicts may be unreliable."
        )

    if evidence_count == 0:
        issues.append("No evidence quotations are available.")

    if missing_source_metadata:
        issues.append(
            "Some evidence quotations lack source-name metadata."
        )

    if not pages:
        issues.append(
            "Evidence page metadata is unavailable."
        )

    # Source metadata may be present in the PDF chunks even when
    # the verifier's evidence objects only contain quote and page.
    chunk_sources = set()
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        source = chunk.get("source")
        if isinstance(source, str) and source.strip():
            chunk_sources.add(source.strip())

    all_sources = sources | chunk_sources

    return {
        "assessment_type": "heuristic",
        "claims_assessed": total,
        "claims_with_evidence_verdict": covered,
        "evidence_coverage": coverage,
        "evidence_quotes": evidence_count,
        "distinct_evidence_pages": len(pages),
        "distinct_source_names": len(all_sources),
        "verification_errors": verification_errors,
        "verdict_counts": {
            verdict: verdict_counts.get(verdict, 0)
            for verdict in sorted(VALID_VERDICTS)
        },
        "issues": issues,
        "limitations": [
            "Source names and page numbers do not prove authenticity.",
            "Publication dates, authority, and recency are not "
            "verified by this heuristic.",
            "Coverage measures supported or contradicted verdicts, "
            "not the overall quality or truth of a document.",
        ],
    }