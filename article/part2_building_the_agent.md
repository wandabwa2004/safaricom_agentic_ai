# Part 2: From Theory to Code — Building the SIM Swap Agent in LangGraph

*Stuck behind a firewall? Read the article for FREE here.*

---

In Part 1, I covered what agentic AI actually means and why a SIM card replacement workflow is a good way to test whether something is genuinely agentic. I introduced the four mental building blocks that every agent shares: state, tools, nodes, and edges. If you haven't read that one yet, I'd suggest starting there because this article builds directly on it.

Here in Part 2, we make all of that concrete. We're translating each of those four concepts into real Python code using LangGraph, and by the end of the article, you'll have a working agent that can run the full SIM swap flow from identity verification all the way to customer notification. All the code is open-source and linked at the end, so you can pull it down and run it yourself.

No handwaving here. Let's get into it.

---

## Starting with the State Object

Remember the notebook analogy from Part 1? State is what the agent carries from step to step, everything it knows at any given moment. In LangGraph, state is defined as a Python `TypedDict`.

The choice of `TypedDict` over a class is deliberate. It serialises cleanly, it's straightforward to checkpoint and restore, and LangGraph can diff it without any custom logic. Here's the full state for the SIM swap agent:

```python
from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages

class SimSwapState(TypedDict):
    # Subscriber context
    subscriber_id: str
    subscriber_name: str
    msisdn: str
    alternate_msisdn: str
    id_number: str

    # Request context
    request_id: str
    request_reason: str          # "lost" | "stolen" | "damaged" | "upgrade"
    request_timestamp: str
    channel: str                 # "shop" | "call_centre" | "ussd"

    # Identity verification (KBA)
    id_verification_status: str  # "pending" | "passed" | "failed"
    id_verification_attempts: int
    id_max_retries: int
    kba_questions_correct: int

    # Line status checks
    line_status: str             # "active" | "suspended" | "barred" | "churned" | "not_found"
    fraud_flag: bool
    pending_swap: bool
    line_check_passed: bool

    # New SIM capture
    new_iccid: str
    new_imsi: str
    sim_validation_status: str   # "pending" | "valid" | "invalid"
    sim_validation_attempts: int
    sim_max_retries: int
    sim_validation_errors: list[str]

    # Current (to-be-blocked) SIM
    old_iccid: str
    old_imsi: str
    old_sim_blocked: bool

    # Provisioning
    new_sim_provisioned: bool

    # M-PESA
    mpesa_registered: bool
    mpesa_balance: float
    mpesa_reactivated: bool
    mpesa_temporary_pin_sent: bool

    # Network
    network_activated: bool

    # Notifications
    confirmation_sms_sent: bool

    # Process metadata
    current_step: str
    audit_log: list[dict]
    error_messages: list[str]
    process_status: str          # "in_progress" | "completed" | "rejected" | "halted"

    # Conversation
    messages: Annotated[list, add_messages]
```

That looks like a lot of fields, but read it in groups and it makes sense. The first block is what you know when the customer walks in: their MSISDN (phone number), their ID number, and an alternate number to send the final confirmation SMS to. Then comes request context — why they're here and which channel they came through.

From there, every block maps directly to a stage in the workflow. KBA tracking holds the attempt count. Line status flags hold whether fraud or a pending swap was found. The SIM capture block tracks validation retries. The pipeline fields (blocked, provisioned, M-PESA, network) flip from `False` to `True` as each step completes. And the metadata block at the bottom gives you audit log, error accumulation, and an overall process status.

One field worth calling out specifically is `messages`. Notice it uses `Annotated[list, add_messages]` rather than just `list`. Everything else in the state is last-write-wins: if a node returns a new value for `fraud_flag`, it overwrites the old one. But `messages` is different. LangGraph sees that `add_messages` annotation and **merges** new messages into the existing list rather than replacing it. That's how the agent accumulates a full conversation history as it moves through the steps.

**The key insight:** the graph itself is stateless. It has no memory between runs. The state is what carries everything. Every business rule in this workflow — whether a retry is allowed, whether fraud was flagged, whether M-PESA needs reactivating — lives in those fields.

---

## The Tools

Tools are what the agent can actually do in the real world. In this implementation, each downstream system gets its own service class. Here's the full list:

