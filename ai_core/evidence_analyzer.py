"""Analyze ONE claim against evidence passages retrieved by the backend (Member 2).

Reuses the Step 1 LLM client, schemas and result builder. Instructions for the LLM
live in prompts/verification_prompt.txt (edit that file to tune behaviour).
This module does no PDF extraction, retrieval or HTTP - it only judges.
"""

import os
import logging
from pathlib import Path

try:  # package import (e.g. `from ai_core import ...`)
    from .llm_client import LLMClient, LLMError
    from .schemas import Claim, coerce_claims, coerce_passages
    from . import verifier as _v
except ImportError:  # flat import (files run from inside the folder)
    from .llm_client import LLMClient, LLMError
    from .schemas import Claim, coerce_claims, coerce_passages
    import verifier as _v

log = logging.getLogger(__name__)
PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "verification_prompt.txt"

def _mock_analyze_claim(claim, passages):
    text = claim.text.lower()
    combined = " ".join(p.text for p in passages).lower()

    if not passages:
        verdict = "insufficient"
        category = "unsupported"
        explanation = "No evidence passages were supplied."
    elif "120 employees" in text and "120 people" in combined:
        verdict = "supported"
        category = "none"
        explanation = "The evidence states that the laboratory employs 120 people."
    elif "established in 1990" in text and "opened in 2018" in combined:
        verdict = "contradicted"
        category = "hallucination"
        explanation = "The evidence says the laboratory opened in 2018, not 1990."
    else:
        verdict = "insufficient"
        category = "unsupported"
        explanation = "The mock verifier has no predefined result for this claim."

    result = _v._fixed(claim, verdict, category, 0.95, explanation)

    data = result.to_dict()
    if passages:
        data["evidence"] = [
            {"quote": p.text, "page": p.page}
            for p in passages
        ]

    return data

def analyze_claim(claim, passages, client: LLMClient = None, claim_id: int = 1) -> dict:
    """Judge one claim against its retrieved passages.

    claim:    str | {"id": int, "text": str} | Claim
              (a plain string gets `claim_id`; the text is kept exactly as given)
    passages: list of {"text": str, "page": int (optional), "source": str (optional)}
              (plain strings also accepted; page/source are preserved in the output)
    client:   optional LLMClient (default: built from environment variables)

    Returns one dict (JSON-compatible, same contract as verify_claims results):
      {"claim_id", "claim_text", "verdict", "category", "confidence",
       "explanation", "evidence": [{"quote", "page", "source"}], "error"}
    verdict  in: supported | contradicted | insufficient | ambiguous
    category in: hallucination | unsupported | logic | unsafe | none
    `error` is None normally; if set, verification could not run and the verdict
    must not be trusted. Raises ValueError only for an unusable claim/passage type.
    """
    claim = _as_claim(claim, claim_id)
    passages = coerce_passages(passages)
    if os.getenv("SO_MOCK_VERIFICATION", "").lower() == "true":
        return _mock_analyze_claim(claim, passages)
    
    if not passages:  # nothing to check against -> insufficient, never "false"
        return _v._fixed(claim, "insufficient", "unsupported", 1.0,
                         "No evidence passages were supplied.").to_dict()

    passages, truncated = _v._fit_budget(passages)

    try:
        system = _load_prompt()
    except (OSError, ValueError) as e:
        return _v._failed(claim, f"Verification prompt unavailable: {e}").to_dict()

    try:
        data = (client or LLMClient()).complete_json(
            system, _v._build_user([claim], passages))
        item = _pick_item(data, claim)
        result = _build(claim, item, passages)
    except LLMError as e:
        log.warning("analysis failed: %s", e)
        return _v._failed(claim, f"Verification failed: {e}").to_dict()
    except (ValueError, TypeError, KeyError) as e:
        log.warning("invalid LLM result: %s", e)
        return _v._failed(claim, f"Verification failed: {e}").to_dict()

    if truncated:
        result.explanation = (result.explanation + " (Note: some passages were "
                              "omitted because of the size limit.)").strip()
    return result.to_dict()


# ---- internals ----
def _as_claim(claim, claim_id) -> Claim:
    if isinstance(claim, str):
        claim = Claim(id=claim_id, text=claim)
    claims = coerce_claims([claim])
    if len(claims) != 1 or not claims[0].text.strip():
        raise ValueError("analyze_claim expects one non-empty claim")
    return claims[0]


def _load_prompt() -> str:
    text = PROMPT_PATH.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("prompt file is empty")
    return text


def _pick_item(data: dict, claim: Claim) -> dict:
    results = data.get("results")
    if isinstance(results, list):
        for r in results:
            if isinstance(r, dict) and str(r.get("claim_id")) == str(claim.id):
                return r
        if len(results) == 1 and isinstance(results[0], dict):
            return results[0]
        raise LLMError("no result returned for this claim")
    if "verdict" in data:  # model returned a bare result object
        return data
    raise LLMError("'results' missing from LLM output")


def _build(claim: Claim, item: dict, passages: list):
    # Which stances did the VERIFIED quotes take? (unverifiable quotes don't count)
    stances = set()
    for e in item.get("evidence") or []:
        if isinstance(e, dict) and _v.find_quote(e.get("quote", ""), passages,
                                                 e.get("passage_id")):
            s = str(e.get("stance", "")).strip().lower()
            if s in ("supports", "contradicts"):
                stances.add(s)

    result = _v._build_result(claim, item, passages)  # validates enums, verifies quotes

    # Deterministic safeguard: real quotes on both sides = conflicting evidence.
    if stances == {"supports", "contradicts"} and result.verdict in ("supported", "contradicted"):
        result.verdict, result.category = "ambiguous", "none"
        result.confidence = min(result.confidence, 0.6)
        result.explanation = (result.explanation + " (Evidence conflicts: verified "
                              "passages both support and contradict this claim.)").strip()
    return result