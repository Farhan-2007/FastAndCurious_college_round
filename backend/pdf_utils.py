import fitz  # PyMuPDF


MAX_PDF_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_PDF_PAGES = 50
MIN_EXTRACTABLE_TEXT = 50
MIN_ANSWER_CHARACTERS = 10
MAX_ANSWER_CHARACTERS = 20_000


class PDFValidationError(Exception):
    """An upload error with an HTTP status suitable for the API."""

    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def validate_answer(answer: str) -> None:
    answer = answer.strip()

    if len(answer) < MIN_ANSWER_CHARACTERS:
        raise PDFValidationError(
            "Answer must contain at least 10 characters",
            422,
        )

    if len(answer) > MAX_ANSWER_CHARACTERS:
        raise PDFValidationError(
            "Answer must not exceed 20,000 characters",
            422,
        )


def extract_pdf(pdf_bytes: bytes, filename: str) -> dict:
    """Validate a PDF and return text chunks with 1-based page numbers."""

    if not filename or not filename.lower().endswith(".pdf"):
        raise PDFValidationError("File must be a PDF", 422)

    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise PDFValidationError("PDF exceeds the 10MB limit", 413)

    if not pdf_bytes.startswith(b"%PDF"):
        raise PDFValidationError("Not a valid PDF", 422)

    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise PDFValidationError("Cannot read PDF", 422) from exc

    try:
        if document.needs_pass:
            raise PDFValidationError("Password-protected PDFs are not supported", 422)

        page_count = document.page_count

        if page_count == 0:
            raise PDFValidationError("No pages found", 422)

        if page_count > MAX_PDF_PAGES:
            raise PDFValidationError("PDF exceeds the 50-page limit", 422)

        chunks = []
        pages_without_text = 0
        total_text_characters = 0

        for page_number, page in enumerate(document, start=1):
            text = page.get_text().strip()

            if not text:
                pages_without_text += 1
                continue

            chunks.append({
                "page": page_number,
                "text": text,
            })
            total_text_characters += len(text)

        if total_text_characters < MIN_EXTRACTABLE_TEXT:
            raise PDFValidationError(
                "No extractable text (the PDF may be scanned or empty)",
                422,
            )

        return {
            "chunks": chunks,
            "total_pages": page_count,
            "pages_without_text": pages_without_text,
            "total_text_characters": total_text_characters,
        }
    finally:
        document.close()