| Tool | What it simulates |
|---|---|
| `IdentityVerificationService` | KBA challenge: ID number, frequently called numbers, recent M-PESA transaction, last top-up amount |
| `LineStatusService` | HLR lookup: line status (active/suspended/barred) + fraud flag + pending swap check |
| `SimValidationService` | Validates ICCID format (19–20 digits, `89254…` Kenya prefix) and IMSI uniqueness |
| `SimManagementService` | Blocks the old SIM, provisions the new one (binds IMSI to MSISDN in the HLR) |
| `MpesaService` | Restores the M-PESA wallet on the new SIM and resets the PIN |
| `NetworkActivationService` | Activates voice, SMS, data, and USSD on the new SIM |
| `NotificationService` | Sends the confirmation SMS to the alternate number |

In this repo, all seven are mocked. They use configurable success rates and a short `asyncio.sleep` to simulate real-world latency. Here's what `IdentityVerificationService` looks like:

```python
class IdentityVerificationService:
    def __init__(self, success_rate: float | None = None):
        self.success_rate = (
            success_rate if success_rate is not None
            else config.IDENTITY_VERIFICATION_SUCCESS_RATE
        )

    async def verify(self, subscriber_id: str) -> dict:
        await asyncio.sleep(random.uniform(0.6, 1.4))

        questions = ["id_number", "frequently_called", "recent_mpesa", "last_topup"]
        per_question: dict[str, bool] = {
            q: random.random() < self.success_rate for q in questions
        }
        correct = sum(per_question.values())
        passed = correct >= config.KBA_QUESTIONS_REQUIRED

        return {
            "verification_id": str(uuid.uuid4()),
            "status": "verified" if passed else "failed",
            "questions_total": config.KBA_QUESTIONS_TOTAL,
            "questions_required": config.KBA_QUESTIONS_REQUIRED,
            "questions_correct": correct,
            "per_question": per_question,
            ...
        }
```

The KBA challenge asks the customer four independent questions. They need to get at least three right to pass, which is configurable in `config.py`:

```python
KBA_QUESTIONS_TOTAL = 4
KBA_QUESTIONS_REQUIRED = 3
MAX_IDENTITY_RETRIES = 3
MAX_SIM_SERIAL_RETRIES = 3
```

You might be wondering why mock if we're building something real. The answer is that the thing being built and tested here is the agent's decision-making logic: the retries, the routing, the state transitions, the fraud handling. That logic is completely separate from the actual Safaricom API. Mocking the services isolates the agent logic so you can run dozens of deterministic scenarios without needing a live network. When you're ready to go to production, you swap the mock classes for real HTTP clients and the rest of the code doesn't change.

---

## The Nodes

Nodes are the individual steps of the workflow, and in LangGraph they follow a simple contract: each node is an `async` function that takes the full state as input and returns a dictionary of just the fields it changed. LangGraph merges the partial update back into the state automatically.

Here's the first node, `initiate_request`, which fires when a customer starts the process:

```python
async def initiate_request(state: dict) -> dict:
    request_id = f"SWP-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now().isoformat()

    msg = (
        f"Karibu Safaricom. I'm here to help you replace your SIM for a "
        f"**{state.get('request_reason', 'lost')}** line.\n\n"
        f"Your request reference is **{request_id}**. "
        f"I'll take you through the swap step by step.\n\n"
        f"**Step 1:** Let's first verify your identity."
    )

    audit_log = _log(state, "request_initiated", {
        "request_id": request_id,
        "request_reason": state.get("request_reason", "lost"),
        "subscriber_id": state.get("subscriber_id", ""),
        "channel": state.get("channel", "shop"),
    })

    return {
        "request_id": request_id,
        "request_timestamp": now,
        "current_step": "initiate_request",
        "process_status": "in_progress",
        "id_verification_status": "pending",
        "id_verification_attempts": 0,
        "id_max_retries": config.MAX_IDENTITY_RETRIES,
        "sim_validation_status": "pending",
        "sim_validation_attempts": 0,
        "sim_max_retries": config.MAX_SIM_SERIAL_RETRIES,
        "old_sim_blocked": False,
        "new_sim_provisioned": False,
        ...
        "audit_log": audit_log,
        "messages": [AIMessage(content=msg)],
    }
```

This node does three things: generates a unique request reference, sets every counter and flag to its initial value, and appends the opening message. That last point is intentional — all initialisation lives here, not scattered across downstream nodes.

Now let's look at `verify_identity`, because this is the first node where things can actually go wrong:

