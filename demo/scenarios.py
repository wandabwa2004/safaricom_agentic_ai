"""Pre-built demo scenarios for the SIM swap agent."""

SCENARIOS = {
    "happy_path": {
        "description": "Subscriber S001 reports a lost SIM. Everything succeeds first try.",
        "subscriber_id": "S001",
        "request_reason": "lost",
        "channel": "shop",
        "opening_message": "Hi, I've lost my Safaricom SIM. My number is +254712345678.",
        "expected_outcome": "completed",
        "config_overrides": {
            "IDENTITY_VERIFICATION_SUCCESS_RATE": 1.0,
            "LINE_STATUS_CLEAR_RATE": 1.0,
            "SIM_SERIAL_VALID_RATE": 1.0,
            "SIM_BLOCK_SUCCESS_RATE": 1.0,
            "SIM_PROVISION_SUCCESS_RATE": 1.0,
            "MPESA_REACTIVATION_SUCCESS_RATE": 1.0,
            "NETWORK_ACTIVATION_SUCCESS_RATE": 1.0,
            "SMS_DELIVERY_SUCCESS_RATE": 1.0,
        },
    },
    "identity_retry": {
        "description": "KBA fails once, succeeds on retry.",
        "subscriber_id": "S001",
        "request_reason": "stolen",
        "channel": "call_centre",
        "opening_message": "My SIM was stolen. Number is +254712345678.",
        "expected_outcome": "completed",
        "config_overrides": {
            # 0.80 per-question → roughly 41% chance of <3/4 on a given attempt.
            # Across 3 attempts it's overwhelmingly likely at least one succeeds.
            "IDENTITY_VERIFICATION_SUCCESS_RATE": 0.80,
            "SIM_SERIAL_VALID_RATE": 1.0,
            "SIM_PROVISION_SUCCESS_RATE": 1.0,
            "MPESA_REACTIVATION_SUCCESS_RATE": 1.0,
            "NETWORK_ACTIVATION_SUCCESS_RATE": 1.0,
            "SMS_DELIVERY_SUCCESS_RATE": 1.0,
        },
    },
    "full_failure": {
        "description": "KBA fails all 3 attempts — rejected.",
        "subscriber_id": "S001",
        "request_reason": "stolen",
        "channel": "ussd",
        "opening_message": "SIM stolen. Number +254712345678.",
        "expected_outcome": "rejected",
        "config_overrides": {
            "IDENTITY_VERIFICATION_SUCCESS_RATE": 0.0,
        },
    },
    "suspended_line": {
        "description": "S003's line is suspended — halted at line-status check.",
        "subscriber_id": "S003",
        "request_reason": "lost",
        "channel": "shop",
        "opening_message": "My line is suspended but I also lost my SIM. +254734567890.",
        "expected_outcome": "halted",
        "config_overrides": {
            "IDENTITY_VERIFICATION_SUCCESS_RATE": 1.0,
        },
    },
    "fraud_flag": {
        "description": "S004 has a fraud flag — halted at line-status check.",
        "subscriber_id": "S004",
        "request_reason": "lost",
        "channel": "call_centre",
        "opening_message": "Lost SIM. Number +254745678901.",
        "expected_outcome": "halted",
        "config_overrides": {
            "IDENTITY_VERIFICATION_SUCCESS_RATE": 1.0,
        },
    },
    "pending_swap": {
        "description": "S005 already has a swap in progress — halted.",
        "subscriber_id": "S005",
        "request_reason": "lost",
        "channel": "shop",
        "opening_message": "I need to swap my SIM again. +254756789012.",
        "expected_outcome": "halted",
        "config_overrides": {
            "IDENTITY_VERIFICATION_SUCCESS_RATE": 1.0,
        },
    },
    "bad_iccid": {
        "description": "New SIM fails validation 3 times — request rejected.",
        "subscriber_id": "S001",
        "request_reason": "damaged",
        "channel": "shop",
        "opening_message": "My SIM card is damaged. +254712345678.",
        "expected_outcome": "rejected",
        "config_overrides": {
            "IDENTITY_VERIFICATION_SUCCESS_RATE": 1.0,
            "SIM_SERIAL_VALID_RATE": 0.0,
        },
    },
    "mpesa_retry": {
        "description": "Happy path, but M-PESA reactivation fails — swap still completes.",
        "subscriber_id": "S002",
        "request_reason": "lost",
        "channel": "shop",
        "opening_message": "Lost SIM. Number +254723456789.",
        "expected_outcome": "completed",
        "config_overrides": {
            "IDENTITY_VERIFICATION_SUCCESS_RATE": 1.0,
            "SIM_SERIAL_VALID_RATE": 1.0,
            "SIM_BLOCK_SUCCESS_RATE": 1.0,
            "SIM_PROVISION_SUCCESS_RATE": 1.0,
            "MPESA_REACTIVATION_SUCCESS_RATE": 0.0,
            "NETWORK_ACTIVATION_SUCCESS_RATE": 1.0,
            "SMS_DELIVERY_SUCCESS_RATE": 1.0,
        },
    },
}
