"""Tests for the FastAPI endpoint."""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph import nodes
from tools.identity import IdentityVerificationService
from tools.line_status import LineStatusService
from tools.sim_validation import SimValidationService
from tools.sim_management import SimManagementService
from tools.mpesa import MpesaService
from tools.network_activation import NetworkActivationService
from tools.notifications import NotificationService


@pytest.fixture(autouse=True)
def _set_all_success():
    nodes.identity_service = IdentityVerificationService(success_rate=1.0)
    nodes.line_status_service = LineStatusService()
    nodes.sim_validation_service = SimValidationService(valid_rate=1.0)
    nodes.sim_mgmt_service = SimManagementService(block_rate=1.0, provision_rate=1.0)
    nodes.mpesa_service = MpesaService(success_rate=1.0)
    nodes.network_activation_service = NetworkActivationService(success_rate=1.0)
    nodes.notification_service = NotificationService(sms_rate=1.0)


@pytest.fixture
def client():
    from main import app
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_list_models(client):
    r = client.get("/v1/models")
    assert r.status_code == 200
    data = r.json()
    assert data["object"] == "list"
    assert len(data["data"]) == 1
    assert data["data"][0]["id"] == "safaricom-sim-swap-agent"


def test_chat_prompts_for_msisdn_when_missing(client):
    r = client.post("/v1/chat/completions", json={
        "messages": [{"role": "user", "content": "Hi"}]
    })
    assert r.status_code == 200
    content = r.json()["choices"][0]["message"]["content"]
    assert "MSISDN" in content or "Safaricom" in content


def test_chat_happy_path(client):
    r = client.post("/v1/chat/completions", json={
        "messages": [
            {"role": "user", "content": "Lost my SIM. Number is +254712345678."}
        ]
    })
    assert r.status_code == 200
    content = r.json()["choices"][0]["message"]["content"]
    # Summary table markers only appear on the completed flow
    assert "SIM Swap Summary" in content


def test_graph_mermaid_endpoint(client):
    r = client.get("/graph/mermaid")
    assert r.status_code == 200
    assert "initiate_request" in r.json()["mermaid"]
