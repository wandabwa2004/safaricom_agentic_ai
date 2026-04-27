"""Tests for graph execution end-to-end."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from graph.builder import build_graph, get_graph_mermaid
from graph import nodes
from tools.identity import IdentityVerificationService
from tools.line_status import LineStatusService
from tools.sim_validation import SimValidationService
from tools.sim_management import SimManagementService
from tools.mpesa import MpesaService
from tools.network_activation import NetworkActivationService
from tools.notifications import NotificationService


def _initial_state(subscriber_id: str = "S001", reason: str = "lost") -> dict:
    return {
        "subscriber_id": subscriber_id,
        "subscriber_name": "",
        "msisdn": "",
        "alternate_msisdn": "",
        "id_number": "",
        "request_id": "",
        "request_reason": reason,
        "request_timestamp": "",
        "channel": "shop",
        "id_verification_status": "pending",
        "id_verification_attempts": 0,
        "id_max_retries": config.MAX_IDENTITY_RETRIES,
        "kba_questions_correct": 0,
        "line_status": "",
        "fraud_flag": False,
        "pending_swap": False,
        "line_check_passed": False,
        "new_iccid": "",
        "new_imsi": "",
        "sim_validation_status": "pending",
        "sim_validation_attempts": 0,
        "sim_max_retries": config.MAX_SIM_SERIAL_RETRIES,
        "sim_validation_errors": [],
        "old_iccid": "",
        "old_imsi": "",
        "old_sim_blocked": False,
        "new_sim_provisioned": False,
        "mpesa_registered": False,
        "mpesa_balance": 0.0,
        "mpesa_reactivated": False,
        "mpesa_temporary_pin_sent": False,
        "network_activated": False,
        "confirmation_sms_sent": False,
        "current_step": "",
        "audit_log": [],
        "error_messages": [],
        "process_status": "in_progress",
        "messages": [],
    }


def _set_all_success():
    nodes.identity_service = IdentityVerificationService(success_rate=1.0)
    nodes.line_status_service = LineStatusService()
    nodes.sim_validation_service = SimValidationService(valid_rate=1.0)
    nodes.sim_mgmt_service = SimManagementService(block_rate=1.0, provision_rate=1.0)
    nodes.mpesa_service = MpesaService(success_rate=1.0)
    nodes.network_activation_service = NetworkActivationService(success_rate=1.0)
    nodes.notification_service = NotificationService(sms_rate=1.0)


@pytest.mark.asyncio
async def test_happy_path():
    """S001 — every step succeeds."""
    _set_all_success()
    graph = build_graph()
    result = await graph.ainvoke(_initial_state("S001", "lost"))

    assert result["process_status"] == "completed"
    assert result["id_verification_status"] == "passed"
    assert result["line_check_passed"] is True
    assert result["sim_validation_status"] == "valid"
    assert result["old_sim_blocked"] is True
    assert result["new_sim_provisioned"] is True
    assert result["mpesa_reactivated"] is True
    assert result["network_activated"] is True
    assert result["confirmation_sms_sent"] is True
    assert len(result["audit_log"]) >= 9


@pytest.mark.asyncio
async def test_identity_full_failure():
    """KBA fails all 3 attempts → rejected."""
    nodes.identity_service = IdentityVerificationService(success_rate=0.0)
    graph = build_graph()
    result = await graph.ainvoke(_initial_state("S001", "stolen"))

    assert result["process_status"] == "rejected"
    assert result["id_verification_attempts"] == config.MAX_IDENTITY_RETRIES
    assert result["id_verification_status"] == "failed"


@pytest.mark.asyncio
async def test_suspended_line_halt():
    """S003 suspended → halted at line check."""
    _set_all_success()
    graph = build_graph()
    result = await graph.ainvoke(_initial_state("S003", "lost"))

    assert result["process_status"] == "halted"
    assert result["line_status"] == "suspended"
    assert result["line_check_passed"] is False


@pytest.mark.asyncio
async def test_fraud_flag_halt():
    """S004 fraud flag → halted at line check."""
    _set_all_success()
    graph = build_graph()
    result = await graph.ainvoke(_initial_state("S004", "lost"))

    assert result["process_status"] == "halted"
    assert result["fraud_flag"] is True


@pytest.mark.asyncio
async def test_pending_swap_halt():
    """S005 already has pending swap → halted."""
    _set_all_success()
    graph = build_graph()
    result = await graph.ainvoke(_initial_state("S005", "lost"))

    assert result["process_status"] == "halted"
    assert result["pending_swap"] is True


@pytest.mark.asyncio
async def test_bad_sim_rejected():
    """New SIM always invalid → rejected after max retries."""
    nodes.identity_service = IdentityVerificationService(success_rate=1.0)
    nodes.line_status_service = LineStatusService()
    nodes.sim_validation_service = SimValidationService(valid_rate=0.0)
    graph = build_graph()
    result = await graph.ainvoke(_initial_state("S001", "damaged"))

    assert result["process_status"] == "rejected"
    assert result["sim_validation_attempts"] == config.MAX_SIM_SERIAL_RETRIES
    assert result["sim_validation_status"] == "invalid"


@pytest.mark.asyncio
async def test_mpesa_retry_still_completes():
    """M-PESA reactivation fails but network activation + swap still completes."""
    nodes.identity_service = IdentityVerificationService(success_rate=1.0)
    nodes.line_status_service = LineStatusService()
    nodes.sim_validation_service = SimValidationService(valid_rate=1.0)
    nodes.sim_mgmt_service = SimManagementService(block_rate=1.0, provision_rate=1.0)
    nodes.mpesa_service = MpesaService(success_rate=0.0)
    nodes.network_activation_service = NetworkActivationService(success_rate=1.0)
    nodes.notification_service = NotificationService(sms_rate=1.0)

    graph = build_graph()
    result = await graph.ainvoke(_initial_state("S002", "lost"))

    assert result["process_status"] == "completed"
    assert result["mpesa_reactivated"] is False
    assert result["network_activated"] is True
    assert result["confirmation_sms_sent"] is True


def test_graph_mermaid():
    mermaid = get_graph_mermaid()
    assert "initiate_request" in mermaid
    assert "verify_identity" in mermaid
    assert "block_old_sim" in mermaid
    assert "send_confirmation_sms" in mermaid
    assert "reject_request" in mermaid
