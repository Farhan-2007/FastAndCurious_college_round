# Second Opinion - Data Integration Test Checklist

## 1. Normal PDF Test

**Test file:** `rivertown_bikeshare.pdf`

- [ ] Upload the original PDF.
- [ ] Enter the question from `question.txt`.
- [ ] Enter the AI-generated answer from `ai_answer.txt`.
- [ ] Check whether the answer is split into individual claims.
- [ ] Verify that each claim receives an appropriate verdict.
- [ ] Check whether evidence excerpts match the PDF content.
- [ ] Verify that the PDF page numbers are correct.
- [ ] Compare the results with `expected_results.json`.

## 2. Prompt Injection Test

**Test file:** `rivertown_bikeshare_injected.pdf`

- [ ] Upload the PDF containing the prompt-injection test.
- [ ] Use the same question and AI-generated answer.
- [ ] Check whether instructions embedded in the PDF are treated as untrusted content.
- [ ] Verify that the embedded instruction does not force every claim to be marked as `supported`.
- [ ] Check whether verdicts remain based on the actual evidence.
- [ ] Record any unexpected results.

**Note:** Do not assume that `expected_results.json` applies to the injected PDF unless expected results for that test have been defined.

## 3. Invalid Input Tests

- [ ] Try submitting without uploading a PDF.
- [ ] Try submitting an empty AI answer.
- [ ] Try uploading an invalid or unsupported file.
- [ ] Check whether appropriate error messages are displayed.

## 4. Verdict and Evidence Validation

- [ ] Verify that `supported` means the evidence supports the claim.
- [ ] Verify that `contradicted` means the evidence conflicts with the claim.
- [ ] Verify that `insufficient_evidence` is used when there is not enough evidence to determine whether a claim is true.
- [ ] Ensure that missing evidence is not automatically treated as proof that a claim is false.
- [ ] Check that explanations and evidence excerpts are relevant to each claim.

## 5. Frontend and Backend Integration

- [ ] Verify that the frontend sends the correct inputs to the Flask API.
- [ ] Check whether the backend returns a valid structured response.
- [ ] Verify that the frontend displays claims, verdicts, evidence, and explanations correctly.
- [ ] Check how the application handles API errors.
- [ ] Confirm that the application works from PDF upload to final results.

## 6. Bug Tracking

For every failed test, record the following information:

- **Test case:** Name of the test.
- **Expected result:** What should happen.
- **Actual result:** What happened.
- **Status:** Pass or Fail.
- **Issue:** Description of the problem.

## Testing Status

**Status:** Not tested yet.

**Important:** Mark a test as passed only after running it and verifying the result.