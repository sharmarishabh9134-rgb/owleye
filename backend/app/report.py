"""Draft a complaint the student can paste into cybercrime.gov.in (national portal) or read out on helpline 1930."""
from __future__ import annotations

from datetime import date


def draft_complaint(result: dict, inputs: dict) -> str:
    lines = [
        "COMPLAINT DRAFT: SUSPECTED FAKE INTERNSHIP / JOB OFFER",
        f"Date: {date.today().isoformat()}",
        "",
        "I received an internship offer that I believe is fraudulent.",
    ]
    if inputs.get("company"):
        lines.append(f"Company named in the offer: {inputs['company']}")
    if inputs.get("sender_email"):
        lines.append(f"Sender email: {inputs['sender_email']}")
    if inputs.get("url"):
        lines.append(f"Website / link: {inputs['url']}")
    lines += ["", f"Automated risk estimate: {result['score']}/100 ({result['level']}). Indicators found:"]
    for r in result["reasons"]:
        ev = f" [{r['evidence']}]" if r.get("evidence") else ""
        lines.append(f"- {r['label']}{ev}")
    text = (inputs.get("text") or "").strip()
    if text:
        lines += ["", "Message received (first 600 characters):", text[:600]]
    lines += ["", "Money lost (if any): INR ____   Payment method / transaction ID: ____",
              "My name: ____   Phone: ____   Email: ____",
              "", "Tip: attach screenshots of the offer, chat and payment receipt. For money already sent, call 1930 immediately."]
    return "\n".join(lines)
