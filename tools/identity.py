"""Mock KBA (Knowledge-Based Authentication) service.

The subscriber is challenged on four independent facts and must get at least
KBA_QUESTIONS_REQUIRED correct to pass:
  1. National ID number
  2. Frequently called number
  3. A recent M-PESA transaction recipient / amount
  4. Last airtime top-up amount
"""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import datetime

import config
from demo.seed_data import DEMO_SUBSCRIBERS


class IdentityVerificationService:
    def __init__(self, success_rate: float | None = None):
        self.success_rate = (
            success_rate
            if success_rate is not None
            else config.IDENTITY_VERIFICATION_SUCCESS_RATE
        )

    async def verify(self, subscriber_id: str) -> dict:
        """Run KBA challenge. Returns which individual questions passed."""
        await asyncio.sleep(random.uniform(0.6, 1.4))

        subscriber = DEMO_SUBSCRIBERS.get(subscriber_id)
        questions = ["id_number", "frequently_called", "recent_mpesa", "last_topup"]

        # Each question independently succeeds with P(success_rate). Overall
        # pass requires at least KBA_QUESTIONS_REQUIRED correct.
        per_question: dict[str, bool] = {
            q: random.random() < self.success_rate for q in questions
        }
        correct = sum(per_question.values())
        passed = correct >= config.KBA_QUESTIONS_REQUIRED

        failure_reasons = {
            "id_number": "ID number didn't match our records",
            "frequently_called": "none of the numbers given matched recent call history",
            "recent_mpesa": "the M-PESA transaction details didn't match",
            "last_topup": "the last top-up amount didn't match",
        }
        failed_details = [
            failure_reasons[q] for q, ok in per_question.items() if not ok
        ]

        return {
            "verification_id": str(uuid.uuid4()),
            "subscriber_id": subscriber_id,
            "status": "verified" if passed else "failed",
            "questions_total": config.KBA_QUESTIONS_TOTAL,
            "questions_required": config.KBA_QUESTIONS_REQUIRED,
            "questions_correct": correct,
            "per_question": per_question,
            "failure_reasons": failed_details,
            "subscriber_exists": subscriber is not None,
            "timestamp": datetime.now().isoformat(),
        }
