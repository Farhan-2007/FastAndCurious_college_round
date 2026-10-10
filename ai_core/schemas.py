"""Data shapes and allowed values shared by all ai-core modules."""
from dataclasses import asdict, dataclass, field
from typing import Optional

VERDICTS = ("supported", "contradicted", "insufficient", "ambiguous")
CATEGORIES = ("hallucination", "unsupported", "logic", "unsafe", "none")


@dataclass
class Claim:
    id: int
    text: str  # exact substring of the original answer

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EvidencePassage:
    text: str
    page: Optional[int] = None    # only set if the caller knows it
    source: Optional[str] = None  # e.g. filename, optional


@dataclass
class EvidenceQuote:
    quote: str                    # verified to appear in a supplied passage
    page: Optional[int] = None    # copied from the passage, never from the LLM
    source: Optional[str] = None


@dataclass
class ClaimResult:
    claim_id: int
    claim_text: str
    verdict: str
    category: str
    confidence: float             # 0.0 - 1.0
    explanation: str
    evidence: list = field(default_factory=list)  # list[EvidenceQuote]
    error: Optional[str] = None   # set only when verification itself failed

    def to_dict(self) -> dict:
        return asdict(self)


def coerce_claims(claims) -> list:
    """Accept list of str / dict{'id','text'} / Claim -> list[Claim]."""
    out = []
    for i, c in enumerate(claims or [], 1):
        if isinstance(c, Claim):
            out.append(c)
        elif isinstance(c, str) and c.strip():
            out.append(Claim(id=i, text=c))
        elif isinstance(c, dict) and str(c.get("text", "")).strip():
            out.append(Claim(id=int(c.get("id", i)), text=str(c["text"])))
        else:
            raise ValueError(f"Unsupported claim at position {i}: {c!r}")
    return out


def coerce_passages(evidence) -> list:
    """Accept str / dict{'text','page','source'} / EvidencePassage -> list[EvidencePassage]."""
    if isinstance(evidence, (str, dict, EvidencePassage)):
        evidence = [evidence]
    out = []
    for e in evidence or []:
        if isinstance(e, EvidencePassage):
            p = e
        elif isinstance(e, str):
            p = EvidencePassage(text=e)
        elif isinstance(e, dict):
            page = e.get("page")
            p = EvidencePassage(text=str(e.get("text", "")),
                                page=int(page) if page is not None else None,
                                source=e.get("source"))
        else:
            raise ValueError(f"Unsupported evidence item: {e!r}")
        if p.text.strip():
            out.append(p)
    return out