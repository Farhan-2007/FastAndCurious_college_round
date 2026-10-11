import unittest

from backend.report_utils import build_overall_report


class ReportUtilsTests(unittest.TestCase):

    def test_weighted_score_and_counts(self):
        claims = [
            {
                "verdict": "supported",
                "importance": 4,
                "evidence": [{"quote": "A source quote", "page": 1}],
            },
            {
                "verdict": "contradicted",
                "importance": 2,
                "evidence": [{"quote": "Another quote", "page": 2}],
            },
        ]

        report = build_overall_report(claims, total_pages=3)

        # 4 supported importance points out of 6 total = 67%.
        self.assertEqual(report["score"], 67)
        self.assertEqual(report["counts"]["supported"], 1)
        self.assertEqual(report["counts"]["contradicted"], 1)
        self.assertEqual(report["source_coverage"]["pages_referenced"], 2)
        self.assertEqual(report["source_coverage"]["claims_without_evidence"], 0)

    def test_claim_without_evidence_is_counted(self):
        claims = [
            {
                "verdict": "insufficient",
                "importance": 3,
                "evidence": [],
            },
        ]

        report = build_overall_report(claims, total_pages=5)

        self.assertEqual(report["score"], 0)
        self.assertEqual(report["source_coverage"]["pages_referenced"], 0)
        self.assertEqual(report["source_coverage"]["claims_without_evidence"], 1)

    def test_invalid_page_is_not_counted(self):
        claims = [
            {
                "verdict": "supported",
                "importance": 3,
                "evidence": [{"quote": "Quote", "page": 20}],
            },
        ]

        report = build_overall_report(claims, total_pages=5)

        self.assertEqual(report["source_coverage"]["pages_referenced"], 0)
        self.assertEqual(report["source_coverage"]["claims_without_evidence"], 1)

    def test_critical_unsafe_claim_is_mentioned(self):
        claims = [
            {
                "verdict": "contradicted",
                "category": "unsafe",
                "importance": 5,
                "evidence": [],
            },
        ]

        report = build_overall_report(claims, total_pages=2)

        self.assertIn("high-importance unsafe claim", report["summary"])

    def test_empty_claim_list(self):
        report = build_overall_report([], total_pages=4)

        self.assertEqual(report["score"], 0)
        self.assertEqual(report["counts"]["supported"], 0)
        self.assertEqual(report["source_coverage"]["total_pages"], 4)
        self.assertIn("No claims", report["summary"])

    def test_invalid_verdict_is_rejected(self):
        claims = [{"verdict": "yes"}]

        with self.assertRaises(ValueError):
            build_overall_report(claims, total_pages=1)


if __name__ == "__main__":
    unittest.main()