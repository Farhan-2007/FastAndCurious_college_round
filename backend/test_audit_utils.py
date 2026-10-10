import unittest

from backend.audit_utils import compute_span, validate_quote


class AuditUtilsTests(unittest.TestCase):

    def test_compute_span_exact_match(self):
        answer = "The report says revenue increased by 15 percent."
        claim = "revenue increased by 15 percent"

        span = compute_span(claim, answer)

        self.assertIsNotNone(span)
        self.assertEqual(answer[span["start"]:span["end"]], claim)

    def test_compute_span_whitespace_difference(self):
        answer = "The report says revenue increased by 15 percent."
        claim = "revenue increased by 15\npercent"

        span = compute_span(claim, answer)

        self.assertIsNotNone(span)
        highlighted_text = answer[span["start"]:span["end"]]
        self.assertEqual(" ".join(highlighted_text.split()), " ".join(claim.split()))

    def test_compute_span_uses_matching_sentence_fallback(self):
        answer = (
            "The report was published last year. "
            "Revenue increased by 15 percent during the study."
        )
        claim = "Revenue increased by 15 percent during the study."

        span = compute_span(claim, answer)

        self.assertIsNotNone(span)
        self.assertEqual(answer[span["start"]:span["end"]], claim)

    def test_compute_span_returns_none_for_unrelated_claim(self):
        answer = "The report discusses annual revenue."
        claim = "The moon is made of cheese."

        self.assertIsNone(compute_span(claim, answer))

    def test_validate_quote_returns_matching_page(self):
        chunks = [
            {"page": 1, "text": "Introduction to the report."},
            {"page": 4, "text": "Revenue increased by 15 percent."},
        ]

        is_valid, page = validate_quote(
            "Revenue increased by 15 percent",
            chunks,
        )

        self.assertTrue(is_valid)
        self.assertEqual(page, 4)

    def test_validate_quote_ignores_whitespace_differences(self):
        chunks = [
            {"page": 2, "text": "Revenue increased\nby 15   percent."},
        ]

        is_valid, page = validate_quote(
            "Revenue increased by 15 percent",
            chunks,
        )

        self.assertTrue(is_valid)
        self.assertEqual(page, 2)

    def test_validate_quote_rejects_missing_quote(self):
        chunks = [
            {"page": 1, "text": "Revenue increased by 15 percent."},
        ]

        is_valid, page = validate_quote(
            "Revenue decreased by 90 percent",
            chunks,
        )

        self.assertFalse(is_valid)
        self.assertIsNone(page)

    def test_validate_quote_rejects_empty_quote(self):
        is_valid, page = validate_quote(
            "   ",
            [{"page": 1, "text": "Some source text."}],
        )

        self.assertFalse(is_valid)
        self.assertIsNone(page)


if __name__ == "__main__":
    unittest.main()