# Safaricom SIM Swap Agent

An agentic AI system that autonomously handles the **SIM card replacement (swap)**
process for Safaricom Kenya. Built with **LangGraph** for deterministic
orchestration and **FastAPI** (OpenAI-compatible) for easy integration with
Open WebUI or any OpenAI client.


---

## The process modelled

```
Customer reports lost SIM
        │
        ▼
  Verify Identity   (ID#, frequent numbers, recent M-PESA, last top-up)
        │  fail × 3 ──► Rejected
        ▼
  Check Line Status (fraud / suspended / pending swap)
        │  flagged   ──► Halted
        ▼
  Capture New SIM   (ICCID + IMSI validation)
        │  invalid   ──► Error
        ▼
  Core Swap:
   Block old SIM → Provision new SIM (bind IMSI↔MSISDN)
                → Reactivate M-PESA (PIN reset, restore balance)
                → Activate on network
        │
        ▼
  SMS confirmation to alternate number
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your ANTHROPIC_API_KEY
```

## Run the server

```bash
uvicorn main:app --host 0.0.0.0 --port 8002
```

Then point Open WebUI (or any OpenAI client) at `http://localhost:8002/v1`.

## Run the CLI demo

```bash
# Interactive session
python -m demo.cli

# List scenarios
python -m demo.cli --list

# Run a specific scenario
python -m demo.cli happy_path
python -m demo.cli identity_retry
python -m demo.cli fraud_flag
python -m demo.cli bad_iccid
python -m demo.cli full_failure
```

## Demo subscribers

| MSISDN | Name | Line status | Notes |
|---|---|---|---|
| `+254712345678` (S001) | Wanjiku Kamau | active | happy path |
| `+254723456789` (S002) | Otieno Odhiambo | active | low M-PESA balance |
| `+254734567890` (S003) | Aisha Mohamed | suspended | halt at line check |
| `+254745678901` (S004) | Njoroge Mwangi | active, fraud_flag | halt at line check |
| `+254756789012` (S005) | Nyambura Wainaina | active, pending_swap | halt at line check |

## Tests

```bash
pytest tests/ -v
```

## Project layout

```
safaricom_agentic_ai/
├── main.py                      FastAPI + OpenAI-compatible endpoint
├── config.py                    success rates, retry limits, ICCID/IMSI rules
├── graph/                       LangGraph state machine
│   ├── state.py                 SimSwapState TypedDict
│   ├── nodes.py                 step functions
│   ├── edges.py                 conditional routing
│   ├── builder.py               graph compilation
│   └── prompts.py               system prompt
├── models/                      typed data models
├── tools/                       mock Safaricom / M-PESA services
├── demo/                        CLI + scenarios + seed subscribers
└── tests/                       pytest suite
```