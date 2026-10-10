
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
TEST_DIR = BASE_DIR / "test_cases"

EXPECTED_FILE = TEST_DIR / "expected_results.json"
ACTUAL_FILE = TEST_DIR / "api_result.json"

with EXPECTED_FILE.open(encoding="utf-8") as f:
    expected_data = json.load(f)

if not ACTUAL_FILE.exists():
    print("API result file not found:", ACTUAL_FILE)
    print("Save a real API response as api_result.json before comparing.")
    raise SystemExit(1)

with ACTUAL_FILE.open(encoding="utf-8") as f:
    actual_data = json.load(f)

expected_claims = expected_data["claims"]
actual_claims = actual_data.get("claims", [])

if not actual_claims:
    print("BLOCKED: API returned no claims.")
    print("Current demo responses cannot verify claim accuracy.")
    raise SystemExit(1)

expected_by_id = {c["id"]: c["expected_verdict"] for c in expected_claims}
actual_by_id = {c["id"]: c["verdict"] for c in actual_claims if "id" in c and "verdict" in c}

print(f"Expected claims: {len(expected_by_id)}")
print(f"Returned claims: {len(actual_claims)}")

matched = 0
mismatches = []
missing = []

for claim_id, expected_verdict in expected_by_id.items():
    if claim_id not in actual_by_id:
        missing.append(claim_id)
        continue

    actual_verdict = actual_by_id[claim_id]

    if actual_verdict == expected_verdict:
        matched += 1
    else:
        mismatches.append(
            (claim_id, expected_verdict, actual_verdict)
        )

extra_ids = sorted(set(actual_by_id) - set(expected_by_id))

print(f"\nMatching verdicts: {matched}")
print(f"Verdict mismatches: {len(mismatches)}")
print(f"Missing claim IDs: {missing}")
print(f"Unexpected claim IDs: {extra_ids}")

if mismatches:
    print("\nMISMATCH DETAILS")
    for claim_id, expected, actual in mismatches:
        print(f"Claim {claim_id}: expected={expected}, actual={actual}")

if not mismatches and not missing and not extra_ids:
    print("\nAll claim verdicts match the expected results.")
