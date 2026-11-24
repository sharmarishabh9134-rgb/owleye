"""Combine signals into an explainable 0-100 risk score."""
from __future__ import annotations

from dataclasses import asdict
from math import prod

from . import checks
from .platforms import PLATFORMS
from .report import draft_complaint

LOW_MAX, MEDIUM_MAX = 24, 54  # 0-24 LOW, 25-54 MEDIUM, 55+ HIGH

ADVICE = {
    "HIGH": "Do not pay or share documents. Verify the company on its official website, LinkedIn or the MCA portal, "
            "then report it at cybercrime.gov.in or call 1930.",
    "MEDIUM": "Proceed with caution. Confirm the recruiter through the company's official careers page before "
              "sharing personal data or money.",
    "LOW": "No major red flags in what you provided. Still verify on the company's official site, and never pay "
           "to get an internship.",
}


def combine(weights: list[int]) -> int:
    """Noisy-OR: each signal independently raises risk; more signals compound, never exceed 100."""
    return round(100 * (1 - prod(1 - w / 100 for w in weights)))


def level_for(score: int) -> str:
    return "LOW" if score <= LOW_MAX else "MEDIUM" if score <= MEDIUM_MAX else "HIGH"


def analyze(text: str = "", url: str | None = None, sender_email: str | None = None,
            company: str | None = None, live: bool = True) -> dict:
    signals: list[checks.Signal] = list(checks.text_signals(text))
    urls = ([url] if url else []) + checks.find_urls(text)
    urls = list(dict.fromkeys(urls))[:5]
    for u in urls:
        signals += checks.url_signals(u)
    if sender_email:
        signals += checks.sender_signals(sender_email, company, text)

    unavailable: list[str] = []
    if live:
        hosts = []
        for u in urls[:2]:
            h = checks.urlparse(u if "://" in u else "//" + u).hostname
            if h and h not in hosts:
                hosts.append(h.lower())
        if sender_email and "@" in sender_email:
            d = sender_email.rsplit("@", 1)[-1].lower()
            if d not in checks.FREE_MAIL and d not in hosts:
                hosts.append(d)
        for h in hosts[:2]:
            sig, na = checks.domain_signals(h)
            signals += sig
            unavailable += na

    best: dict[str, checks.Signal] = {}
    for s in signals:                      # one signal per id: no double counting
        if s.id not in best or s.weight > best[s.id].weight:
            best[s.id] = s
    ranked = sorted(best.values(), key=lambda s: -s.weight)

    score = combine([s.weight for s in ranked])
    level = level_for(score)
    result = {
        "score": score,
        "level": level,
        "reasons": [asdict(s) for s in ranked],
        "unavailable_checks": unavailable,
        "recommendation": ADVICE[level],
        "safe_alternatives": [{"name": p["name"], "url": p["url"], "type": p["type"]} for p in PLATFORMS[:6]] if level != "LOW" else [],
        "disclaimer": "Heuristic risk estimate based on the details you provided, not proof of fraud.",
    }
    result["report_draft"] = draft_complaint(result, {"text": text, "url": url, "sender_email": sender_email, "company": company}) if level != "LOW" else None
    return result
