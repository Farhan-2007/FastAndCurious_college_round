
import json
from pathlib import Path

import requests

BASE_URL = "http://127.0.0.1:8000"
TEST_DIR = Path("data-integration/test_cases")

pdf_path = TEST_DIR / "rivertown_bikeshare.pdf"
answer_path = TEST_DIR / "ai_answer.txt"
question_path = TEST_DIR / "question.txt"

# Verify the test files exist.
for path in (pdf_path, answer_path, question_path):
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

answer = answer_path.read_text(encoding="utf-8")
question = question_path.read_text(encoding="utf-8")

print("Sending Rivertown audit request...")

with pdf_path.open("rb") as pdf_file:
    response = requests.post(
        f"{BASE_URL}/api/audit",
        files={
            "pdf": (
                pdf_path.name,
                pdf_file,
                "application/pdf",
            )
        },
        data={
            "answer": answer,
            "question": question,
        },
        timeout=180,
    )

print(f"HTTP status: {response.status_code}")

try:
    result = response.json()
except ValueError:
    print(response.text)
    raise SystemExit("The API returned a non-JSON response.")

print(json.dumps(result, indent=2, ensure_ascii=False))

if response.ok:
    output_path = TEST_DIR / "live_api_result.json"
    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nSaved response to: {output_path}")
