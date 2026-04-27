"""Subscriber (customer) model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LineStatus = Literal["active", "suspended", "barred", "churned"]


@dataclass
class Subscriber:
    subscriber_id: str          # internal: e.g. "S001"
    msisdn: str                 # +2547...
    name: str
    id_number: str              # Kenyan National ID
    alternate_msisdn: str       # second number used for final SMS confirmation
    iccid: str                  # currently-bound SIM serial
    imsi: str                   # currently-bound IMSI
    status: LineStatus
    fraud_flag: bool
    pending_swap: bool
    mpesa_registered: bool
    mpesa_balance: float        # Ksh
    last_topup_kes: float       # last airtime top-up amount
    last_topup_date: str        # ISO date
    frequently_called: list[str]  # list of MSISDNs
    recent_mpesa_txns: list[dict]  # most recent M-PESA transactions
