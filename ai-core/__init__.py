"""Second Opinion - AI/Core Logic (claim extraction + verification)."""
from claim_extractor import extract_claims
from llm_client import LLMClient, LLMError
from schemas import CATEGORIES, VERDICTS, Claim, ClaimResult, EvidencePassage
from verifier import verify_claims

__all__ = ["extract_claims", "verify_claims", "LLMClient", "LLMError",
           "Claim", "ClaimResult", "EvidencePassage", "VERDICTS", "CATEGORIES"]