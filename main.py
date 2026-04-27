"""FastAPI app with OpenAI-compatible /v1/chat/completions endpoint."""

from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import config
from graph.builder import build_graph, get_graph_mermaid
from demo.seed_data import DEMO_SUBSCRIBERS, MSISDN_TO_SUBSCRIBER_ID


# ── Session store ────────────────────────────────────────────────────────────
sessions: dict[str, dict] = {}


# ── App lifecycle ────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.graph = build_graph()
    yield


app = FastAPI(
    title="Safaricom SIM Swap Agent",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / response models ───────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = config.MODEL_NAME
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float = 0.7
    max_tokens: int = 4096


# ── Helpers ──────────────────────────────────────────────────────────────────
def _extract_session_id(messages: list[ChatMessage]) -> str:
    """Derive a stable session ID from the conversation's first user message."""
    for m in messages:
        if m.role == "user":
            return str(uuid.uuid5(uuid.NAMESPACE_DNS, m.content[:80]))
    return str(uuid.uuid4())


def _extract_subscriber_context(text: str) -> dict:
    """Try to extract subscriber_id or MSISDN from the user message."""
    ctx: dict = {}

    sid_match = re.search(r"\b(S\d{3})\b", text, re.IGNORECASE)
    if sid_match:
        sid = sid_match.group(1).upper()
        if sid in DEMO_SUBSCRIBERS:
            ctx["subscriber_id"] = sid
            return ctx

    phone_match = re.search(r"(\+254\d{9}|\b0\d{9}\b)", text)
    if phone_match:
        phone = phone_match.group(1)
        if not phone.startswith("+"):
            phone = "+254" + phone[1:]
        sid = MSISDN_TO_SUBSCRIBER_ID.get(phone)
        if sid:
            ctx["subscriber_id"] = sid
            return ctx

    return ctx


def _detect_reason(text: str) -> str:
    lower = text.lower()
    if "stolen" in lower or "steal" in lower or "theft" in lower:
        return "stolen"
    if "damage" in lower or "broken" in lower or "crack" in lower:
        return "damaged"
    if "upgrade" in lower or "4g" in lower or "5g" in lower:
        return "upgrade"
    return "lost"


def _detect_channel(text: str) -> str:
    lower = text.lower()
    if "ussd" in lower or "*100" in lower:
        return "ussd"
    if "call" in lower or "phone" in lower:
        return "call_centre"
    return "shop"


def _initial_state(subscriber_id: str, reason: str, channel: str) -> dict:
    subscriber = DEMO_SUBSCRIBERS.get(subscriber_id, {})
    return {
        "subscriber_id": subscriber_id,
        "subscriber_name": subscriber.get("name", ""),
        "msisdn": subscriber.get("msisdn", ""),
        "alternate_msisdn": subscriber.get("alternate_msisdn", ""),
        "id_number": subscriber.get("id_number", ""),
        "request_id": "",
        "request_reason": reason,
        "request_timestamp": "",
        "channel": channel,
        "id_verification_status": "pending",
        "id_verification_attempts": 0,
        "id_max_retries": config.MAX_IDENTITY_RETRIES,
        "kba_questions_correct": 0,
        "line_status": "",
        "fraud_flag": False,
        "pending_swap": False,
        "line_check_passed": False,
        "new_iccid": "",
        "new_imsi": "",
        "sim_validation_status": "pending",
        "sim_validation_attempts": 0,
        "sim_max_retries": config.MAX_SIM_SERIAL_RETRIES,
        "sim_validation_errors": [],
        "old_iccid": "",
        "old_imsi": "",
        "old_sim_blocked": False,
        "new_sim_provisioned": False,
        "mpesa_registered": False,
        "mpesa_balance": 0.0,
        "mpesa_reactivated": False,
        "mpesa_temporary_pin_sent": False,
        "network_activated": False,
        "confirmation_sms_sent": False,
        "current_step": "",
        "audit_log": [],
        "error_messages": [],
        "process_status": "in_progress",
        "messages": [],
    }


async def _run_graph(graph, user_text: str, session_id: str) -> str:
    ctx = _extract_subscriber_context(user_text)
    subscriber_id = ctx.get("subscriber_id", "")

    session = sessions.get(session_id)

    # If graph already completed/rejected/halted for this session
    if session and session.get("process_status") in ("completed", "rejected", "halted"):
        return (
            "Your SIM swap request has already been processed. "
            "If you need further help, please visit any Safaricom shop or call 100 "
            "(free from a Safaricom line). Asante!"
        )

    # If no subscriber yet, prompt
    if not subscriber_id and not session:
        return (
            "Karibu Safaricom! I can help you replace a lost, stolen, or damaged SIM.\n\n"
            "To get started, please share your **Safaricom number** "
            "(e.g. +254712345678) or a demo subscriber ID like **S001**."
        )

    # Start new session
    if not session and subscriber_id:
        reason = _detect_reason(user_text)
        channel = _detect_channel(user_text)

        result = await graph.ainvoke(_initial_state(subscriber_id, reason, channel))

        all_messages = []
        for m in result.get("messages", []):
            if hasattr(m, "content") and (not hasattr(m, "type") or m.type == "ai"):
                all_messages.append(m.content)

        sessions[session_id] = {
            "process_status": result.get("process_status", "completed"),
            "result": result,
        }
        return "\n\n---\n\n".join(all_messages)

    return (
        "I couldn't find that number on the Safaricom network. "
        "Please share your **MSISDN** starting with +254, or a demo subscriber ID (e.g. S001)."
    )


# ── API endpoints ────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "safaricom-sim-swap-agent"}


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": config.MODEL_NAME,
                "object": "model",
                "created": 1700000000,
                "owned_by": "safaricom",
                "name": "Safaricom SIM Swap Agent",
            }
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    user_messages = [m for m in request.messages if m.role == "user"]
    user_text = user_messages[-1].content if user_messages else ""
    session_id = _extract_session_id(request.messages)
    graph = app.state.graph

    if request.stream:
        return StreamingResponse(
            _stream_response(graph, user_text, session_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    response_text = await _run_graph(graph, user_text, session_id)
    return _format_completion(response_text)


async def _stream_response(graph, user_text: str, session_id: str):
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created = int(time.time())

    response_text = await _run_graph(graph, user_text, session_id)

    chunk_size = 15
    for i in range(0, len(response_text), chunk_size):
        chunk = response_text[i : i + chunk_size]
        data = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": config.MODEL_NAME,
            "choices": [
                {"index": 0, "delta": {"content": chunk}, "finish_reason": None}
            ],
        }
        yield f"data: {json.dumps(data)}\n\n"
        await asyncio.sleep(0.03)

    data = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": config.MODEL_NAME,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(data)}\n\n"
    yield "data: [DONE]\n\n"


def _format_completion(text: str) -> dict:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": config.MODEL_NAME,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


@app.get("/graph/mermaid")
async def graph_mermaid():
    return {"mermaid": get_graph_mermaid()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)
