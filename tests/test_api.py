"""End-to-end tests of POST /leads with Notion replaced by an in-memory fake."""
import json
import os

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.notion import NOTION_API, NotionClient

SECRET = os.environ["WEBHOOK_SECRET"]
HOT_LEAD = {
    "full_name": "Mariana Gómez",
    "phone": "7221234567",
    "business_type": "restaurant",
    "property_type": "retail_unit",
    "operation": "lease",
    "budget_min_mxn": 25000,
    "budget_max_mxn": 40000,
    "timeframe": "1_3_months",
    "decision_role": "decision_maker",
    "conversation_id": "conv-123",
}


class FakeNotion:
    """Records requests and answers like the Notion API would."""

    def __init__(self, existing_page=None, fail=False):
        self.requests = []
        self.existing_page = existing_page
        self.fail = fail

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        self.requests.append((request.method, request.url.path, body))
        if self.fail:
            return httpx.Response(400, json={"message": "Score is not a property that exists."})
        if request.url.path.endswith("/query"):
            results = [{"id": self.existing_page}] if self.existing_page else []
            return httpx.Response(200, json={"results": results})
        return httpx.Response(200, json={"id": self.existing_page or "new-page-id"})


@pytest.fixture
def make_client():
    def _make(fake: FakeNotion) -> TestClient:
        client = TestClient(app)
        client.__enter__()  # runs the lifespan, then we swap in the fake transport
        app.state.notion = NotionClient(
            "key", "db-id", http=httpx.AsyncClient(base_url=NOTION_API, transport=httpx.MockTransport(fake))
        )
        return client
    return _make


def test_rejects_missing_or_wrong_secret(make_client):
    client = make_client(FakeNotion())
    assert client.post("/leads", json=HOT_LEAD).status_code == 401
    assert client.post("/leads", json=HOT_LEAD, headers={"X-Webhook-Secret": "nope"}).status_code == 401


def test_creates_hot_lead_with_status_new(make_client):
    fake = FakeNotion()
    client = make_client(fake)
    r = client.post("/leads", json=HOT_LEAD, headers={"X-Webhook-Secret": SECRET})

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "created" and data["score"] == "Hot"
    assert data["follow_up_message"].startswith("Un asesor se pondrá en contacto con usted")

    method, path, body = fake.requests[-1]
    props = body["properties"]
    assert (method, path) == ("POST", "/v1/pages")
    assert props["Status"]["select"]["name"] == "New"
    assert props["Business type"]["select"]["name"] == "Restaurant"
    assert props["Property type"]["select"]["name"] == "Retail unit"
    assert props["Timeframe"]["select"]["name"] == "1–3 months"
    assert props["Source"]["select"]["name"] == "Voice agent – web"
    assert props["Budget max (MXN)"]["number"] == 40000


def test_same_conversation_updates_without_resetting_status(make_client):
    fake = FakeNotion(existing_page="page-abc")
    client = make_client(fake)
    r = client.post("/leads", json=HOT_LEAD, headers={"X-Webhook-Secret": SECRET})

    assert r.json()["status"] == "updated"
    method, path, body = fake.requests[-1]
    assert (method, path) == ("PATCH", "/v1/pages/page-abc")
    assert "Status" not in body["properties"]


def test_invalid_payload_returns_readable_errors(make_client):
    client = make_client(FakeNotion())
    bad = {**HOT_LEAD, "property_type": "castle"}
    r = client.post("/leads", json=bad, headers={"X-Webhook-Secret": SECRET})
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_payload"
    assert any(d.startswith("property_type:") for d in r.json()["details"])


def test_notion_failure_returns_502(make_client):
    client = make_client(FakeNotion(fail=True))
    r = client.post("/leads", json=HOT_LEAD, headers={"X-Webhook-Secret": SECRET})
    assert r.status_code == 502
    assert "manual recovery" in r.json()["detail"]