```python
async def verify_identity(state: dict) -> dict:
    attempts = state.get("id_verification_attempts", 0) + 1
    result = await identity_service.verify(state["subscriber_id"])

    correct = result["questions_correct"]
    required = result["questions_required"]
    total = result["questions_total"]

    if result["status"] == "verified":
        msg = (
            f"Identity verified — you answered **{correct}/{total}** questions "
            f"correctly (minimum {required} required). Thank you!\n\n"
            f"**Step 2:** I'll now check the status of your line."
        )
        status = "passed"
    else:
        remaining = state.get("id_max_retries", config.MAX_IDENTITY_RETRIES) - attempts
        reasons = "; ".join(result.get("failure_reasons", []))
        if remaining > 0:
            msg = (
                f"I got **{correct}/{total}** correct — I need at least **{required}**. "
                f"Specifically: {reasons}.\n\n"
                f"Let's try again. You have **{remaining}** attempt(s) remaining."
            )
        else:
            msg = (
                f"Identity verification failed after "
                f"{state.get('id_max_retries', config.MAX_IDENTITY_RETRIES)} attempts. "
                f"For your security, I cannot proceed with the SIM swap."
            )
        status = "failed"

    return {
        "current_step": "verify_identity",
        "id_verification_status": status,
        "id_verification_attempts": attempts,
        "kba_questions_correct": correct,
        "audit_log": _log(state, "identity_verification", {...}),
        "messages": [AIMessage(content=msg)],
    }
```

A few things to notice here. First, the node increments `id_verification_attempts` itself — it owns that counter. Second, it produces a contextual message depending on the outcome: if retries remain, it tells the customer how many are left; if they're exhausted, it delivers the bad news. Third, and most importantly, **it does not decide what happens next**. It just sets `id_verification_status` to `"passed"` or `"failed"` and returns. The decision about whether to retry or reject lives elsewhere. That's the edge's job.

The other nodes follow the same pattern. `check_line_status` queries the HLR and sets `fraud_flag`, `pending_swap`, and `line_check_passed`. `capture_new_sim` validates the new SIM's ICCID and IMSI. Then the core pipeline runs sequentially: `block_old_sim`, `provision_new_sim`, `reactivate_mpesa`, `activate_on_network`, and finally `send_confirmation_sms`, which assembles the full swap summary table for the customer.

There's also a shared `_log` helper used by every node:

```python
def _log(state: dict, action: str, details: dict) -> list[dict]:
    entry = {
        "timestamp": datetime.now().isoformat(),
        "step": state.get("current_step", "unknown"),
        "action": action,
        "request_id": state.get("request_id", ""),
        **details,
    }
    return state.get("audit_log", []) + [entry]
```

It appends one structured entry per node execution and returns the full updated list. Because audit log is just a field in the state, it travels with the swap from start to finish with no external system required.

---

## The Edges — Where the Decisions Actually Live

This is the most important section. If nodes are the checklist items, edges are the logic between them. In LangGraph, an edge is a function that reads the current state and returns the name of the next node to run.

There are two kinds. **Linear edges** connect nodes that always run in sequence, no matter what. The core swap pipeline is entirely linear once the gate checks pass:

```python
graph.add_edge("block_old_sim", "provision_new_sim")
graph.add_edge("provision_new_sim", "reactivate_mpesa")
graph.add_edge("reactivate_mpesa", "activate_on_network")
graph.add_edge("activate_on_network", "send_confirmation_sms")
```

You cannot provision before blocking. You cannot activate before provisioning. The order is non-negotiable and the linear edges encode that directly.

**Conditional edges** are where the agentic behaviour actually comes from. There are three of them. Let's look at the one after identity verification:

```python
def route_after_identity(state: SimSwapState) -> str:
    if state.get("id_verification_status") == "passed":
        return "check_line_status"
    if state.get("id_verification_attempts", 0) >= state.get(
        "id_max_retries", config.MAX_IDENTITY_RETRIES
    ):
        return "reject_request"
    return "verify_identity"
```

Three possible outcomes. If KBA passed, move on to the line check. If it failed but retries remain, return `"verify_identity"` — the same node that just ran. If attempts are exhausted, send to `reject_request`. That last return value, routing a node back to itself, is the retry loop. A chatbot doesn't have this. It can't decide to revisit a step based on what just happened. This function is five lines and it's the difference between a pipeline and an agent.

The line check router is deliberately simpler:

