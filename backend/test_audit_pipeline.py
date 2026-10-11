from unittest.mock import patch

from backend.audit_pipeline import run_audit_pipeline


@patch("backend.audit_pipeline.verify_claims")
@patch("backend.audit_pipeline.retrieve_evidence")
@patch("backend.audit_pipeline.decompose_claims")
def test_unverified_quote_downgrades_supported_claim(
    mock_decompose,
    mock_retrieve,
    mock_verify,
):
    mock_decompose.return_value = [
        {"id": 1, "text": "The service has 500 bikes."}
    ]

    mock_retrieve.return_value = [
        {"page": 1, "text": "The report describes the service."}
    ]

    mock_verify.return_value = {
        "claims": [
            {
                "id": 1,
                "verdict": "supported",
                "category": "none",
                "confidence": 0.95,
                "explanation": "The source supports the claim.",
                "evidence": [
                    {"quote": "The service has 500 bikes.", "page": 1}
                ],
            }
        ]
    }

    pdf_chunks = [
        {"page": 1, "text": "The report describes the service."}
    ]

    result = run_audit_pipeline(
        answer="The service has 500 bikes.",
        pdf_chunks=pdf_chunks,
        total_pages=1,
    )

    claim = result["claims"][0]

    assert claim["verdict"] == "ambiguous"
    assert claim["category"] == "none"
    assert claim["confidence"] <= 0.3
    assert claim["evidence"] == []
    assert "Downgraded" in claim["explanation"]

@patch("backend.audit_pipeline.verify_claims")
@patch("backend.audit_pipeline.retrieve_evidence")
@patch("backend.audit_pipeline.decompose_claims")
def test_verification_error_is_preserved_and_not_presented_as_valid(
    mock_decompose,
    mock_retrieve,
    mock_verify,
):
    mock_decompose.return_value = [
        {"id": 1, "text": "The service has 500 bikes."}
    ]

    mock_retrieve.return_value = [
        {"page": 1, "text": "The report describes the service."}
    ]

    mock_verify.return_value = {
        "claims": [
            {
                "id": 1,
                "verdict": "supported",
                "category": "none",
                "confidence": 0.95,
                "explanation": "Verification failed.",
                "evidence": [
                    {"quote": "The service has 500 bikes.", "page": 1}
                ],
                "error": "AI provider quota exceeded",
            }
        ]
    }

    result = run_audit_pipeline(
        answer="The service has 500 bikes.",
        pdf_chunks=[
            {"page": 1, "text": "The service has 500 bikes."}
        ],
        total_pages=1,
    )

    claim = result["claims"][0]

    assert claim["verdict"] == "ambiguous"
    assert claim["category"] == "none"
    assert claim["confidence"] == 0.0
    assert claim["evidence"] == []
    assert claim["error"] == "AI provider quota exceeded"
    assert "Verification failed" in claim["explanation"]