"""Mock SMS notification service — used to confirm swap to alternate number."""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import datetime

import config


class NotificationService:
    def __init__(self, sms_rate: float | None = None):
        self.sms_rate = (
            sms_rate if sms_rate is not None else config.SMS_DELIVERY_SUCCESS_RATE
        )

    async def send_sms(self, msisdn: str, message: str) -> dict:
        """Send SMS via Safaricom bulk SMS gateway."""
        await asyncio.sleep(random.uniform(0.3, 0.9))
        success = random.random() < self.sms_rate
        return {
            "action": "send_sms",
            "provider": "Safaricom_BulkSMS",
            "msisdn": msisdn,
            "status": "delivered" if success else "failed",
            "message_id": f"SAF-{uuid.uuid4().hex[:10].upper()}",
            "delivery_report": "DeliveredToTerminal" if success else "DeliveryImpossible",
            "cost_kes": 1.0,
            "timestamp": datetime.now().isoformat(),
        }
