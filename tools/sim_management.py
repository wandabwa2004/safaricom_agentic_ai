"""Mock SIM management service: block old SIM, provision new SIM."""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import datetime

import config


class SimManagementService:
    def __init__(
        self,
        block_rate: float | None = None,
        provision_rate: float | None = None,
    ):
        self.block_rate = (
            block_rate if block_rate is not None else config.SIM_BLOCK_SUCCESS_RATE
        )
        self.provision_rate = (
            provision_rate
            if provision_rate is not None
            else config.SIM_PROVISION_SUCCESS_RATE
        )

    async def block_old(self, iccid: str, imsi: str) -> dict:
        """Hot-list the old SIM on the HLR — instantly unusable on the network."""
        await asyncio.sleep(random.uniform(0.4, 1.2))
        success = random.random() < self.block_rate
        return {
            "action": "block_old_sim",
            "iccid": iccid,
            "imsi": imsi,
            "status": "blocked" if success else "failed",
            "hlr_updated": success,
            "reference": f"BLK-{uuid.uuid4().hex[:10].upper()}",
            "timestamp": datetime.now().isoformat(),
        }

    async def provision_new(self, msisdn: str, new_iccid: str, new_imsi: str) -> dict:
        """Bind new IMSI↔MSISDN in HLR and activate the new SIM as the line's SIM."""
        await asyncio.sleep(random.uniform(0.8, 1.6))
        success = random.random() < self.provision_rate
        return {
            "action": "provision_new_sim",
            "msisdn": msisdn,
            "new_iccid": new_iccid,
            "new_imsi": new_imsi,
            "status": "provisioned" if success else "failed",
            "imsi_bound": success,
            "reference": f"PROV-{uuid.uuid4().hex[:10].upper()}",
            "timestamp": datetime.now().isoformat(),
        }
