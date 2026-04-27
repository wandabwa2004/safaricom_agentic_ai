"""SIM card model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Sim:
    iccid: str        # printed serial, 19–20 digits
    imsi: str         # HLR subscriber identity, 15 digits
    status: str       # "in_stock" | "bound" | "blocked"
    bound_msisdn: str | None = None
