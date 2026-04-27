"""Mock M-PESA reactivation service (PIN reset + balance restore)."""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import datetime

import config
from demo.seed_data import DEMO_SUBSCRIBERS


class MpesaService:
    def __init__(self, success_rate: float | None = None):
        self.success_rate = (
            success_rate
            if success_rate is not None
            else config.MPESA_REACTIVATION_SUCCESS_RATE
        )

    async def reactivate(self, subscriber_id: str, new_imsi: str) -> dict:
        """Re-bind the M-PESA wallet to the new SIM, reset PIN, restore balance."""
        await asyncio.sleep(random.uniform(0.7, 1.5))

        subscriber = DEMO_SUBSCRIBERS.get(subscriber_id, {})
        restored_balance = subscriber.get("mpesa_balance", 0.0)

        if not subscriber.get("mpesa_registered", False):
            return {
                "action": "mpesa_reactivate",
                "subscriber_id": subscriber_id,
                "status": "not_applicable",
                "reason": "subscriber is not registered for M-PESA",
                "timestamp": datetime.now().isoformat(),
            }

        success = random.random() < self.success_rate
        return {
            "action": "mpesa_reactivate",
            "subscriber_id": subscriber_id,
            "new_imsi": new_imsi,
            "status": "reactivated" if success else "failed",
            "pin_reset": success,
            "temporary_pin_sent": success,
            "balance_restored_kes": restored_balance if success else 0.0,
            "reference": f"MPESA-{uuid.uuid4().hex[:10].upper()}",
            "timestamp": datetime.now().isoformat(),
        }
