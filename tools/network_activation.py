"""Mock network activation service (HLR/MME update to bring the SIM online)."""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import datetime

import config


class NetworkActivationService:
    def __init__(self, success_rate: float | None = None):
        self.success_rate = (
            success_rate
            if success_rate is not None
            else config.NETWORK_ACTIVATION_SUCCESS_RATE
        )

    async def activate(self, msisdn: str, new_imsi: str) -> dict:
        """Flag the new IMSI as active on the HLR — voice/SMS/data all enabled."""
        await asyncio.sleep(random.uniform(0.5, 1.2))
        success = random.random() < self.success_rate
        return {
            "action": "network_activate",
            "msisdn": msisdn,
            "new_imsi": new_imsi,
            "status": "active" if success else "failed",
            "services_enabled": (
                ["voice", "sms", "data", "ussd"] if success else []
            ),
            "reference": f"ACT-{uuid.uuid4().hex[:10].upper()}",
            "timestamp": datetime.now().isoformat(),
        }
