
import os

from ai_core.verifier import verify_claims


def test_verify_claims_in_mock_mode(monkeypatch):
    monkeypatch.setenv("SO_MOCK_VERIFICATION", "true")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    claims = [
        {"id": 1, "text": "The lab has 120 employees."},
        {"id": 2, "text": "The lab was established in 1990."},
    ]

    evidence_by_claim = {
        1: [
            {
                "page": 1,
                "text": "The laboratory employs 120 people.",
            }
        ],
        2: [
            {
                "page": 2,
                "text": "The laboratory opened in 2018.",
            }
        ],
    }

    result = verify_claims(claims, evidence_by_claim)

    assert "claims" in result
    assert len(result["claims"]) == 2

    for claim in result["claims"]:
        assert "verdict" in claim
        assert "error" not in claim, claim.get("error")