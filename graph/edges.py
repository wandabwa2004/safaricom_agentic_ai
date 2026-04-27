"""Conditional edge routing logic for the SIM swap graph."""

import config
from graph.state import SimSwapState


def route_after_identity(state: SimSwapState) -> str:
    """Route after KBA: pass, retry, or reject."""
    if state.get("id_verification_status") == "passed":
        return "check_line_status"
    if state.get("id_verification_attempts", 0) >= state.get(
        "id_max_retries", config.MAX_IDENTITY_RETRIES
    ):
        return "reject_request"
    return "verify_identity"


def route_after_line_check(state: SimSwapState) -> str:
    """Route after line-status check: proceed or halt."""
    if state.get("line_check_passed"):
        return "capture_new_sim"
    return "reject_request"


def route_after_sim_validation(state: SimSwapState) -> str:
    """Route after SIM validation: proceed, retry, or reject."""
    if state.get("sim_validation_status") == "valid":
        return "block_old_sim"
    if state.get("sim_validation_attempts", 0) >= state.get(
        "sim_max_retries", config.MAX_SIM_SERIAL_RETRIES
    ):
        return "reject_request"
    return "capture_new_sim"
