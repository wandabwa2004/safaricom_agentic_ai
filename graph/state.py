"""LangGraph state schema for the SIM swap process."""

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class SimSwapState(TypedDict):
    # Subscriber context
    subscriber_id: str
    subscriber_name: str
    msisdn: str
    alternate_msisdn: str
    id_number: str

    # Request context
    request_id: str
    request_reason: str          # "lost" | "stolen" | "damaged" | "upgrade"
    request_timestamp: str
    channel: str                 # "shop" | "call_centre" | "ussd"

    # Identity verification (KBA)
    id_verification_status: str  # "pending" | "passed" | "failed"
    id_verification_attempts: int
    id_max_retries: int
    kba_questions_correct: int

    # Line status checks
    line_status: str             # "active" | "suspended" | "barred" | "churned" | "not_found"
    fraud_flag: bool
    pending_swap: bool
    line_check_passed: bool

    # New SIM capture
    new_iccid: str
    new_imsi: str
    sim_validation_status: str   # "pending" | "valid" | "invalid"
    sim_validation_attempts: int
    sim_max_retries: int
    sim_validation_errors: list[str]

    # Current (to-be-blocked) SIM
    old_iccid: str
    old_imsi: str
    old_sim_blocked: bool

    # Provisioning
    new_sim_provisioned: bool

    # M-PESA
    mpesa_registered: bool
    mpesa_balance: float
    mpesa_reactivated: bool
    mpesa_temporary_pin_sent: bool

    # Network
    network_activated: bool

    # Notifications
    confirmation_sms_sent: bool

    # Process metadata
    current_step: str
    audit_log: list[dict]
    error_messages: list[str]
    process_status: str          # "in_progress" | "completed" | "rejected" | "halted"

    # Conversation
    messages: Annotated[list, add_messages]
