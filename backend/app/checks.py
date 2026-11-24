"""Heuristic evidence checks for OwlEye.

Every check returns Signal objects. Network checks are best-effort: when a lookup
cannot be completed it is reported as "unavailable" and adds NO risk, so a flaky
network never makes an offer look worse than it is.
"""
from __future__ import annotations

import ipaddress
import re
import socket
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx


@dataclass
class Signal:
    id: str
    label: str          # plain-language reason shown to the student
    weight: int         # 0-100: how strongly this signal suggests a scam
    category: str       # payment | identity | pressure | content | domain
    evidence: str = ""  # the exact text / value that triggered it


FREE_MAIL = {"gmail.com", "yahoo.com", "yahoo.in", "outlook.com", "hotmail.com", "rediffmail.com",
             "proton.me", "protonmail.com", "icloud.com", "aol.com", "live.com", "ymail.com"}
SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "cutt.ly", "rb.gy", "goo.gl", "is.gd", "shorturl.at", "tiny.cc"}
RISKY_TLDS = {"xyz", "top", "click", "work", "site", "icu", "buzz", "shop", "live", "cfd", "sbs", "rest"}
GENERIC_COMPANY_WORDS = {"pvt", "ltd", "private", "limited", "technologies", "technology", "solutions", "services",
                         "india", "systems", "labs", "software", "global", "group", "and", "the", "inc", "llp"}
# brand -> official domains (a small demo list; the real system would use a registry lookup)
BRANDS = {
    "tcs": ("tcs.com",), "infosys": ("infosys.com",), "wipro": ("wipro.com",), "google": ("google.com",),
    "microsoft": ("microsoft.com",), "amazon": ("amazon.com", "amazon.in", "amazon.jobs"),
    "flipkart": ("flipkart.com",), "accenture": ("accenture.com",), "deloitte": ("deloitte.com",),
    "ibm": ("ibm.com",), "cognizant": ("cognizant.com",), "capgemini": ("capgemini.com",),
    "techmahindra": ("techmahindra.com",), "hcl": ("hcltech.com", "hcl.com"),
}

_CTX = r"(?:careers|hr|recruit\w*|hiring|talent|human\s+resources|pvt|ltd|limited|technologies|consultancy|internship|team)"
_BRAND_RES = {b: re.compile(rf"\b{b}\b[\s\w,.&-]{{0,20}}\b{_CTX}\b|\b{_CTX}\b[\s\w,.&-]{{0,20}}\b{b}\b", re.I) for b in BRANDS}

_FEE = re.compile(
    r"(?:registration|processing|training|security|refundable|onboarding|kit|verification|admission|enrol+ment|laptop|id\s*card)"
    r"\s*(?:fee|fees|deposit|charges?|amount)"
    r"|(?:pay|send|transfer|deposit)\s+(?:rs\.?|inr|₹)\s*[\d,]+"
    r"|(?:rs\.?|inr|₹)\s*[\d,]+\s*(?:as|for|towards)\s+(?:registration|processing|training|security|refundable|onboarding|verification)",
    re.I)
_SENSITIVE = re.compile(r"\b(?:aadhaar|aadhar|pan\s*(?:card|number)|bank\s*(?:account|details|statement)|otp|cvv|card\s*number|passport\s*copy|net\s*banking)\b", re.I)
_URGENCY = re.compile(r"(?:within|in)\s+(?:the\s+next\s+)?(?:12|24|48)\s*(?:hours?|hrs?)|last\s+date\s+(?:is\s+)?today|limited\s+(?:seats|slots|vacanc\w+|positions)|hurry|act\s+now|today\s+only|urgent(?:ly)?", re.I)
_OFFPLATFORM = re.compile(r"\b(?:whatsapp|telegram)\b", re.I)
_NO_INTERVIEW = re.compile(r"no\s+interview|without\s+(?:an?\s+)?interview|direct\s+(?:selection|joining)|guaranteed\s+(?:job|placement|selection|internship)|100\s*%\s*(?:placement|job|guarantee)|selected\s+without", re.I)
_PAY = re.compile(r"(?:stipend|salary|earn(?:ings?)?|income)\D{0,25}?(?:rs\.?|inr|₹)?\s*(\d[\d,]{3,8})", re.I)
_URL = re.compile(r"https?://[^\s<>\"')]+|www\.[^\s<>\"')]+", re.I)


