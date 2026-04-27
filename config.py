"""Configuration for the Safaricom SIM Swap Agent."""

import os
from dotenv import load_dotenv

load_dotenv()

# LLM
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

# Configurable failure rates for demo scenarios
IDENTITY_VERIFICATION_SUCCESS_RATE = 0.80
LINE_STATUS_CLEAR_RATE = 0.95
SIM_SERIAL_VALID_RATE = 0.95
SIM_BLOCK_SUCCESS_RATE = 0.99
SIM_PROVISION_SUCCESS_RATE = 0.97
MPESA_REACTIVATION_SUCCESS_RATE = 0.95
NETWORK_ACTIVATION_SUCCESS_RATE = 0.98
SMS_DELIVERY_SUCCESS_RATE = 0.97

# Process limits
MAX_IDENTITY_RETRIES = 3
MAX_SIM_SERIAL_RETRIES = 3

# KBA: how many of the four challenge questions must be correct
KBA_QUESTIONS_TOTAL = 4
KBA_QUESTIONS_REQUIRED = 3

# ICCID: Safaricom SIMs start with 89254 (ITU country code 254 = Kenya)
SAFARICOM_ICCID_PREFIX = "89254"
ICCID_LENGTH = 19  # typical Safaricom ICCID length (can also be 20)

# IMSI: Kenya MCC = 639, Safaricom MNC = 02
SAFARICOM_IMSI_PREFIX = "63902"
IMSI_LENGTH = 15

# API
API_HOST = "0.0.0.0"
API_PORT = 8002
MODEL_NAME = "safaricom-sim-swap-agent"
