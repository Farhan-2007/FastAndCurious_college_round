import unittest

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


if __name__ == "__main__":
    unittest.main()