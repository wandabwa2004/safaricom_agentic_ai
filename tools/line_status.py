"""Mock HLR line-status service."""

from __future__ import annotations

import asyncio
import random
from datetime import datetime

from demo.seed_data import DEMO_SUBSCRIBERS


class LineStatusService:
    async def check(self, subscriber_id: str) -> dict:
        """Return status, fraud flag, and any pending swap for the line."""
        await asyncio.sleep(random.uniform(0.3, 0.9))

        subscriber = DEMO_SUBSCRIBERS.get(subscriber_id)
        if not subscriber:
            return {
                "subscriber_id": subscriber_id,
                "found": False,
                "status": "not_found",
                "timestamp": datetime.now().isoformat(),
            }

        return {
            "subscriber_id": subscriber_id,
            "found": True,
            "msisdn": subscriber["msisdn"],
            "name": subscriber["name"],
            "status": subscriber["status"],
            "fraud_flag": subscriber["fraud_flag"],
            "pending_swap": subscriber["pending_swap"],
            "current_iccid": subscriber["iccid"],
            "current_imsi": subscriber["imsi"],
            "alternate_msisdn": subscriber["alternate_msisdn"],
            "mpesa_registered": subscriber["mpesa_registered"],
            "mpesa_balance": subscriber["mpesa_balance"],
            "timestamp": datetime.now().isoformat(),
        }