```python
def route_after_line_check(state: SimSwapState) -> str:
    if state.get("line_check_passed"):
        return "capture_new_sim"
    return "reject_request"
```

Two outcomes, no retry. Fraud flags, suspended lines, and pending swaps all terminate immediately because none of those are recoverable through self-service. There's no loop here by design — the edge is encoding a business rule, not just a technical one.

The SIM validation router mirrors the identity one: pass, retry up to the limit, or reject.

```python
def route_after_sim_validation(state: SimSwapState) -> str:
    if state.get("sim_validation_status") == "valid":
        return "block_old_sim"
    if state.get("sim_validation_attempts", 0) >= state.get(
        "sim_max_retries", config.MAX_SIM_SERIAL_RETRIES
    ):
        return "reject_request"
    return "capture_new_sim"
```

The value of keeping routing logic in edges rather than nodes is this: you can unit test each router as a pure function of state. Pass it a dict with the relevant fields and assert on the returned string. You don't need to wire up the full graph, call any services, or manage async. And if a business rule changes — say the fraud policy becomes a soft warning rather than a hard stop — you update one function in `edges.py` and nothing else in the system needs to change.

---

## Wiring It All Together

The graph assembly lives in `builder.py`. It's a straightforward sequence: create the graph, register each node, connect them with edges, and compile:

```python
from langgraph.graph import StateGraph, END

def build_graph():
    graph = StateGraph(SimSwapState)

    # Register nodes
    graph.add_node("initiate_request", initiate_request)
    graph.add_node("verify_identity", verify_identity)
    graph.add_node("check_line_status", check_line_status)
    graph.add_node("capture_new_sim", capture_new_sim)
    graph.add_node("block_old_sim", block_old_sim)
    graph.add_node("provision_new_sim", provision_new_sim)
    graph.add_node("reactivate_mpesa", reactivate_mpesa)
    graph.add_node("activate_on_network", activate_on_network)
    graph.add_node("send_confirmation_sms", send_confirmation_sms)
    graph.add_node("reject_request", reject_request)

    # Entry point
    graph.set_entry_point("initiate_request")

    # Linear edge: entry flows into first gate
    graph.add_edge("initiate_request", "verify_identity")

    # Conditional routing at the three decision points
    graph.add_conditional_edges("verify_identity", route_after_identity, {
        "check_line_status": "check_line_status",
        "reject_request": "reject_request",
        "verify_identity": "verify_identity",   # the retry self-loop
    })
    graph.add_conditional_edges("check_line_status", route_after_line_check, {
        "capture_new_sim": "capture_new_sim",
        "reject_request": "reject_request",
    })
    graph.add_conditional_edges("capture_new_sim", route_after_sim_validation, {
        "block_old_sim": "block_old_sim",
        "capture_new_sim": "capture_new_sim",   # retry self-loop
        "reject_request": "reject_request",
    })

    # Linear pipeline: core swap
    graph.add_edge("block_old_sim", "provision_new_sim")
    graph.add_edge("provision_new_sim", "reactivate_mpesa")
    graph.add_edge("reactivate_mpesa", "activate_on_network")
    graph.add_edge("activate_on_network", "send_confirmation_sms")

    # Terminal nodes
    graph.add_edge("send_confirmation_sms", END)
    graph.add_edge("reject_request", END)

    return graph.compile()
```

One thing I like about LangGraph is that the compiled graph can export itself as a Mermaid diagram:

```python
def get_graph_mermaid() -> str:
    compiled = build_graph()
    return compiled.get_graph().draw_mermaid()
```

That diagram is generated from the same code that runs in production, which means it can never be out of date. If you change a routing rule, the diagram reflects it on the next export. For anyone who's ever maintained a "system architecture diagram" in a slide deck that was stale within a week of being drawn, that matters.

---

## Five Scenarios, Five Paths Through the Same Graph

The demo comes with five built-in scenarios, each using a different subscriber from the seed data. You run them like this:

```bash
python -m demo.cli happy_path
python -m demo.cli identity_retry
python -m demo.cli fraud_flag
python -m demo.cli bad_iccid
python -m demo.cli full_failure
```

Here's what each one exercises:

| Scenario | Subscriber | What actually happens |
|---|---|---|
| `happy_path` | Wanjiku Kamau (+254712345678) | All gates pass on the first attempt, full pipeline runs, swap completes |
| `identity_retry` | — | KBA fails once, the self-loop fires, passes on the second attempt |
| `fraud_flag` | Njoroge Mwangi (+254745678901) | Line check finds a fraud flag, `route_after_line_check` returns `reject_request` immediately |
| `bad_iccid` | — | SIM validation fails on the first attempt, retries, eventually rejects |
| `full_failure` | — | Identity verification exhausted after three attempts, process rejected |