def _snip(m: re.Match) -> str:
    return " ".join(m.group(0).split())[:80]


def find_urls(text: str) -> list[str]:
    seen, out = set(), []
    for u in _URL.findall(text or ""):
        u = u.rstrip(".,;:!?")
        if u.lower() not in seen:
            seen.add(u.lower())
            out.append(u)
    return out[:5]


def registered_domain(host: str) -> str:
    labels = host.lower().strip(".").split(".")
    if len(labels) <= 2:
        return ".".join(labels)
    if len(labels[-1]) == 2 and labels[-2] in {"co", "com", "org", "net", "ac", "gov", "edu", "nic"}:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def brands_claimed(text: str, company: str | None) -> set[str]:
    found = set()
    comp = re.sub(r"[^a-z]", "", (company or "").lower())
    for b, rx in _BRAND_RES.items():
        if (comp and b in comp) or rx.search(text or ""):
            found.add(b)
    return found


def _is_official(host: str, brand: str) -> bool:
    return any(host == d or host.endswith("." + d) for d in BRANDS[brand])


# ---------------------------------------------------------------- text
def text_signals(text: str) -> list[Signal]:
    out: list[Signal] = []
    t = text or ""
    if m := _FEE.search(t):
        out.append(Signal("fee", "Asks for money (fee / deposit) for an internship", 35, "payment", _snip(m)))
    if m := _NO_INTERVIEW.search(t):
        out.append(Signal("no_interview", "Promises selection with no interview or a guaranteed job", 18, "content", _snip(m)))
    if m := _SENSITIVE.search(t):
        out.append(Signal("sensitive", "Asks for sensitive documents or banking details up front", 15, "identity", _snip(m)))
    if m := _URGENCY.search(t):
        out.append(Signal("urgency", "Uses pressure or urgency to rush the decision", 12, "pressure", _snip(m)))
    if m := _OFFPLATFORM.search(t):
        out.append(Signal("offplatform", "Moves the conversation to WhatsApp / Telegram", 8, "pressure", _snip(m)))
    if "intern" in t.lower():
        for m in _PAY.finditer(t):
            amount = int(re.sub(r"[^\d]", "", m.group(1)) or 0)
            if amount >= 40000:
                out.append(Signal("pay", f"Stipend of about ₹{amount:,} is unusually high for an internship", 15, "content", _snip(m)))
                break
    return out


# ---------------------------------------------------------------- urls
def url_signals(url: str) -> list[Signal]:
    p = urlparse(url if "://" in url else "//" + url)
    host = (p.hostname or "").lower()
    if not host:
        return []
    scheme = p.scheme if "://" in url else ""
    out: list[Signal] = []
    try:
        ipaddress.ip_address(host)
        out.append(Signal("ip_host", "Link points to a raw IP address", 25, "domain", host))
    except ValueError:
        pass
    if registered_domain(host) in SHORTENERS:
        out.append(Signal("shortener", "Link is hidden behind a URL shortener", 12, "domain", host))
    if "xn--" in host:
        out.append(Signal("punycode", "Domain uses look-alike (punycode) characters", 15, "domain", host))
    if host.rsplit(".", 1)[-1] in RISKY_TLDS:
        out.append(Signal("risky_tld", f"Domain ends in .{host.rsplit('.', 1)[-1]}, common in throw-away scam sites", 8, "domain", host))
    if host.count("-") >= 3:
        out.append(Signal("hyphens", "Domain stuffed with hyphens (typical of fake portals)", 8, "domain", host))
    if scheme == "http":
        out.append(Signal("no_https", "Link does not use HTTPS", 8, "domain", url[:80]))
    tokens = re.split(r"[.\-_]", host)
    for b in BRANDS:
        if b in tokens and not _is_official(host, b):
            out.append(Signal("brand_domain", f"Domain imitates {b.upper()} but is not its official site ({BRANDS[b][0]})", 30, "identity", host))
            break
    return out


