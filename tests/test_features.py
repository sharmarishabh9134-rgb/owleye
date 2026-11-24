import pytest
from fastapi.testclient import TestClient

from backend.app import assistant, scoring
from backend.app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def no_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OWLEYE_OFFLINE", "1")


def chat(text, **extra):
    return client.post("/api/chat", json={"messages": [{"role": "user", "content": text}], **extra})


def test_platforms_endpoint_lists_official_portals():
    d = client.get("/api/platforms").json()
    urls = {p["url"] for p in d["platforms"]}
    assert "https://pminternship.mca.gov.in" in urls and "https://internship.aicte-india.org" in urls
    assert all(u.startswith("https://") for u in urls)
    assert d["tips"]


def test_chat_rules_mode_handles_already_paid():
    r = chat("I already paid 2000 rupees as registration fee")
    assert r.status_code == 200
    d = r.json()
    assert d["mode"] == "rules" and "1930" in d["reply"] and "cybercrime.gov.in" in d["reply"]


def test_chat_fee_question_says_do_not_pay():
    assert "Do not pay" in chat("should I pay the registration fee?").json()["reply"]


def test_chat_uses_llm_when_available(monkeypatch):
    monkeypatch.setattr(assistant, "_llm", lambda msgs, ctx: "LLM says hi")
    d = chat("hello there").json()
    assert d == {"reply": "LLM says hi", "mode": "llm"}


def test_chat_falls_back_when_llm_fails(monkeypatch):
    monkeypatch.setattr(assistant, "_llm", lambda msgs, ctx: None)
    assert chat("how do I report this").json()["mode"] == "rules"


def test_chat_validation():
    assert client.post("/api/chat", json={"messages": [{"role": "system", "content": "x"}]}).status_code == 422
    assert client.post("/api/chat", json={"messages": []}).status_code == 422
    assert client.post("/api/chat", json={"messages": [{"role": "assistant", "content": "hi"}]}).status_code == 422
    too_long = {"role": "user", "content": "a" * 1001}
    assert client.post("/api/chat", json={"messages": [too_long]}).status_code == 422


def test_chat_context_is_accepted():
    ctx = {"score": 88, "level": "HIGH", "reasons": ["Asks for money"]}
    assert chat("what should I do?", context=ctx).status_code == 200
    assert chat("x", context={"score": 500, "level": "HIGH", "reasons": []}).status_code == 422


def test_llm_prompt_includes_scan_summary_only(monkeypatch):
    seen = {}

    class R:
        status_code = 200
        def json(self): return {"content": [{"type": "text", "text": "ok"}]}

    def fake_post(url, headers, json, timeout):
        seen["system"] = json["system"]; seen["first"] = json["messages"][0]["role"]
        return R()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(assistant.httpx, "post", fake_post)
    out = assistant.reply([{"role": "assistant", "content": "hi"}, {"role": "user", "content": "help"}],
                          {"score": 70, "level": "HIGH", "reasons": ["Asks for money"]})
    assert out == {"reply": "ok", "mode": "llm"}
    assert "70/100" in seen["system"] and "Asks for money" in seen["system"] and seen["first"] == "user"


def test_rate_limiter():
    ip = "9.9.9.9"
    assert all(assistant.allow(ip, limit=3, window=60) for _ in range(3))
    assert assistant.allow(ip, limit=3, window=60) is False


def test_complaint_with_money_lost_is_urgent():
    body = {"what_happened": "I paid a registration fee to a fake TCS recruiter.", "amount_lost": "2000",
            "transaction_id": "UTR123456", "scammer_contact": "tcs.hr@gmail.com", "scan_reasons": ["Asks for money"]}
    d = client.post("/api/complaint", json=body).json()
    assert d["urgent"] is True and d["portal_url"] == "https://cybercrime.gov.in" and d["helpline"] == "1930"
    assert "UTR123456" in d["complaint"] and "tcs.hr@gmail.com" in d["complaint"] and "Asks for money" in d["complaint"]
    assert "1930" in d["steps"][0]


def test_complaint_without_loss_not_urgent_and_validates():
    d = client.post("/api/complaint", json={"what_happened": "They asked me to send my Aadhaar on WhatsApp."}).json()
    assert d["urgent"] is False and "No money lost so far" in d["complaint"]
    assert client.post("/api/complaint", json={"what_happened": "short"}).status_code == 422
    assert client.post("/api/complaint", json={}).status_code == 422


def test_complaint_report_email_from_env(monkeypatch):
    monkeypatch.setenv("OWLEYE_REPORT_EMAIL", "cell@college.edu")
    d = client.post("/api/complaint", json={"what_happened": "Fake offer asked for a fee."}).json()
    assert d["report_email"] == "cell@college.edu"


def test_safe_alternatives_only_for_risky_offers():
    risky = scoring.analyze("Pay a registration fee of Rs 500 now", live=False)
    assert risky["safe_alternatives"] and risky["safe_alternatives"][0]["url"].startswith("https://")
    assert scoring.analyze("Hello, thanks for interviewing with us.", live=False)["safe_alternatives"] == []
