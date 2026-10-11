from ai_core.claim_extractor import decompose_claims

answer = """
The laboratory employs 120 people.
The laboratory opened in 2018.
"""

result = decompose_claims(answer)

print("Extracted claims:")
print(result)
