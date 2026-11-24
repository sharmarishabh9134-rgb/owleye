import sys

if sys.version_info < (3, 10):
    raise SystemExit("OwlEye needs Python 3.10 or newer. Install it from python.org and try again.")

import os
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StringConstraints

from . import assistant, report, scoring
from .platforms import PLATFORMS, SAFE_TIPS

ROOT = Path(__file__).resolve().parents[2]
app = FastAPI(title="OwlEye", version="0.2.0",
              description="Verify an internship offer before you apply or pay.")

Short = Annotated[str, StringConstraints(max_length=200)]


class AnalyzeRequest(BaseModel):
    text: str = Field("", max_length=20000, description="Offer letter / WhatsApp / email text")
    url: str | None = Field(None, max_length=2048)
    sender_email: str | None = Field(None, max_length=254)
    company: str | None = Field(None, max_length=200)
    live: bool = Field(True, description="Run live domain-age / TLS lookups")


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=1000)


class ScanContext(BaseModel):
    score: int = Field(..., ge=0, le=100)
    level: Literal["LOW", "MEDIUM", "HIGH"]
    reasons: list[Short] = Field(default_factory=list, max_length=12)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=20)
    context: ScanContext | None = None


class ComplaintRequest(BaseModel):
    what_happened: str = Field(..., min_length=10, max_length=5000)
    scammer_company: str = Field("", max_length=200)
    scammer_contact: str = Field("", max_length=500)
    incident_date: str = Field("", max_length=50)
    amount_lost: str = Field("", max_length=50)
    payment_method: str = Field("", max_length=200)
    transaction_id: str = Field("", max_length=100)
    your_name: str = Field("", max_length=100)
    your_phone: str = Field("", max_length=30)
    your_email: str = Field("", max_length=200)
    scan_reasons: list[Short] = Field(default_factory=list, max_length=15)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    if not (req.text.strip() or req.url or req.sender_email):
        raise HTTPException(status_code=422, detail="Provide at least the offer text, a link or the sender email.")
    live = req.live and os.getenv("OWLEYE_OFFLINE") != "1"
    return scoring.analyze(req.text, req.url, req.sender_email, req.company, live)


@app.get("/api/platforms")
def platforms():
    return {"platforms": PLATFORMS, "tips": SAFE_TIPS}


@app.post("/api/chat")
def chat(req: ChatRequest, request: Request):
    ip = request.client.host if request.client else "unknown"
    if not assistant.allow(ip):
        raise HTTPException(status_code=429, detail="Too many messages. Please wait a minute.")
    if req.messages[-1].role != "user":
        raise HTTPException(status_code=422, detail="The last message must be from the user.")
    return assistant.reply([m.model_dump() for m in req.messages],
                           req.context.model_dump() if req.context else None)


@app.post("/api/complaint")
def complaint(req: ComplaintRequest):
    """Prepare a paste-ready complaint. Nothing is stored or sent anywhere."""
    f = req.model_dump()
    urgent = report.is_urgent(f)
    return {
        "complaint": report.build_user_complaint(f),
        "urgent": urgent,
        "portal_url": report.PORTAL_URL,
        "helpline": report.HELPLINE,
        "steps": report.filing_steps(urgent),
        "report_email": os.getenv("OWLEYE_REPORT_EMAIL", ""),
    }


# static files last so /api routes win
app.mount("/samples", StaticFiles(directory=ROOT / "samples"), name="samples")
app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="ui")
