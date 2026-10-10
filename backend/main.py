from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


app = FastAPI(title="Second Opinion API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    detail = exc.detail
    message = detail["error"] if isinstance(detail, dict) else str(detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": message},
    )


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "llm": "not_configured",
        "fallback": "not_configured",
    }


@app.post("/api/audit")
async def create_audit(
    pdf: UploadFile = File(...),
    answer: str = Form(...),
    question: str = Form(""),
):
    if not (pdf.filename or "").lower().endswith(".pdf"):
        raise HTTPException(422, detail={"error": "File must be a PDF"})

    if not answer.strip():
        raise HTTPException(
            422,
            detail={"error": "Please provide the AI-generated answer"},
        )

    contents = await pdf.read()

    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(
            413,
            detail={"error": "PDF exceeds the 10MB limit"},
        )

    if not contents.startswith(b"%PDF"):
        raise HTTPException(
            422,
            detail={"error": "Not a valid PDF"},
        )

    audit_id = str(uuid4())

    # Temporary mock response for frontend integration.
    return {
        "audit_id": audit_id,
        "demo_mode": True,
        "overall": {
            "score": 62,
            "summary": "Demo result only; real verification is not connected yet.",
            "counts": {
                "supported": 5,
                "contradicted": 2,
                "insufficient": 2,
                "ambiguous": 1,
            },
            "source_coverage": {
                "pages_referenced": 8,
                "total_pages": 12,
                "claims_without_evidence": 2,
            },
        },
        "claims": [],
    }


@app.get("/api/audit/{audit_id}/status")
def get_audit_status(audit_id: str):
    return {
        "step": "Demo result ready",
        "progress": 100,
    }