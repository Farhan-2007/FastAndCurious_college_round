
from ai_core import decompose_claims, retrieve_evidence, run_ai_core


def test_pipeline_in_mock_mode(monkeypatch):
    monkeypatch.setenv("SO_MOCK_VERIFICATION", "true")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    answer = (
        "The lab has 120 employees. "
        "The lab was established in 1990."
    )

    pdf_chunks = [
        {"page": 1, "text": "The laboratory employs 120 people."},
        {"page": 2, "text": "The laboratory opened in 2018."},
    ]

    result = run_ai_core(answer, pdf_chunks)

    assert result is not None

    claims = decompose_claims(answer)
    assert isinstance(claims, list)
    assert len(claims) > 0

    for claim in claims:
        evidence = retrieve_evidence(claim, pdf_chunks, top_k=5)
        assert isinstance(evidence, list)