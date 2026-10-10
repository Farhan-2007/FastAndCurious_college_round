# Second Opinion - Integration Notes

## Purpose

Define the information required to connect the React frontend, FastAPI backend, and data-integration test dataset.

## Input Requirements

1. Original source PDF.
2. Audit question from `question.txt`.
3. AI-generated answer from `ai_answer.txt`.

## Expected Processing Flow

1. User uploads a PDF and provides the AI-generated answer.
2. Backend extracts PDF text and page numbers.
3. AI processing identifies individual claims in the answer.
4. Each claim is checked against relevant evidence.
5. Each claim receives one of the following verdicts:
   - `supported`
   - `contradicted`
   - `insufficient`
   - `ambiguous`
6. Backend returns structured results to the frontend.
7. Frontend displays each claim, its verdict, evidence, and explanation.

## Expected Result Fields

The following fields are proposed for integration and must be confirmed with the backend developer.

- Claim text
- Verdict
- Evidence excerpt
- PDF page number
- Explanation
- Confidence score, if implemented

## Error Handling

- Missing PDF
- Empty AI-generated answer
- Invalid PDF
- PDF text extraction failure
- API processing failure

## Integration Checklist

- [ ] Confirm the API endpoint with the backend developer.
- [ ] Confirm whether the endpoint accepts multipart form data or another request format.
- [ ] Confirm the names of the input fields.
- [ ] Confirm the response JSON structure.
- [ ] Confirm the format used for verdicts and page numbers.
- [ ] Test the frontend against the backend.
- [ ] Run the original PDF test.
- [ ] Run the prompt-injection test.

**Note:** This document records proposed requirements, not a confirmed API contract. Update it after discussing the actual implementation with the team.