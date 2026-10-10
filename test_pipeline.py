from ai_core import decompose_claims, retrieve_evidence
from ai_core import run_ai_core

answer = (
    "The lab has 120 employees. "
    "The lab was established in 1990."
)

pdf_chunks = [
    {"page": 1, "text": "The laboratory employs 120 people."},
    {"page": 2, "text": "The laboratory opened in 2018."}
]

result = run_ai_core(answer, pdf_chunks)
print(result)

claims = decompose_claims(answer)
print("Claims:", claims)

for claim in claims:
    evidence = retrieve_evidence(claim, pdf_chunks, top_k=5)
    print("Claim:", claim["text"])
    print("Evidence:", evidence)


# answer = (
#     "The lab has 120 employees. "
#     "The lab was established in 1990."
# )

# pdf_chunks = [
#     {"page": 1, "text": "The laboratory employs 120 people."},
#     {"page": 2, "text": "The laboratory opened in 2018."}
# ]

# result = run_ai_core(answer, pdf_chunks)
# print(result)