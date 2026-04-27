"""Tests for individual tool services."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from tools.identity import IdentityVerificationService
from tools.line_status import LineStatusService
from tools.sim_validation import SimValidationService, generate_valid_sim_pair
from tools.sim_management import SimManagementService
from tools.mpesa import MpesaService
from tools.network_activation import NetworkActivationService
from tools.notifications import NotificationService


@pytest.mark.asyncio
async def test_identity_always_passes():
    svc = IdentityVerificationService(success_rate=1.0)
    result = await svc.verify("S001")
    assert result["status"] == "verified"
    assert result["questions_correct"] == config.KBA_QUESTIONS_TOTAL


@pytest.mark.asyncio
async def test_identity_always_fails():
    svc = IdentityVerificationService(success_rate=0.0)
    result = await svc.verify("S001")
    assert result["status"] == "failed"
    assert result["questions_correct"] == 0


@pytest.mark.asyncio
async def test_line_status_active():
    svc = LineStatusService()
    result = await svc.check("S001")
    assert result["found"] is True
    assert result["status"] == "active"
    assert result["fraud_flag"] is False


@pytest.mark.asyncio
async def test_line_status_suspended():
    svc = LineStatusService()
    result = await svc.check("S003")
    assert result["status"] == "suspended"


@pytest.mark.asyncio
async def test_line_status_fraud_flag():
    svc = LineStatusService()
    result = await svc.check("S004")
    assert result["fraud_flag"] is True


@pytest.mark.asyncio
async def test_line_status_not_found():
    svc = LineStatusService()
    result = await svc.check("S999")
    assert result["found"] is False


@pytest.mark.asyncio
async def test_sim_validation_valid_pair():
    svc = SimValidationService(valid_rate=1.0)
    iccid, imsi = generate_valid_sim_pair()
    result = await svc.validate(iccid, imsi)
    assert result["status"] == "valid"


@pytest.mark.asyncio
async def test_sim_validation_bad_iccid_prefix():
    svc = SimValidationService(valid_rate=1.0)
    bad_iccid = "99999" + "0" * (config.ICCID_LENGTH - 5)
    _, imsi = generate_valid_sim_pair()
    result = await svc.validate(bad_iccid, imsi)
    assert result["status"] == "invalid"
    assert result["reason"] == "structural"


@pytest.mark.asyncio
async def test_sim_validation_bad_imsi_length():
    svc = SimValidationService(valid_rate=1.0)
    iccid, _ = generate_valid_sim_pair()
    result = await svc.validate(iccid, "123")
    assert result["status"] == "invalid"


@pytest.mark.asyncio
async def test_sim_management_block_and_provision():
    svc = SimManagementService(block_rate=1.0, provision_rate=1.0)
    iccid, imsi = generate_valid_sim_pair()
    block = await svc.block_old(iccid, imsi)
    assert block["status"] == "blocked"

    new_iccid, new_imsi = generate_valid_sim_pair()
    prov = await svc.provision_new("+254712345678", new_iccid, new_imsi)
    assert prov["status"] == "provisioned"
    assert prov["imsi_bound"] is True


@pytest.mark.asyncio
async def test_mpesa_reactivate_registered():
    svc = MpesaService(success_rate=1.0)
    result = await svc.reactivate("S001", "639021234567890")
    assert result["status"] == "reactivated"
    assert result["balance_restored_kes"] == 15420.50


@pytest.mark.asyncio
async def test_mpesa_reactivate_unknown_subscriber():
    svc = MpesaService(success_rate=1.0)
    result = await svc.reactivate("S999", "639029999999999")
    # Unknown subscribers are not mpesa_registered in seed data
    assert result["status"] == "not_applicable"


@pytest.mark.asyncio
async def test_network_activation_success():
    svc = NetworkActivationService(success_rate=1.0)
    result = await svc.activate("+254712345678", "639021234567890")
    assert result["status"] == "active"
    assert "voice" in result["services_enabled"]


@pytest.mark.asyncio
async def test_notifications_sms_delivered():
    svc = NotificationService(sms_rate=1.0)
    result = await svc.send_sms("+254711000001", "test")
    assert result["status"] == "delivered"
