import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


class ApiValidationTests(unittest.TestCase):

    def test_wrong_extension_returns_422(self):
        response = client.post(
            "/api/audit",
            data={"answer": "This answer is long enough."},
            files={"pdf": ("notes.txt", b"not a PDF", "text/plain")},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"], "File must be a PDF")

    def test_invalid_pdf_bytes_return_422(self):
        response = client.post(
            "/api/audit",
            data={"answer": "This answer is long enough."},
            files={"pdf": ("broken.pdf", b"not a PDF", "application/pdf")},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("PDF", response.json()["error"])

    def test_too_short_answer_returns_422(self):
        response = client.post(
            "/api/audit",
            data={"answer": "short"},
            files={"pdf": ("test.pdf", b"not a PDF", "application/pdf")},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("10 characters", response.json()["error"])

    def test_file_over_10mb_returns_413(self):
        # Make a file slightly larger than 10 MB.
        large_pdf = b"%PDF" + (b"x" * (10 * 1024 * 1024))

        response = client.post(
            "/api/audit",
            data={"answer": "This answer is long enough."},
            files={"pdf": ("large.pdf", large_pdf, "application/pdf")},
        )

        self.assertEqual(response.status_code, 413)
        self.assertIn("10MB", response.json()["error"])

    def test_cors_allows_frontend_port_5174(self):
        response = client.options(
            "/api/audit",
            headers={
                "Origin": "http://localhost:5174",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            "http://localhost:5174",
        )

    @patch("backend.main.verify_claims")
    @patch("backend.main.retrieve_evidence")
    @patch("backend.main.decompose_claims")
    @patch("backend.main.extract_pdf")
    def test_successful_audit_returns_frontend_response_shape(
        self,
        mock_extract_pdf,
        mock_decompose_claims,
        mock_retrieve_evidence,
        mock_verify_claims,
    ):
        mock_extract_pdf.return_value = {
            "chunks": [
                {
                    "page": 1,
                    "text": "Revenue increased by 15 percent.",
                }
            ],
            "total_pages": 1,
            "pages_without_text": 0,
            "total_text_characters": 32,
        }

        mock_decompose_claims.return_value = [
            {
                "id": "claim-1",
                "text": "Revenue increased by 15 percent",
            }
        ]

        mock_retrieve_evidence.return_value = [
            {
                "page": 1,
                "quote": "Revenue increased by 15 percent.",
            }
        ]

        mock_verify_claims.return_value = {
            "claims": [
                {
                    "id": "claim-1",
                    "text": "Revenue increased by 15 percent",
                    "verdict": "supported",
                    "explanation": "The source supports the claim.",
                    "confidence": 0.95,
                    "evidence": [
                        {
                            "page": 1,
                            "quote": "Revenue increased by 15 percent.",
                        }
                    ],
                }
            ]
        }

        response = client.post(
            "/api/audit",
            data={
                "answer": "Revenue increased by 15 percent.",
            },
            files={
                "pdf": (
                    "test.pdf",
                    b"mock PDF bytes",
                    "application/pdf",
                )
            },
        )

        self.assertEqual(response.status_code, 200)

        body = response.json()

        self.assertTrue(body["success"])
        self.assertFalse(body["demo_mode"])
        self.assertIn("audit_id", body)
        self.assertEqual(body["overall"]["score"], 100)
        self.assertEqual(
            body["overall"]["counts"]["supported"],
            1,
        )
        self.assertEqual(
            body["claims"][0]["verdict"],
            "supported",
        )
        self.assertEqual(
            body["claims"][0]["evidence"][0]["page"],
            1,
        )

        mock_verify_claims.assert_called_once()

    @patch("backend.main.verify_claims")
    @patch("backend.main.retrieve_evidence")
    @patch("backend.main.decompose_claims")
    @patch("backend.main.extract_pdf")
    def test_verification_failure_returns_503(
        self,
        mock_extract_pdf,
        mock_decompose_claims,
        mock_retrieve_evidence,
        mock_verify_claims,
    ):
        mock_extract_pdf.return_value = {
            "chunks": [
                {
                    "page": 1,
                    "text": "Revenue increased by 15 percent.",
                }
            ],
            "total_pages": 1,
            "pages_without_text": 0,
            "total_text_characters": 32,
        }

        mock_decompose_claims.return_value = [
            {
                "id": "claim-1",
                "text": "Revenue increased by 15 percent",
            }
        ]

        mock_retrieve_evidence.return_value = [
            {
                "page": 1,
                "quote": "Revenue increased by 15 percent.",
            }
        ]

        mock_verify_claims.return_value = {
            "claims": [
                {
                    "id": "claim-1",
                    "text": "Revenue increased by 15 percent",
                    "error": "Simulated verification failure",
                }
            ]
        }

        response = client.post(
            "/api/audit",
            data={
                "answer": "Revenue increased by 15 percent.",
            },
            files={
                "pdf": (
                    "test.pdf",
                    b"mock PDF bytes",
                    "application/pdf",
                )
            },
        )

        self.assertEqual(response.status_code, 503)

        body = response.json()

        self.assertEqual(
            body["code"],
            "VERIFICATION_FAILED",
        )
        self.assertTrue(body["retryable"])
        self.assertEqual(body["total_claims"], 1)
        self.assertEqual(body["failed_claims"], 1)


if __name__ == "__main__":
    unittest.main()