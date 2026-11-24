import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import scoring

ROOT = Path(__file__).resolve().parents[2]
app = FastAPI(title="OwlEye", version="0.1.0",
              description="Verify an internship offer before you apply or pay.")


class AnalyzeRequest(BaseModel):
    text: str = Field("", max_length=20000, description="Offer letter / WhatsApp / email text")
    url: str | None = Field(None, max_length=2048)
    sender_email: str | None = Field(None, max_length=254)
    company: str | None = Field(None, max_length=200)
    live: bool = Field(True, description="Run live domain-age / TLS lookups")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    if not (req.text.strip() or req.url or req.sender_email):
        raise HTTPException(status_code=422, detail="Provide at least the offer text, a link or the sender email.")
    live = req.live and os.getenv("OWLEYE_OFFLINE") != "1"
    return scoring.analyze(req.text, req.url, req.sender_email, req.company, live)


# static files last so /api routes win
app.mount("/samples", StaticFiles(directory=ROOT / "samples"), name="samples")
app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="ui")
