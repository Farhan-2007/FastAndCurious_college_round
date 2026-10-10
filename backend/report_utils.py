VALID_VERDICTS = {
    "supported",
    "contradicted",
    "insufficient",
    "ambiguous",
}


def build_overall_report(claims: list[dict], total_pages: int) -> dict:
    """
    Build the API's overall summary from normalized claim results.

    Each claim should contain:
      - verdict: supported | contradicted | insufficient | ambiguous
      - importance: integer from 1 to 5 (optional; defaults to 3)
      - category: string (optional)
      - evidence: list of {"quote": str, "page": int} (optional)

    Evidence should already have been checked by validate_quote().
    """

    if not isinstance(claims, list):
        raise ValueError("claims must be a list")

    if not isinstance(total_pages, int) or isinstance(total_pages, bool):
        raise ValueError("total_pages must be an integer")

    if total_pages < 0:
        raise ValueError("total_pages cannot be negative")

    counts = {
        "supported": 0,
        "contradicted": 0,
        "insufficient": 0,
        "ambiguous": 0,
    }

    total_importance = 0
    supported_importance = 0
    pages_referenced = set()
    claims_without_evidence = 0
    has_critical_unsafe_claim = False

    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("each claim must be a dictionary")

        verdict = claim.get("verdict")

        if verdict not in VALID_VERDICTS:
            raise ValueError(f"invalid verdict: {verdict!r}")

        counts[verdict] += 1

        # Member 3's current proposed claim shape may not include importance.
        # Use a neutral default of 3 until the final contract is confirmed.
        importance = claim.get("importance", 3)

        if isinstance(importance, bool) or not isinstance(importance, int):
            importance = 3

        importance = max(1, min(5, importance))
        total_importance += importance

        if verdict == "supported":
            supported_importance += importance

        category = str(claim.get("category", "")).lower()
        if category == "unsafe" and importance >= 4:
            has_critical_unsafe_claim = True

        evidence = claim.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = []

        # Count only evidence entries with a valid page number.
        valid_page_numbers = set()

        for item in evidence:
            if not isinstance(item, dict):
                continue

            page = item.get("page")

            if isinstance(page, bool) or not isinstance(page, int):
                continue

            if 1 <= page <= total_pages:
                valid_page_numbers.add(page)

        if valid_page_numbers:
            pages_referenced.update(valid_page_numbers)
        else:
            claims_without_evidence += 1

    if total_importance == 0:
        score = 0
    else:
        score = round(100 * supported_importance / total_importance)

    summary = _make_summary(
        total_claims=len(claims),
        counts=counts,
        score=score,
        has_critical_unsafe_claim=has_critical_unsafe_claim,
    )

    return {
        "score": score,
        "summary": summary,
        "counts": counts,
        "source_coverage": {
            "pages_referenced": len(pages_referenced),
            "total_pages": total_pages,
            "claims_without_evidence": claims_without_evidence,
        },
    }


def _make_summary(
    total_claims: int,
    counts: dict,
    score: int,
    has_critical_unsafe_claim: bool,
) -> str:
    """Create a deterministic summary from the calculated results."""

    if total_claims == 0:
        return "No claims were available to assess."

    if score >= 80:
        assessment = "mostly supported by the source"
    elif score >= 50:
        assessment = "partially supported by the source"
    else:
        assessment = "poorly supported by the source"

    summary = (
        f"The AI answer is {assessment}. "
        f"Of {total_claims} claims, {counts['supported']} were supported, "
        f"{counts['contradicted']} were contradicted, "
        f"{counts['insufficient']} lacked sufficient evidence, and "
        f"{counts['ambiguous']} were ambiguous."
    )

    if has_critical_unsafe_claim:
        summary += " The audit also found a high-importance unsafe claim."

    return summary