The important thing to observe is that all five paths run through the same compiled graph. The agent doesn't have a separate code path for fraud versus normal flow. The fraud flag is a field in the state. The edge reads it. The routing follows. That's all there is to it.

A happy path run produces output that looks roughly like this:

```
Agent: Karibu Safaricom. I'm here to help you replace your SIM for a lost line.

Your request reference is SWP-3F8A21DC. I'll take you through the swap step by step.

Step 1: Let's first verify your identity.

Agent: Identity verified — you answered 3/4 questions correctly (minimum 3 required). Thank you!

Step 2: I'll now check the status of your line.

Agent: Line status confirmed.
- MSISDN: +254712345678
- Name: Wanjiku Kamau
- Status: Active
- Current SIM serial: 89254…5678
- M-PESA: Registered (balance Ksh 4,320.00)

Step 3: Please hand me the new SIM so I can capture its serial (ICCID) and IMSI.

...

Agent: Your new SIM is now LIVE on the Safaricom network — voice, SMS, data and USSD are all enabled.

SIM Swap Summary
| Request Ref       | SWP-3F8A21DC          |
| MSISDN            | +254712345678         |
| Old SIM           | 89254…1234 (Blocked)  |
| New SIM           | 89254…5678 (Active)   |
| M-PESA            | Restored (Ksh 4,320)  |
| Confirmation SMS  | Delivered             |

AUDIT LOG (9 entries)
  [2026-04-25T10:12:03] request_initiated
  [2026-04-25T10:12:04] identity_verification
  [2026-04-25T10:12:05] line_status_check
  [2026-04-25T10:12:06] sim_validation
  [2026-04-25T10:12:07] block_old_sim
  [2026-04-25T10:12:08] provision_new_sim
  [2026-04-25T10:12:09] mpesa_reactivate
  [2026-04-25T10:12:10] network_activation
  [2026-04-25T10:12:11] confirmation_sms

Final status: completed
```

Nine audit entries, one per node, each with a timestamp and a request ID. The full state at any point in that run can be checkpointed and replayed. That's not something you get out of a chatbot.

---

## What You Actually Have Now

If you run this locally, here's what you've built:

**The graph is the documentation.** The Mermaid export is generated from live code. The retry loops, the fraud halt, the M-PESA skip for unregistered lines — they're all visible in the diagram and they all come directly from the routing functions. Nobody has to keep a separate flowchart up to date.

**The state is the audit trail.** Every step appends one entry to `audit_log`. By the time the process reaches its terminal node, you have a complete, timestamped record of exactly what the agent did and why. That record lives in the same object as the result, no separate logging infrastructure required for the prototype.

**The edges are the policy.** If Safaricom changes the KBA requirement from three-out-of-four to four-out-of-four, that's a one-line change in `config.py`. If fraud policy changes from immediate termination to a human-escalation path, you update `route_after_line_check` and add a new node. The rest of the graph doesn't care.

---

## What's Still Missing

What you have here is a solid prototype. But there's a meaningful gap between prototype and production, and Part 3 is entirely about that gap.

We haven't connected this to anything external yet. There's a FastAPI wrapper that exposes the agent as an OpenAI-compatible endpoint so Open WebUI can talk to it, but I haven't walked through that here. We also haven't added observability — right now, if something fails mid-run, you'd need to dig through the state manually. And there's no human-in-the-loop interrupt, which means a human operator can't pause the flow and review it before the old SIM gets blocked. For a production SIM swap system, that last one is not optional.

Part 3 will cover all of it: the FastAPI service, hooking into LangSmith for tracing, and adding interrupt-based human review at the fraud flag step. The code will be extended in the same repo.

---

The full source code is available here: [github.com/wandabwa2004/safaricom_agentic_ai](https://github.com/wandabwa2004/safaricom_agentic_ai)

I hope this was useful. If you found it helpful, follow me, leave a comment, and let me know what you'd like to see in Part 3 — whether that's a specific LangGraph pattern, a deployment detail, or something else entirely. You can also find all my other articles on my profile and connect with me on LinkedIn. All my articles are free to read.

*See you in Part 3.*
