import os, tempfile
tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/test.db"
os.environ["UPLOAD_DIR"] = f"{tmp}/uploads"
os.environ["SEED_DEMO"] = "true"
os.environ["DEMO_PASSWORD"] = "TestPass@123"

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
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_full_lifecycle(client):
    c = client
    client_h, fm_h, tech_h = login(c, "client@example.com"), login(c, "fm@example.com"), login(c, "tech@example.com")
    site = c.get("/api/sites", headers=client_h).json()
    assert len(site) == 1  # client only sees authorised site
    sid = site[0]["id"]
    struct = c.get(f"/api/sites/{sid}/structure", headers=client_h).json()[0]
    cat = c.get("/api/categories", headers=client_h).json()[0]
    r = c.post("/api/tickets", headers=client_h, json={
        "site_id": sid, "building_id": struct["id"], "tower_id": struct["towers"][0]["id"],
        "floor_id": struct["floors"][0]["id"], "location": "3rd floor meeting room",
        "category_id": cat["id"], "subject": "AC not cooling", "description": "AC is not cooling in the meeting room",
        "client_name": "Acme Corp", "rep_name": "Anita", "rep_phone": "9876543210", "rep_whatsapp": "98765 43210"})
    assert r.status_code == 201, r.text
    t = r.json(); tid = t["id"]
    assert t["number"].startswith("TKT-") and t["status"] == "New"
    assert t["rep_whatsapp"] == "+919876543210" and t["wa_link"] == "https://wa.me/919876543210"

    # Photo upload by client
    r = c.post(f"/api/tickets/{tid}/attachments", headers=client_h, files={"file": ("a.jpg", b"\xff\xd8fake", "image/jpeg")}, data={"kind": "before"})
    assert r.status_code == 201
    # Bad file type rejected
    r = c.post(f"/api/tickets/{tid}/attachments", headers=client_h, files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 415

    # Technician cannot see it until assigned
    assert c.get("/api/tickets", headers=tech_h).json()["total"] == 0
    assert c.get(f"/api/tickets/{tid}", headers=tech_h).status_code == 404

    # FM assigns
    techs = c.get("/api/users?role=technician", headers=fm_h).json()
    r = c.post(f"/api/tickets/{tid}/assign", headers=fm_h, json={"assignee_id": techs[0]["id"]})
    assert r.status_code == 200 and r.json()["status"] == "Assigned"

    # Client cannot assign or change status
    assert c.post(f"/api/tickets/{tid}/assign", headers=client_h, json={"assignee_id": techs[0]["id"]}).status_code == 403
    assert c.post(f"/api/tickets/{tid}/status", headers=client_h, json={"status": "In Progress"}).status_code == 403

    # Technician works the ticket
    assert c.post(f"/api/tickets/{tid}/status", headers=tech_h, json={"status": "In Progress"}).status_code == 200
    assert c.post(f"/api/tickets/{tid}/status", headers=tech_h, json={"status": "Resolved"}).status_code == 422  # needs corrective action
    # cannot resolve without during + after photos
    r = c.post(f"/api/tickets/{tid}/status", headers=tech_h, json={"status": "Resolved", "corrective_action": "Refilled gas"})
    assert r.status_code == 422 and "photo" in r.json()["detail"]
    # client cannot upload during/after photos
    assert c.post(f"/api/tickets/{tid}/attachments", headers=client_h, files={"file": ("x.jpg", b"\xff\xd8x", "image/jpeg")}, data={"kind": "after"}).status_code == 403
    # photo stages must be images
    assert c.post(f"/api/tickets/{tid}/attachments", headers=tech_h, files={"file": ("x.pdf", b"%PDF", "application/pdf")}, data={"kind": "during"}).status_code == 415
    for kind in ("during", "after"):
        assert c.post(f"/api/tickets/{tid}/attachments", headers=tech_h, files={"file": (f"{kind}.jpg", b"\xff\xd8x", "image/jpeg")}, data={"kind": kind}).status_code == 201
    r = c.post(f"/api/tickets/{tid}/status", headers=tech_h, json={"status": "Resolved", "root_cause": "Gas leak", "corrective_action": "Refilled gas"})
    assert r.status_code == 200 and r.json()["status"] == "Resolved"

    # Internal note hidden from client
    c.post(f"/api/tickets/{tid}/comments", headers=tech_h, json={"body": "internal only", "internal": True})
    c.post(f"/api/tickets/{tid}/comments", headers=client_h, json={"body": "thanks"})
    assert all(not x["internal"] for x in c.get(f"/api/tickets/{tid}", headers=client_h).json()["comments"])

    # Client confirms closure + feedback
    assert c.post(f"/api/tickets/{tid}/status", headers=client_h, json={"status": "Closed"}).status_code == 200
    assert c.post(f"/api/tickets/{tid}/feedback", headers=client_h, json={"rating": 5, "comment": "great"}).status_code == 201
    assert c.post(f"/api/tickets/{tid}/feedback", headers=client_h, json={"rating": 4}).status_code == 409

    d = c.get(f"/api/tickets/{tid}", headers=fm_h).json()
    assert d["status"] == "Closed" and d["feedback"]["rating"] == 5
    assert len(d["history"]) >= 6 and sorted(a["kind"] for a in d["attachments"]) == ["after", "before", "during"]
    assert c.get("/api/dashboard/summary", headers=fm_h).json()["total"] >= 1


def test_auth_and_isolation(client):
    c = client
    assert c.get("/api/tickets").status_code == 401
    assert c.post("/api/auth/login", json={"email": "client@example.com", "password": "wrong"}).status_code == 401
    # client cannot manage users or sites
    h = login(c, "client@example.com")
    assert c.get("/api/users", headers=h).status_code == 403
    assert c.post("/api/sites", headers=h, json={"region": "X", "name": "Y", "code": "ZZ"}).status_code == 403
    # client cannot raise ticket at unauthorised site
    admin = login(c, "admin@example.com")
    sites = c.get("/api/sites", headers=admin).json()
    other = [s for s in sites if s["code"] != "HYD-HC"][0]
    st = c.get(f"/api/sites/{other['id']}/structure", headers=admin).json()[0]
    r = c.post("/api/tickets", headers=h, json={"site_id": other["id"], "building_id": st["id"], "location": "lobby",
               "category_id": 1, "subject": "Test", "description": "Some issue here",
               "rep_name": "A", "rep_phone": "9876543210", "rep_whatsapp": "9876543210"})
    assert r.status_code == 403
    assert c.get(f"/api/sites/{other['id']}/structure", headers=h).status_code == 403
    # admin can add a new site without code changes
    r = c.post("/api/sites", headers=admin, json={"region": "Chennai", "name": "OMR Park", "code": "CHN-OMR"})
    assert r.status_code == 201
