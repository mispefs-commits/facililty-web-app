"""Load test for the 500+ concurrent user target.
  pip install locust
  locust -f loadtest.py --host http://localhost:8000 -u 500 -r 25 --headless -t 5m
Needs the demo users (SEED_DEMO=true) or edit the credentials below."""
import os, random
from locust import HttpUser, between, task

PW = os.getenv("DEMO_PASSWORD", "ChangeMe@123")


class Staff(HttpUser):
    wait_time = between(1, 4)

    def on_start(self):
        email = random.choice(["fm@example.com", "client@example.com", "tech@example.com", "manager@example.com"])
        r = self.client.post("/api/auth/login", json={"email": email, "password": PW})
        self.h = {"Authorization": f"Bearer {r.json().get('access_token', '')}"}

    @task(5)
    def tickets(self): self.client.get("/api/tickets?page=1", headers=self.h, name="/api/tickets")
    @task(3)
    def dash(self): self.client.get("/api/dashboard/summary", headers=self.h)
    @task(1)
    def sites(self): self.client.get("/api/sites", headers=self.h)
