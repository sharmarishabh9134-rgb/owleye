from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import checks, scoring
from backend.app.main import app

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
client = TestClient(app)


def run(name, **kw):
    return scoring.analyze((SAMPLES / name).read_text(), live=False, **kw)


def ids(result):
    return {r["id"] for r in result["reasons"]}


def test_fake_offer_is_high_risk():
    r = run("fake_offer.txt", sender_email="tcs.careers.hr@gmail.com", company="TCS")
    assert r["level"] == "HIGH" and r["score"] >= 80
    assert {"fee", "sender_brand", "brand_domain", "urgency", "no_interview"} <= ids(r)
    assert r["report_draft"] and "1930" in r["report_draft"]


def test_genuine_offer_is_low_risk():
    r = run("genuine_offer.txt", sender_email="meera@acmerobotics.in", company="Acme Robotics Pvt Ltd")
    assert r["level"] == "LOW" and r["score"] <= 24
    assert r["report_draft"] is None


def test_fee_alone_is_at_least_medium():
    r = scoring.analyze("Pay a registration fee of Rs 500 to start.", live=False)
    assert r["level"] in {"MEDIUM", "HIGH"}


def test_brand_lookalike_domain():
    sig = {s.id for s in checks.url_signals("http://tcs-internship-registration.xyz/apply")}
    assert {"brand_domain", "no_https", "risky_tld"} <= sig
    assert not any(s.id == "brand_domain" for s in checks.url_signals("https://www.tcs.com/careers"))


def test_ssrf_guard_blocks_internal_hosts():
    for host in ("127.0.0.1", "localhost", "169.254.169.254", "10.0.0.5"):
        assert checks.is_public_host(host)[0] is False


def test_score_combination_is_bounded():
    assert scoring.combine([]) == 0
    assert 0 < scoring.combine([35, 30, 30, 20, 15]) <= 100


def test_api_roundtrip_and_validation(monkeypatch):
    monkeypatch.setenv("OWLEYE_OFFLINE", "1")
    ok = client.post("/api/analyze", json={"text": (SAMPLES / "fake_offer.txt").read_text()})
    assert ok.status_code == 200 and ok.json()["level"] == "HIGH"
    assert client.post("/api/analyze", json={}).status_code == 422
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/").status_code == 200
