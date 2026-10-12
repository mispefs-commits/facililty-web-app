import os, tempfile
tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/chat.db"
os.environ["UPLOAD_DIR"] = f"{tmp}/uploads"
os.environ["SEED_DEMO"] = "true"
os.environ["DEMO_PASSWORD"] = "TestPass@123"
os.environ["OPENAI_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient
from app.main import app

PW = "TestPass@123"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def login(c, email):
    r = c.post("/api/auth/login", json={"email": email, "password": PW})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def say(c, h, tid, text=None, choice=None):
    r = c.post(f"/api/chat/threads/{tid}/messages", headers=h, json={"text": text or "", "choice": choice})
    assert r.status_code == 200, r.text
    return r.json()["messages"][-1]


def test_full_chatbot_ticket_flow(client):
    c = client
    h = login(c, "client@example.com")
    th = c.post("/api/chat/threads", headers=h).json()
    tid = th["id"]
    first = c.get(f"/api/chat/threads/{tid}/messages", headers=h).json()["messages"][0]
    assert "Report an issue" in first["options"]

    m = say(c, h, tid, "ac not coling properly in 3rd floor meeting room")  # typo on purpose
    assert m["text"].startswith("Which site") and "Hitech City Campus" in m["options"]
    m = say(c, h, tid, choice="Hitech City Campus")
    assert m["text"] == "Which floor?"
    m = say(c, h, tid, choice=m["options"][-1])
    assert "room or area" in m["text"]
    m = say(c, h, tid, "Meeting room 3B")
    assert "client" in m["text"].lower()
    m = say(c, h, tid, "Acme Corp")
    assert "representative" in m["text"].lower()
    m = say(c, h, tid, "Anita Rao")
    m = say(c, h, tid, "12345")                       # invalid phone is rejected
    assert "valid phone" in m["text"]
    m = say(c, h, tid, "9876543210")
    m = say(c, h, tid, choice="Same as phone number")
    assert "pictures" in m["text"]
    r = c.post(f"/api/chat/threads/{tid}/upload", headers=h, files={"file": ("leak.jpg", b"\xff\xd8x", "image/jpeg")})
    assert r.status_code == 201
    m = say(c, h, tid, choice="Done")
    assert m["text"].startswith("Please confirm") and "Photos attached: 1" in m["text"]
    m = say(c, h, tid, choice="✅ Confirm & create ticket")
    assert m["meta"]["number"].startswith("TKT-") and m["meta"]["whatsapp"] == "+919876543210"
    assert "+919876543210" in m["text"]

    tk = c.get(f"/api/tickets/{m['meta']['ticket_id']}", headers=h).json()
    assert tk["source"] == "Chatbot" and tk["rep_name"] == "Anita Rao" and tk["client_name"] == "Acme Corp"
    assert tk["category"]["name"].startswith("HVAC")
    assert [a["kind"] for a in tk["attachments"]] == ["before"]

    # status question through the bot
    m = say(c, h, tid, "status " + tk["number"])
    assert tk["number"] in m["text"] and "Status: New" in m["text"]


def test_emergency_is_critical_and_agent_handoff(client):
    c = client
    h = login(c, "client@example.com")
    tid = c.post("/api/chat/threads", headers=h).json()["id"]
    r = c.post(f"/api/chat/threads/{tid}/messages", headers=h, json={"text": "there is smoke and sparks from the panel"})
    assert any("safety-critical" in m["text"] for m in r.json()["messages"])

    # hand off to a live agent
    assert c.post(f"/api/chat/threads/{tid}/handoff", headers=h).json()["mode"] == "agent"
    fm = login(c, "fm@example.com")
    inbox = c.get("/api/chat/threads", headers=fm).json()
    assert any(t["id"] == tid and t["unread"] > 0 for t in inbox)
    assert c.get("/api/chat/unread", headers=fm).json()["unread"] > 0
    r = c.post(f"/api/chat/threads/{tid}/messages", headers=fm, json={"text": "Hello, security is on the way"})
    assert r.status_code == 200
    msgs = c.get(f"/api/chat/threads/{tid}/messages", headers=h).json()["messages"]
    assert msgs[-1]["sender_type"] == "agent" and "security" in msgs[-1]["text"]
    # a technician or other client cannot read this chat
    assert c.get(f"/api/chat/threads/{tid}/messages", headers=login(c, "tech@example.com")).status_code in (403, 404)
    # client can go back to the bot, agent can close
    assert c.post(f"/api/chat/threads/{tid}/bot", headers=h).json()["mode"] == "bot"
    assert c.post(f"/api/chat/threads/{tid}/close", headers=h).status_code == 403
    assert c.post(f"/api/chat/threads/{tid}/close", headers=fm).json()["mode"] == "closed"
