
from ai_core.verifier import verify_claims

claims = [
    {"id": 1, "text": "The lab has 120 employees."},
    {"id": 2, "text": "The lab was established in 1990."}
]

evidence_by_claim = {
    1: [
        {
            "page": 1,
            "text": "The laboratory employs 120 people."
        }
    ],
    2: [
        {
            "page": 2,
            "text": "The laboratory opened in 2018."
        }
    ]
}

result = verify_claims(claims, evidence_by_claim)

print(result)