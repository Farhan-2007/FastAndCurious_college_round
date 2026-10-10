"""Second Opinion - AI/Core Logic (claim decomposition, retrieval, verification)."""
from .claim_extractor import decompose_claims, extract_claims
from .evidence_analyzer import analyze_claim
from .evidence_retriever import retrieve_evidence
from .llm_client import LLMClient, LLMError
from .schemas import CATEGORIES, VERDICTS, Claim, ClaimResult, EvidencePassage
from .verifier import verify_claims, verify_claims_batch

__all__ = ["decompose_claims", "retrieve_evidence", "verify_claims", "verify_claims_batch",
           "extract_claims", "analyze_claim", "LLMClient", "LLMError",
           "Claim", "ClaimResult", "EvidencePassage", "VERDICTS", "CATEGORIES"]



def run_ai_core(answer, pdf_chunks, client=None):
    claims = decompose_claims(answer, client=client)
    evidence_by_claim = {}

    for claim in claims:
        evidence_by_claim[claim["id"]] = retrieve_evidence(
            claim, pdf_chunks, top_k=5
        )

    verification = verify_claims(
        claims, evidence_by_claim, client=client
    )

    return {"claims": verification["claims"]}