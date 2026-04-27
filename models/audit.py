"""Audit log entry."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AuditEntry:
    timestamp: str
    step: str
    action: str
    request_id: str
    details: dict = field(default_factory=dict)
