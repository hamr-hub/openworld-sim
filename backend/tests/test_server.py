"""FastAPI HTTP API smoke tests."""

import pytest
from fastapi.testclient import TestClient

from openworld.server import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_root_returns_service_info(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "openworld-sim"
    assert "version" in body


def test_snapshot_returns_initial_world(client):
    r = client.get("/snapshot")
    assert r.status_code == 200
    body = r.json()
    assert "width" in body and "height" in body
    assert "agents" in body
    assert isinstance(body["agents"], list)


def test_events_returns_log(client):
    r = client.get("/events", params={"limit": 10})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_stats_returns_counts(client):
    r = client.get("/stats")
    assert r.status_code == 200
    body = r.json()
    assert "tick" in body
    assert "event_count" in body
    assert "kinds" in body
    assert "agent_count" in body
    assert "task_count" in body