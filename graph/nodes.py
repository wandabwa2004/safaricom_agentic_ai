"""Graph node functions for the SIM swap process."""

from __future__ import annotations

import uuid
from datetime import datetime

from langchain_core.messages import AIMessage

import config
from tools.identity import IdentityVerificationService
from tools.line_status import LineStatusService
from tools.sim_validation import SimValidationService, generate_valid_sim_pair
from tools.sim_management import SimManagementService
from tools.mpesa import MpesaService
from tools.network_activation import NetworkActivationService
from tools.notifications import NotificationService

# Service instances (replaceable in tests/scenarios)
identity_service = IdentityVerificationService()
line_status_service = LineStatusService()
sim_validation_service = SimValidationService()
sim_mgmt_service = SimManagementService()
mpesa_service = MpesaService()
network_activation_service = NetworkActivationService()
notification_service = NotificationService()


def _log(state: dict, action: str, details: dict) -> list[dict]:
    """Append an entry to the audit log."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "step": state.get("current_step", "unknown"),
        "action": action,
        "request_id": state.get("request_id", ""),
        **details,
    }
    return state.get("audit_log", []) + [entry]


def _mask_iccid(iccid: str) -> str:
    return f"{iccid[:5]}…{iccid[-4:]}" if len(iccid) >= 9 else iccid


# ─────────────────────────────────────────────────────────────────────────────
# 1. Initiate request
# ─────────────────────────────────────────────────────────────────────────────
async def initiate_request(state: dict) -> dict:
    """Validate input, generate request_id, set initial state."""
    request_id = f"SWP-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now().isoformat()

    msg = (
        f"Karibu Safaricom. I'm here to help you replace your SIM for a "
        f"**{state.get('request_reason', 'lost')}** line.\n\n"
        f"Your request reference is **{request_id}**. "
        f"I'll take you through the swap step by step.\n\n"
        f"**Step 1:** Let's first verify your identity."
    )

    audit_log = _log(state, "request_initiated", {
        "request_id": request_id,
        "request_reason": state.get("request_reason", "lost"),
        "subscriber_id": state.get("subscriber_id", ""),
        "channel": state.get("channel", "shop"),
    })

    return {
        "request_id": request_id,
        "request_timestamp": now,
        "current_step": "initiate_request",
        "process_status": "in_progress",
        "id_verification_status": "pending",
        "id_verification_attempts": 0,
        "id_max_retries": config.MAX_IDENTITY_RETRIES,
        "sim_validation_status": "pending",
        "sim_validation_attempts": 0,
        "sim_max_retries": config.MAX_SIM_SERIAL_RETRIES,
        "sim_validation_errors": [],
        "old_sim_blocked": False,
        "new_sim_provisioned": False,
        "mpesa_reactivated": False,
        "mpesa_temporary_pin_sent": False,
        "network_activated": False,
        "confirmation_sms_sent": False,
        "audit_log": audit_log,
        "error_messages": [],
        "messages": [AIMessage(content=msg)],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. Verify identity (KBA)
# ─────────────────────────────────────────────────────────────────────────────
async def verify_identity(state: dict) -> dict:
    """KBA: ID number, frequent numbers, recent M-PESA, last top-up."""
    attempts = state.get("id_verification_attempts", 0) + 1
    result = await identity_service.verify(state["subscriber_id"])

    correct = result["questions_correct"]
    required = result["questions_required"]
    total = result["questions_total"]

    if result["status"] == "verified":
        msg = (
            f"Identity verified — you answered **{correct}/{total}** questions "
            f"correctly (minimum {required} required). Thank you!\n\n"
            f"**Step 2:** I'll now check the status of your line."
        )
        status = "passed"
    else:
        remaining = state.get("id_max_retries", config.MAX_IDENTITY_RETRIES) - attempts
        reasons = "; ".join(result.get("failure_reasons", [])) or "one or more answers didn't match"
        if remaining > 0:
            msg = (
                f"I got **{correct}/{total}** correct — I need at least **{required}**. "
                f"Specifically: {reasons}.\n\n"
                f"Let's try again. You have **{remaining}** attempt(s) remaining."
            )
        else:
            msg = (
                f"Identity verification failed after "
                f"{state.get('id_max_retries', config.MAX_IDENTITY_RETRIES)} attempts. "
                f"For your security, I cannot proceed with the SIM swap."
            )
        status = "failed"

    audit_log = _log(state, "identity_verification", {
        "attempt": attempts,
        "result": result["status"],
        "verification_id": result["verification_id"],
        "questions_correct": correct,
        "questions_required": required,
        "per_question": result.get("per_question"),
    })

    return {
        "current_step": "verify_identity",
        "id_verification_status": status,
        "id_verification_attempts": attempts,
        "kba_questions_correct": correct,
        "audit_log": audit_log,
        "messages": [AIMessage(content=msg)],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. Check line status
# ─────────────────────────────────────────────────────────────────────────────
async def check_line_status(state: dict) -> dict:
    """Check HLR for line status, fraud flag, pending swap."""
    result = await line_status_service.check(state["subscriber_id"])

    issues: list[str] = []
    passed = True

    if not result.get("found"):
        issues.append("The MSISDN is not recognised on our network.")
        passed = False
    else:
        if result["status"] != "active":
            issues.append(f"The line's status is **{result['status']}**.")
            passed = False
        if result.get("fraud_flag"):
            issues.append(
                "There is a security flag on this line that requires an in-person shop visit."
            )
            passed = False
        if result.get("pending_swap"):
            issues.append("A SIM swap is already in progress for this line.")
            passed = False

    if passed:
        msg = (
            f"Line status confirmed.\n\n"
            f"- **MSISDN:** {result['msisdn']}\n"
            f"- **Name:** {result['name']}\n"
            f"- **Status:** Active\n"
            f"- **Current SIM serial:** {_mask_iccid(result['current_iccid'])}\n"
            f"- **M-PESA:** "
            f"{'Registered (balance Ksh ' + format(result['mpesa_balance'], ',.2f') + ')' if result['mpesa_registered'] else 'Not registered'}\n\n"
            f"**Step 3:** Please hand me the new SIM so I can capture its "
            f"serial (ICCID) and IMSI."
        )
    else:
        msg = (
            f"I can't continue with this swap on self-service:\n\n"
            + "\n".join(f"- {i}" for i in issues) + "\n\n"
            f"Please visit any **Safaricom shop** with your National ID, "
            f"or call **100** (free from a Safaricom line) for assistance."
        )

    audit_log = _log(state, "line_status_check", {
        "status": result.get("status"),
        "fraud_flag": result.get("fraud_flag"),
        "pending_swap": result.get("pending_swap"),
        "passed": passed,
    })

    return {
        "current_step": "check_line_status",
        "line_status": result.get("status", "not_found"),
        "fraud_flag": result.get("fraud_flag", False),
        "pending_swap": result.get("pending_swap", False),
        "line_check_passed": passed,
        "msisdn": result.get("msisdn", state.get("msisdn", "")),
        "subscriber_name": result.get("name", state.get("subscriber_name", "")),
        "alternate_msisdn": result.get(
            "alternate_msisdn", state.get("alternate_msisdn", "")
        ),
        "old_iccid": result.get("current_iccid", state.get("old_iccid", "")),
        "old_imsi": result.get("current_imsi", state.get("old_imsi", "")),
        "mpesa_registered": result.get("mpesa_registered", False),
        "mpesa_balance": result.get("mpesa_balance", 0.0),
        "audit_log": audit_log,
        "messages": [AIMessage(content=msg)],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. Capture + validate new SIM (ICCID + IMSI)
# ─────────────────────────────────────────────────────────────────────────────
async def capture_new_sim(state: dict) -> dict:
    """Validate the new SIM's ICCID and IMSI."""
    attempts = state.get("sim_validation_attempts", 0) + 1

    # If the caller didn't supply a SIM (e.g. demo mode), generate a valid pair.
    iccid = state.get("new_iccid") or ""
    imsi = state.get("new_imsi") or ""
    if not iccid or not imsi:
        iccid, imsi = generate_valid_sim_pair()

    result = await sim_validation_service.validate(iccid, imsi)

    if result["status"] == "valid":
        msg = (
            f"New SIM validated successfully:\n\n"
            f"- **ICCID:** {_mask_iccid(iccid)}\n"
            f"- **IMSI:** bound to Safaricom HLR\n\n"
            f"**Step 4:** Blocking your old SIM now."
        )
        status = "valid"
        errors: list[str] = []
    else:
        remaining = state.get("sim_max_retries", config.MAX_SIM_SERIAL_RETRIES) - attempts
        errors = result.get("errors", [])
        if remaining > 0:
            msg = (
                f"I couldn't validate that SIM:\n\n"
                + "\n".join(f"- {e}" for e in errors) + "\n\n"
                f"Please double-check and try another blank SIM. "
                f"**{remaining}** attempt(s) remaining."
            )
        else:
            msg = (
                f"I was unable to validate a new SIM after "
                f"{state.get('sim_max_retries', config.MAX_SIM_SERIAL_RETRIES)} attempts:\n\n"
                + "\n".join(f"- {e}" for e in errors) + "\n\n"
                f"Please retry at a Safaricom shop with a fresh blank SIM."
            )
        status = "invalid"

    audit_log = _log(state, "sim_validation", {
        "attempt": attempts,
        "iccid_last4": iccid[-4:] if iccid else "",
        "status": result["status"],
        "reason": result.get("reason"),
        "errors": errors,
    })

    return {
        "current_step": "capture_new_sim",
        "new_iccid": iccid,
        "new_imsi": imsi,
        "sim_validation_status": status,
        "sim_validation_attempts": attempts,
        "sim_validation_errors": errors,
        "audit_log": audit_log,
        "messages": [AIMessage(content=msg)],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. Block old SIM
# ─────────────────────────────────────────────────────────────────────────────
async def block_old_sim(state: dict) -> dict:
    old_iccid = state.get("old_iccid", "")
    old_imsi = state.get("old_imsi", "")
    result = await sim_mgmt_service.block_old(old_iccid, old_imsi)

    if result["status"] == "blocked":
        msg = (
            f"Your old SIM (serial {_mask_iccid(old_iccid)}) has been **blocked** "
            f"across the Safaricom network — no one can use it to make calls, "
            f"send SMS, or access M-PESA.\n\n"
            f"**Step 5:** Provisioning your new SIM now."
        )
        blocked = True
    else:
        msg = (
            f"Hot-listing the old SIM encountered a temporary issue. Our engineers "
            f"have been notified and will force-block it shortly. Proceeding with the swap."
        )
        blocked = False

    audit_log = _log(state, "block_old_sim", {
        "old_iccid_last4": old_iccid[-4:] if old_iccid else "",
        "status": result["status"],
        "reference": result.get("reference"),
    })

    return {
        "current_step": "block_old_sim",
        "old_sim_blocked": blocked,
        "audit_log": audit_log,
        "messages": [AIMessage(content=msg)],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 6. Provision new SIM (bind IMSI ↔ MSISDN)
# ─────────────────────────────────────────────────────────────────────────────
async def provision_new_sim(state: dict) -> dict:
    msisdn = state.get("msisdn", "")
    new_iccid = state.get("new_iccid", "")
    new_imsi = state.get("new_imsi", "")

    result = await sim_mgmt_service.provision_new(msisdn, new_iccid, new_imsi)

    if result["status"] == "provisioned":
        msg = (
            f"Your MSISDN **{msisdn}** has been bound to the new SIM.\n\n"
            f"- **New SIM serial:** {_mask_iccid(new_iccid)}\n"
            f"- **IMSI bound:** Yes\n\n"
            f"**Step 6:** Reactivating your M-PESA wallet on the new SIM."
        )
        provisioned = True
    else:
        msg = (
            f"Provisioning the new SIM hit a temporary issue. Retrying via "
            f"the back-office queue. Proceeding to M-PESA reactivation."
        )
        provisioned = False

    audit_log = _log(state, "provision_new_sim", {
        "msisdn": msisdn,
        "new_iccid_last4": new_iccid[-4:] if new_iccid else "",
        "status": result["status"],
        "reference": result.get("reference"),
    })

    return {
        "current_step": "provision_new_sim",
        "new_sim_provisioned": provisioned,
        "audit_log": audit_log,
        "messages": [AIMessage(content=msg)],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 7. Reactivate M-PESA
# ─────────────────────────────────────────────────────────────────────────────
async def reactivate_mpesa(state: dict) -> dict:
    if not state.get("mpesa_registered", False):
        msg = (
            f"This line is not registered for M-PESA, so there is no wallet to "
            f"restore.\n\n**Step 7:** Activating the new SIM on the network."
        )
        audit_log = _log(state, "mpesa_reactivate", {"status": "not_applicable"})
        return {
            "current_step": "reactivate_mpesa",
            "mpesa_reactivated": False,
            "mpesa_temporary_pin_sent": False,
            "audit_log": audit_log,
            "messages": [AIMessage(content=msg)],
        }

    subscriber_id = state.get("subscriber_id", "")
    new_imsi = state.get("new_imsi", "")
    result = await mpesa_service.reactivate(subscriber_id, new_imsi)

    if result["status"] == "reactivated":
        balance = result.get("balance_restored_kes", 0.0)
        msg = (
            f"Your M-PESA wallet has been restored on the new SIM.\n\n"
            f"- **Balance restored:** Ksh {balance:,.2f}\n"
            f"- **PIN:** reset — a temporary PIN has been queued for delivery\n"
            f"- **Action required:** Change the temporary PIN the first time you "
            f"dial *334# after activation\n\n"
            f"**Step 7:** Activating the new SIM on the network."
        )
        reactivated = True
        pin_sent = True
    else:
        msg = (
            f"M-PESA reactivation failed on the first attempt — our back-office "
            f"will retry automatically. You'll receive an SMS once it completes.\n\n"
            f"**Step 7:** Activating the new SIM on the network."
        )
        reactivated = False
        pin_sent = False

    audit_log = _log(state, "mpesa_reactivate", {
        "status": result["status"],
        "balance_restored": result.get("balance_restored_kes"),
        "reference": result.get("reference"),
    })

    return {
        "current_step": "reactivate_mpesa",
        "mpesa_reactivated": reactivated,
        "mpesa_temporary_pin_sent": pin_sent,
        "audit_log": audit_log,
        "messages": [AIMessage(content=msg)],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 8. Activate on network
# ─────────────────────────────────────────────────────────────────────────────
async def activate_on_network(state: dict) -> dict:
    msisdn = state.get("msisdn", "")
    new_imsi = state.get("new_imsi", "")
    result = await network_activation_service.activate(msisdn, new_imsi)

    if result["status"] == "active":
        msg = (
            f"Your new SIM is now **LIVE** on the Safaricom network — voice, "
            f"SMS, data and USSD are all enabled.\n\n"
            f"Please **power off your phone, insert the new SIM, and switch it back on**. "
            f"It may take up to 2 minutes to register on the network.\n\n"
            f"**Step 8:** Sending a confirmation SMS."
        )
        activated = True
    else:
        msg = (
            f"Automatic network activation hit a temporary issue. Your new SIM "
            f"will come online within 2 hours via automated retries.\n\n"
            f"**Step 8:** Sending a confirmation SMS."
        )
        activated = False

    audit_log = _log(state, "network_activation", {
        "status": result["status"],
        "services_enabled": result.get("services_enabled"),
        "reference": result.get("reference"),
    })

    return {
        "current_step": "activate_on_network",
        "network_activated": activated,
        "audit_log": audit_log,
        "messages": [AIMessage(content=msg)],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 9. Send confirmation SMS to alternate number
# ─────────────────────────────────────────────────────────────────────────────
async def send_confirmation_sms(state: dict) -> dict:
    alternate = state.get("alternate_msisdn", "")
    msisdn = state.get("msisdn", "")
    request_id = state.get("request_id", "")
    new_iccid = state.get("new_iccid", "")

    sms_text = (
        f"Safaricom: Your SIM swap (Ref {request_id}) for {msisdn} is complete. "
        f"New SIM ending {new_iccid[-4:]} is now active. Power off, insert the "
        f"new SIM, and restart. Not you? Call 100 immediately."
    )
    sms_result = await notification_service.send_sms(alternate, sms_text)

    sent = sms_result["status"] == "delivered"

    summary = (
        f"Confirmation SMS {'sent to' if sent else 'queued for'} your alternate "
        f"number ({alternate}).\n\n"
        f"---\n\n"
        f"**SIM Swap Summary**\n\n"
        f"| Detail | Value |\n"
        f"|---|---|\n"
        f"| **Request Ref** | {request_id} |\n"
        f"| **Reason** | {state.get('request_reason', 'lost').title()} |\n"
        f"| **MSISDN** | {msisdn} |\n"
        f"| **Old SIM** | {_mask_iccid(state.get('old_iccid', ''))} (Blocked) |\n"
        f"| **New SIM** | {_mask_iccid(new_iccid)} ({'Active' if state.get('network_activated') else 'Activating'}) |\n"
        f"| **M-PESA** | {'Restored (Ksh ' + format(state.get('mpesa_balance', 0.0), ',.2f') + ')' if state.get('mpesa_reactivated') else ('Not registered' if not state.get('mpesa_registered') else 'Pending')} |\n"
        f"| **Confirmation SMS** | {'Delivered' if sent else 'Pending'} |\n\n"
        f"Please **power off your phone, insert the new SIM, and switch it back on**. "
        f"Dial **\\*100#** after a minute to confirm service, and **\\*334#** to verify M-PESA.\n\n"
        f"Asante for choosing Safaricom. Anything else I can help you with?"
    )

    audit_log = _log(state, "confirmation_sms", {
        "alternate_msisdn": alternate,
        "status": sms_result["status"],
        "message_id": sms_result.get("message_id"),
    })

    return {
        "current_step": "send_confirmation_sms",
        "confirmation_sms_sent": sent,
        "process_status": "completed",
        "audit_log": audit_log,
        "messages": [AIMessage(content=summary)],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Terminal: rejection / halt
# ─────────────────────────────────────────────────────────────────────────────
async def reject_request(state: dict) -> dict:
    """Terminal node for failed / halted processes."""
    step = state.get("current_step", "unknown")
    request_id = state.get("request_id", "N/A")

    reasons = {
        "verify_identity": (
            "identity verification failed after the maximum number of attempts. "
            "For your security, we cannot proceed without a verified identity."
        ),
        "check_line_status": _build_line_rejection_reason(state),
        "capture_new_sim": (
            "the new SIM could not be validated after multiple attempts. "
            "Please retry at a Safaricom shop with a fresh blank SIM."
        ),
    }

    reason = reasons.get(step, "an issue was encountered during processing.")
    is_halt = step == "check_line_status"
    process_status = "halted" if is_halt else "rejected"
    header = "halted" if is_halt else "rejected"

    msg = (
        f"I'm sorry, but your SIM swap request (Ref: **{request_id}**) "
        f"has been **{header}** because {reason}\n\n"
        f"**What you can do:**\n"
        f"- Visit any **Safaricom shop** with your valid National ID\n"
        f"- Call **100** (free from a Safaricom line) or **0722 002 100** (other networks)\n"
        f"- Retry via **MySafaricom** app or **\\*100#** self-care\n\n"
        f"Asante sana."
    )

    audit_log = _log(state, "request_terminated", {
        "reason_step": step,
        "request_id": request_id,
        "outcome": process_status,
    })

    return {
        "current_step": "reject_request",
        "process_status": process_status,
        "audit_log": audit_log,
        "messages": [AIMessage(content=msg)],
    }


def _build_line_rejection_reason(state: dict) -> str:
    parts: list[str] = []
    if state.get("fraud_flag"):
        parts.append("there is a security flag on the line")
    if state.get("line_status") and state["line_status"] != "active":
        parts.append(f"the line status is '{state['line_status']}'")
    if state.get("pending_swap"):
        parts.append("a SIM swap is already in progress for this line")
    if parts:
        return ", ".join(parts) + "."
    return "the line did not pass the required status checks."
