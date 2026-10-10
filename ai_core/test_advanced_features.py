
from advanced_features import (
    build_heatmap,
    assess_source_quality,
    generate_corrected_answer,
)

claims = [
    {
        "id": 1,
        "text": "The lab has 120 employees.",
        "verdict": "supported",
        "category": "none",
        "confidence": 0.95,
        "explanation": "The evidence supports the claim.",
        "evidence": [
            {"quote": "The laboratory employs 120 people.", "page": 1}
        ],
    },
    {
        "id": 2,
        "text": "The lab was established in 1990.",
        "verdict": "contradicted",
        "category": "hallucination",
        "confidence": 0.95,
        "explanation": "The evidence says it opened in 2018.",
        "evidence": [
            {"quote": "The laboratory opened in 2018.", "page": 2}
        ],
    },
    {
        "id": 3,
        "text": "The laboratory has five branches.",
        "verdict": "insufficient",
        "category": "unsupported",
        "confidence": 0.8,
        "explanation": "There is no supporting evidence.",
        "evidence": [],
    },
]

print("\n--- FEATURE 2: HEATMAP ---")
print(build_heatmap(claims))

print("\n--- FEATURE 6: SOURCE QUALITY ---")
print(assess_source_quality(claims))

print("\n--- FEATURE 3: CORRECTED ANSWER MOCK TEST ---")
import os
os.environ["SO_MOCK_VERIFICATION"] = "true"

print(
    generate_corrected_answer(
        "The lab has 120 employees and was established in 1990.",
        claims,
    )
)


print("\n--- EDGE CASE 1: EMPTY CLAIMS ---")
print("Heatmap:", build_heatmap([]))
print("Source quality:", assess_source_quality([]))


print("\n--- EDGE CASE 2: VERIFICATION ERROR ---")
error_claims = [
    {
        "id": 4,
        "text": "Example claim",
        "verdict": "ambiguous",
        "category": "none",
        "confidence": 0.0,
        "error": "Verification failed",
        "evidence": [],
    }
]
print("Heatmap:", build_heatmap(error_claims))
print("Source quality:", assess_source_quality(error_claims))


print("\n--- EDGE CASE 3: AMBIGUOUS CLAIM ---")
ambiguous_claims = [
    {
        "id": 5,
        "text": "The project started in 2020.",
        "verdict": "ambiguous",
        "category": "none",
        "confidence": 0.5,
        "evidence": [
            {"quote": "The project started in 2020.", "page": 1},
            {"quote": "The project started in 2022.", "page": 2},
        ],
    }
]
print("Heatmap:", build_heatmap(ambiguous_claims))
print("Source quality:", assess_source_quality(ambiguous_claims))


print("\n--- EDGE CASE 4: MISSING METADATA ---")
metadata_claims = [
    {
        "id": 6,
        "text": "The lab has 120 employees.",
        "verdict": "supported",
        "category": "none",
        "confidence": 0.95,
        "evidence": [
            {"quote": "The laboratory employs 120 people."}
        ],
    }
]
print("Heatmap:", build_heatmap(metadata_claims))
print("Source quality:", assess_source_quality(metadata_claims))