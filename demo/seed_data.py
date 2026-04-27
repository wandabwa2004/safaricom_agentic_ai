"""Sample subscriber data for demos."""

from __future__ import annotations

# Deterministic ICCIDs/IMSIs for reproducible demos.
# ICCID format: 89254 + 14 digits (19 total). Safaricom prefix.
# IMSI format:  63902 + 10 digits (15 total). MCC=639 (Kenya), MNC=02 (Safaricom).
DEMO_SUBSCRIBERS: dict[str, dict] = {
    "S001": {
        "name": "Wanjiku Kamau",
        "msisdn": "+254712345678",
        "id_number": "12345678",
        "alternate_msisdn": "+254711000001",
        "iccid": "8925412345678901234",
        "imsi": "639021234567890",
        "status": "active",
        "fraud_flag": False,
        "pending_swap": False,
        "mpesa_registered": True,
        "mpesa_balance": 15420.50,
        "last_topup_kes": 100.0,
        "last_topup_date": "2026-04-18",
        "frequently_called": ["+254711111111", "+254722222222", "+254733333333"],
        "recent_mpesa_txns": [
            {"type": "send", "to": "+254711111111", "amount": 500.0, "date": "2026-04-17"},
            {"type": "paybill", "to": "KPLC 888880", "amount": 1200.0, "date": "2026-04-15"},
            {"type": "receive", "from": "+254744444444", "amount": 2000.0, "date": "2026-04-12"},
        ],
    },
    "S002": {
        "name": "Otieno Odhiambo",
        "msisdn": "+254723456789",
        "id_number": "23456789",
        "alternate_msisdn": "+254722000002",
        "iccid": "8925423456789012345",
        "imsi": "639022345678901",
        "status": "active",
        "fraud_flag": False,
        "pending_swap": False,
        "mpesa_registered": True,
        "mpesa_balance": 35.50,   # very low balance — still valid, swap proceeds
        "last_topup_kes": 20.0,
        "last_topup_date": "2026-04-10",
        "frequently_called": ["+254712345678", "+254734567890"],
        "recent_mpesa_txns": [
            {"type": "buy_airtime", "amount": 20.0, "date": "2026-04-10"},
            {"type": "send", "to": "+254712345678", "amount": 100.0, "date": "2026-04-08"},
        ],
    },
    "S003": {
        "name": "Aisha Mohamed",
        "msisdn": "+254734567890",
        "id_number": "34567890",
        "alternate_msisdn": "+254733000003",
        "iccid": "8925434567890123456",
        "imsi": "639023456789012",
        "status": "suspended",   # halt at line check
        "fraud_flag": False,
        "pending_swap": False,
        "mpesa_registered": True,
        "mpesa_balance": 78950.75,
        "last_topup_kes": 500.0,
        "last_topup_date": "2026-03-28",
        "frequently_called": ["+254745678901", "+254756789012"],
        "recent_mpesa_txns": [
            {"type": "receive", "from": "+254722222222", "amount": 50000.0, "date": "2026-03-27"},
        ],
    },
    "S004": {
        "name": "Njoroge Mwangi",
        "msisdn": "+254745678901",
        "id_number": "45678901",
        "alternate_msisdn": "+254744000004",
        "iccid": "8925445678901234567",
        "imsi": "639024567890123",
        "status": "active",
        "fraud_flag": True,      # halt at line check
        "pending_swap": False,
        "mpesa_registered": True,
        "mpesa_balance": 5200.0,
        "last_topup_kes": 50.0,
        "last_topup_date": "2026-04-15",
        "frequently_called": ["+254734567890", "+254722222222"],
        "recent_mpesa_txns": [
            {"type": "send", "to": "+254734567890", "amount": 1500.0, "date": "2026-04-14"},
        ],
    },
    "S005": {
        "name": "Nyambura Wainaina",
        "msisdn": "+254756789012",
        "id_number": "56789012",
        "alternate_msisdn": "+254755000005",
        "iccid": "8925456789012345678",
        "imsi": "639025678901234",
        "status": "active",
        "fraud_flag": False,
        "pending_swap": True,    # halt — a swap is already in progress
        "mpesa_registered": True,
        "mpesa_balance": 42100.00,
        "last_topup_kes": 250.0,
        "last_topup_date": "2026-04-16",
        "frequently_called": ["+254712345678"],
        "recent_mpesa_txns": [
            {"type": "paybill", "to": "Nairobi Water 888888", "amount": 1800.0, "date": "2026-04-14"},
        ],
    },
}

# Lookup by MSISDN
MSISDN_TO_SUBSCRIBER_ID = {s["msisdn"]: sid for sid, s in DEMO_SUBSCRIBERS.items()}
