"""CLI mode for running the SIM swap demo without Open WebUI."""

from __future__ import annotations

import asyncio
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from graph.builder import build_graph
from demo.scenarios import SCENARIOS
from demo.seed_data import DEMO_SUBSCRIBERS, MSISDN_TO_SUBSCRIBER_ID


def _initial_state(
    subscriber_id: str,
    request_reason: str = "lost",
    channel: str = "shop",
) -> dict:
    subscriber = DEMO_SUBSCRIBERS.get(subscriber_id, {})
    return {
        "subscriber_id": subscriber_id,
        "subscriber_name": subscriber.get("name", ""),
        "msisdn": subscriber.get("msisdn", ""),
        "alternate_msisdn": subscriber.get("alternate_msisdn", ""),
        "id_number": subscriber.get("id_number", ""),
        "request_id": "",
        "request_reason": request_reason,
        "request_timestamp": "",
        "channel": channel,
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


def _detect_reason(text: str) -> str:
    lower = text.lower()
    if "stolen" in lower or "steal" in lower or "theft" in lower:
        return "stolen"
    if "damage" in lower or "broken" in lower or "crack" in lower:
        return "damaged"
    if "upgrade" in lower or "4g" in lower or "5g" in lower:
        return "upgrade"
    return "lost"


def _detect_channel(text: str) -> str:
    lower = text.lower()
    if "ussd" in lower or "*100" in lower:
        return "ussd"
    if "call" in lower or "phone" in lower:
        return "call_centre"
    return "shop"


def _resolve_subscriber(user_input: str) -> str | None:
    """Resolve a subscriber ID (S001) or MSISDN (+2547…) from the user's text."""
    sid_match = re.search(r"\b(S\d{3})\b", user_input, re.IGNORECASE)
    if sid_match:
        sid = sid_match.group(1).upper()
        if sid in DEMO_SUBSCRIBERS:
            return sid

    phone_match = re.search(r"(\+254\d{9}|\b0\d{9}\b)", user_input)
    if phone_match:
        phone = phone_match.group(1)
        if not phone.startswith("+"):
            phone = "+254" + phone[1:]
        return MSISDN_TO_SUBSCRIBER_ID.get(phone)

    return None


async def run_interactive():
    graph = build_graph()

    print("=" * 64)
    print("  Safaricom SIM Swap Agent — CLI Demo")
    print("=" * 64)
    print()
    print("Available demo subscribers:")
    for sid, s in DEMO_SUBSCRIBERS.items():
        flags = []
        if s["status"] != "active":
            flags.append(s["status"])
        if s.get("fraud_flag"):
            flags.append("fraud flag")
        if s.get("pending_swap"):
            flags.append("pending swap")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        print(f"  {sid}: {s['name']} — {s['msisdn']}{flag_str}")
    print()
    print("Type a message to begin, or 'quit' to exit.")
    print("Example: 'I've lost my SIM. My number is +254712345678.'")
    print("-" * 64)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAsante sana. Kwaheri!")
            break

        if not user_input or user_input.lower() in ("quit", "exit", "q"):
            print("Asante sana. Kwaheri!")
            break

        subscriber_id = _resolve_subscriber(user_input)
        if not subscriber_id:
            print(
                "\nAgent: Karibu Safaricom. Please share your **MSISDN** "
                "(e.g. +254712345678) or your demo ID (e.g. S001)."
            )
            continue

        reason = _detect_reason(user_input)
        channel = _detect_channel(user_input)

        print(f"\n{'─' * 64}")
        print(f"Processing SIM swap for {subscriber_id} ({reason} / {channel})...")
        print(f"{'─' * 64}\n")

        result = await graph.ainvoke(_initial_state(subscriber_id, reason, channel))

        for m in result.get("messages", []):
            if hasattr(m, "content") and (not hasattr(m, "type") or m.type == "ai"):
                print(f"Agent: {m.content}\n")

        print(f"\n{'─' * 64}")
        print(f"AUDIT LOG ({len(result.get('audit_log', []))} entries)")
        print(f"{'─' * 64}")
        for entry in result.get("audit_log", []):
            ts = entry.get("timestamp", "")[:19]
            action = entry.get("action", "")
            print(f"  [{ts}] {action}")

        print(f"\nFinal status: {result.get('process_status', 'unknown')}")
        print(f"{'─' * 64}\n")


async def run_scenario(scenario_name: str):
    if scenario_name not in SCENARIOS:
        print(f"Unknown scenario: {scenario_name}")
        print(f"Available: {', '.join(SCENARIOS.keys())}")
        return

    scenario = SCENARIOS[scenario_name]
    print(f"\n{'=' * 64}")
    print(f"  Scenario: {scenario_name}")
    print(f"  {scenario['description']}")
    print(f"{'=' * 64}\n")

    overrides = scenario.get("config_overrides", {})
    originals = {k: getattr(config, k) for k in overrides}
    for k, v in overrides.items():
        setattr(config, k, v)

    # Reinitialise services with overridden rates
    from tools.identity import IdentityVerificationService
    from tools.sim_validation import SimValidationService
    from tools.sim_management import SimManagementService
    from tools.mpesa import MpesaService
    from tools.network_activation import NetworkActivationService
    from tools.notifications import NotificationService
    from graph import nodes

    nodes.identity_service = IdentityVerificationService()
    nodes.sim_validation_service = SimValidationService()
    nodes.sim_mgmt_service = SimManagementService()
    nodes.mpesa_service = MpesaService()
    nodes.network_activation_service = NetworkActivationService()
    nodes.notification_service = NotificationService()

    graph = build_graph()

    result = await graph.ainvoke(_initial_state(
        scenario["subscriber_id"],
        scenario.get("request_reason", "lost"),
        scenario.get("channel", "shop"),
    ))

    for m in result.get("messages", []):
        if hasattr(m, "content") and (not hasattr(m, "type") or m.type == "ai"):
            print(f"Agent: {m.content}\n")

    print(f"\n{'─' * 64}")
    print(f"AUDIT LOG ({len(result.get('audit_log', []))} entries)")
    print(f"{'─' * 64}")
    for entry in result.get("audit_log", []):
        ts = entry.get("timestamp", "")[:19]
        action = entry.get("action", "")
        print(f"  [{ts}] {action}")

    status = result.get("process_status", "unknown")
    expected = scenario.get("expected_outcome", "")
    match = "PASS" if status == expected else "MISMATCH"
    print(f"\nFinal status: {status} (expected: {expected}) [{match}]")
    print(f"{'─' * 64}\n")

    # Restore config
    for k, v in originals.items():
        setattr(config, k, v)


def main():
    if len(sys.argv) > 1:
        name = sys.argv[1]
        if name == "--list":
            print("Available scenarios:")
            for n, s in SCENARIOS.items():
                print(f"  {n}: {s['description']}")
            return
        asyncio.run(run_scenario(name))
    else:
        asyncio.run(run_interactive())


if __name__ == "__main__":
    main()
