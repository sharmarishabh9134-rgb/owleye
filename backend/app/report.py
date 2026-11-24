"""Complaint drafts for cybercrime.gov.in (national portal) or helpline 1930.

OwlEye cannot file on the portal for the user (it needs the user's own login and OTP), so it prepares
a complete, paste-ready text instead.
"""
from __future__ import annotations

import re
from datetime import date

PORTAL_URL = "https://cybercrime.gov.in"
HELPLINE = "1930"
_URGENT = re.compile(r"\b(paid|sent|transferred|deposited|lost|deducted|scammed|cheated)\b", re.I)


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
              "", f"Tip: attach screenshots of the offer, chat and payment receipt. For money already sent, call {HELPLINE} immediately."]
    return "\n".join(lines)


def is_urgent(f: dict) -> bool:
    return bool(f.get("amount_lost", "").strip() or f.get("transaction_id", "").strip()
                or _URGENT.search(f.get("what_happened", "")))


def build_user_complaint(f: dict) -> str:
    def add(label: str, key: str, out: list[str]):
        if f.get(key, "").strip():
            out.append(f"{label}: {f[key].strip()}")

    out = ["COMPLAINT: SUSPECTED FRAUDULENT INTERNSHIP / JOB OFFER", f"Date of report: {date.today().isoformat()}"]
    add("Date of incident", "incident_date", out)
    out += ["", "WHAT HAPPENED", f["what_happened"].strip(), "", "ABOUT THE OFFENDER"]
    add("Company / name used", "scammer_company", out)
    add("Phone / email / website / social handle", "scammer_contact", out)
    if len(out) and out[-1] == "ABOUT THE OFFENDER":
        out.append("Not known")
    out += ["", "MONEY AND PAYMENT"]
    mark = len(out)
    add("Amount lost (INR)", "amount_lost", out)
    add("Payment method", "payment_method", out)
    add("Transaction ID / UTR", "transaction_id", out)
    if len(out) == mark:
        out.append("No money lost so far")
    if f.get("scan_reasons"):
        out += ["", "AUTOMATED CHECK BY OWLEYE (heuristic, not proof)"] + [f"- {r}" for r in f["scan_reasons"]]
    out += ["", "COMPLAINANT"]
    add("Name", "your_name", out)
    add("Phone", "your_phone", out)
    add("Email", "your_email", out)
    out += ["", "Attachments to add: screenshots of the offer/chat, payment receipt, sender profile or website."]
    return "\n".join(out)


def filing_steps(urgent: bool) -> list[str]:
    steps = []
    if urgent:
        steps.append(f"Money or data may be at risk: call {HELPLINE} now and tell your bank / UPI app.")
    steps += [
        f"Open {PORTAL_URL}, start a new report and paste this complaint into the incident description.",
        "Attach screenshots of the offer, chats and any payment receipt.",
        "Tell your college placement cell, and the company being impersonated (use its official contact).",
        "Keep the acknowledgement / complaint number the portal gives you.",
    ]
    return steps
