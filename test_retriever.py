from ai_core.evidence_retriever import retrieve_evidence

claim = {"id": 1, "text": "The laboratory employs 120 people."}

chunks = [
{"page": 1, "text": "The laboratory employs 120 people."},
{"page": 2, "text": "The laboratory opened in 2018."},
{"page": 3, "text": "The laboratory has a research department."}
]

result = retrieve_evidence(claim, chunks, top_k=2)

print("Retrieved evidence:")
print(result)


from ai_core import retrieve_evidence

chunks = [
    {"page": 1, "text": "The laboratory employs 120 people."},
    {"page": 2, "text": "The laboratory opened in 2018."}
]

claim = {"id": 2, "text": "The lab was established in 1990."}

evidence = retrieve_evidence(claim, chunks, top_k=5)

print("Retrieved evidence:", evidence)