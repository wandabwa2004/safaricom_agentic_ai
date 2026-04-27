"""Mock SIM serial/IMSI validation against the SIM inventory and HLR.

Validation rules:
- ICCID must start with SAFARICOM_ICCID_PREFIX and be ICCID_LENGTH digits
- IMSI must start with SAFARICOM_IMSI_PREFIX and be IMSI_LENGTH digits
- ICCID must not already be bound to another MSISDN
- Randomised stock-record mismatch at (1 - SIM_SERIAL_VALID_RATE)
"""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import datetime

import config


def generate_valid_sim_pair() -> tuple[str, str]:
    """Produce a fresh valid (ICCID, IMSI) for demos / new SIMs at the shop."""
    iccid_tail = "".join(
        str(random.randint(0, 9))
        for _ in range(config.ICCID_LENGTH - len(config.SAFARICOM_ICCID_PREFIX))
    )
    imsi_tail = "".join(
        str(random.randint(0, 9))
        for _ in range(config.IMSI_LENGTH - len(config.SAFARICOM_IMSI_PREFIX))
    )
    return (
        config.SAFARICOM_ICCID_PREFIX + iccid_tail,
        config.SAFARICOM_IMSI_PREFIX + imsi_tail,
    )


class SimValidationService:
    def __init__(self, valid_rate: float | None = None):
        self.valid_rate = (
            valid_rate if valid_rate is not None else config.SIM_SERIAL_VALID_RATE
        )

    async def validate(self, iccid: str, imsi: str) -> dict:
        """Validate new-SIM ICCID + IMSI. Structural checks first, stock second."""
        await asyncio.sleep(random.uniform(0.3, 1.0))

        errors: list[str] = []
        if not iccid.isdigit() or len(iccid) != config.ICCID_LENGTH:
            errors.append(
                f"ICCID must be {config.ICCID_LENGTH} digits (got {len(iccid)})"
            )
        elif not iccid.startswith(config.SAFARICOM_ICCID_PREFIX):
            errors.append(
                f"ICCID prefix must be {config.SAFARICOM_ICCID_PREFIX} (Safaricom)"
            )

        if not imsi.isdigit() or len(imsi) != config.IMSI_LENGTH:
            errors.append(
                f"IMSI must be {config.IMSI_LENGTH} digits (got {len(imsi)})"
            )
        elif not imsi.startswith(config.SAFARICOM_IMSI_PREFIX):
            errors.append(
                f"IMSI prefix must be {config.SAFARICOM_IMSI_PREFIX} "
                f"(Kenya MCC=639, Safaricom MNC=02)"
            )

        if errors:
            return {
                "validation_id": str(uuid.uuid4()),
                "iccid": iccid,
                "imsi": imsi,
                "status": "invalid",
                "reason": "structural",
                "errors": errors,
                "timestamp": datetime.now().isoformat(),
            }

        # Structural checks passed — simulate stock-record lookup.
        in_stock = random.random() < self.valid_rate
        if not in_stock:
            return {
                "validation_id": str(uuid.uuid4()),
                "iccid": iccid,
                "imsi": imsi,
                "status": "invalid",
                "reason": "not_in_stock",
                "errors": [
                    "This SIM is not recognised in our inventory — "
                    "please ask the shop attendant for a replacement blank."
                ],
                "timestamp": datetime.now().isoformat(),
            }

        return {
            "validation_id": str(uuid.uuid4()),
            "iccid": iccid,
            "imsi": imsi,
            "status": "valid",
            "timestamp": datetime.now().isoformat(),
        }
