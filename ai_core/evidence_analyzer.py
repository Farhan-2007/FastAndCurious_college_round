"""Analyze ONE claim against evidence passages retrieved by the backend (Member 2).

Reuses the Step 1 LLM client, schemas and result builder. Instructions for the LLM
live in prompts/verification_prompt.txt (edit that file to tune behaviour).
This module does no PDF extraction, retrieval or HTTP - it only judges.
"""
import logging
from pathlib import Path

try:  # package import (e.g. `from ai_core import ...`)
    from .llm_client import LLMClient, LLMError
    from .schemas import Claim, coerce_claims, coerce_passages
    from . import verifier as _v
except ImportError:  # flat import (files run from inside the folder)
    from llm_client import LLMClient, LLMError
    from schemas import Claim, coerce_claims, coerce_passages
    import verifier as _v

log = logging.getLogger(__name__)
PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "verification_prompt.txt"


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
    # Verify quotes first, then use their supplied passage IDs to determine stance.
    verified_quotes = []
    for e in item.get("evidence") or []:
        if not isinstance(e, dict):
            continue

        quote = str(e.get("quote", "")).strip()
        if not quote:
            continue

        normalized_quote = _v._norm(quote)
        passage_id = e.get("passage_id")

        try:
            index = int(passage_id) - 1
        except (TypeError, ValueError):
            index = -1

        if 0 <= index < len(passages):
            if normalized_quote in _v._norm(passages[index].text):
                verified_quotes.append(
                    str(e.get("stance", "")).strip().lower()
                )

    stances = {
        stance for stance in verified_quotes
        if stance in ("supports", "contradicts")
    }

    result = _v._build_result(claim, item, passages)

    # Conflicting verified evidence must not produce a firm verdict.
    if (
        stances == {"supports", "contradicts"}
        and result.verdict in ("supported", "contradicted")
    ):
        result.verdict = "ambiguous"
        result.category = "none"
        result.confidence = min(result.confidence, 0.6)
        result.explanation = (
            result.explanation
            + " (Evidence conflicts: verified passages both support "
              "and contradict this claim.)"
        ).strip()

    return result