# ---------------------------------------------------------------- sender
def sender_signals(email: str, company: str | None, text: str) -> list[Signal]:
    if "@" not in (email or ""):
        return []
    domain = email.rsplit("@", 1)[-1].strip().lower()
    claimed = brands_claimed(text, company)
    if domain in FREE_MAIL:
        if claimed:
            b = sorted(claimed)[0]
            return [Signal("sender_brand", f"Claims to be {b.upper()} but writes from a free email ({domain})", 30, "identity", email)]
        return [Signal("sender_free", f"Official-looking offer sent from a free email address ({domain})", 12, "identity", email)]
    for b in claimed:
        if not _is_official(domain, b):
            return [Signal("sender_brand", f"Claims to be {b.upper()} but sender domain {domain} is not official", 30, "identity", email)]
    if company:
        words = [w for w in re.findall(r"[a-z0-9]+", company.lower()) if len(w) >= 4 and w not in GENERIC_COMPANY_WORDS]
        dom = domain.replace("-", "")
        if words and not any(w in dom for w in words):
            return [Signal("sender_mismatch", f"Sender domain {domain} does not resemble the company name", 12, "identity", email)]
    return []


# ---------------------------------------------------------------- network (best effort)
def is_public_host(host: str) -> tuple[bool, str | None]:
    """SSRF guard: only allow hosts whose every address is globally routable."""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False, None
    ips = [i[4][0] for i in infos]
    if not ips or not all(ipaddress.ip_address(ip).is_global for ip in ips):
        return False, None
    return True, ips[0]


def domain_age_days(domain: str) -> int | None:
    if not re.fullmatch(r"[a-z0-9.-]{3,253}", domain) or "." not in domain:
        return None
    try:
        r = httpx.get(f"https://rdap.org/domain/{domain}", timeout=4.0, follow_redirects=True,
                      headers={"accept": "application/rdap+json"})
        if r.status_code != 200:
            return None
        for ev in r.json().get("events", []):
            if ev.get("eventAction") == "registration":
                dt = datetime.fromisoformat(ev["eventDate"].replace("Z", "+00:00"))
                return max((datetime.now(timezone.utc) - dt).days, 0)
    except Exception:
        return None
    return None


def tls_status(host: str) -> str | None:
    ok, ip = is_public_host(host)
    if not ok:
        return None
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((ip, 443), timeout=4) as sock:
            with ctx.wrap_socket(sock, server_hostname=host):
                return "ok"
    except ssl.SSLCertVerificationError:
        return "invalid"
    except Exception:
        return None


def domain_signals(host: str) -> tuple[list[Signal], list[str]]:
    out: list[Signal] = []
    unavailable: list[str] = []
    reg = registered_domain(host)
    age = domain_age_days(reg)
    if age is None:
        unavailable.append(f"domain age of {reg} (RDAP)")
    elif age < 30:
        out.append(Signal("domain_new", f"Domain {reg} was registered only {age} days ago", 35, "domain", f"{age} days"))
    elif age < 90:
        out.append(Signal("domain_new", f"Domain {reg} is only {age} days old", 22, "domain", f"{age} days"))
    elif age < 365:
        out.append(Signal("domain_new", f"Domain {reg} is less than a year old ({age} days)", 8, "domain", f"{age} days"))
    tls = tls_status(host)
    if tls is None:
        unavailable.append(f"TLS certificate of {host}")
    elif tls == "invalid":
        out.append(Signal("tls_invalid", f"{host} presents an invalid TLS certificate", 20, "domain", host))
    return out, unavailable
