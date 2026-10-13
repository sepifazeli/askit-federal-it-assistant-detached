# AskIT — Federal Agency IT Support Assistant

A federal IT help-desk assistant built during an AWS Workshop Studio session
("Go Deeper: Build Your Own Guardrail"), using the **Strands Agents SDK**,
**Amazon Bedrock**, and **AgentCore**.

AskIT answers IT policy questions, walks users through troubleshooting, and can
create or check the status of help-desk tickets, all while staying inside a
custom four-layer guardrail that blocks the agent from drifting into legal,
budget, or HR territory it isn't scoped to handle.

## Architecture

- **Model:** Claude (via Amazon Bedrock `BedrockModel`), with a Bedrock
  Guardrail (`AskIT-Guardrail`) attached directly to the model config so every
  input and output passes through it.
- **Knowledge retrieval:** a Bedrock Knowledge Base holding IT policy documents
  (acceptable use, VPN access, MFA setup, password requirements, software
  approval), queried through the `retrieve` tool. The system prompt forces the
  agent to search the Knowledge Base before answering any policy question
  rather than answering from general knowledge.
- **Ticketing tools:** an **AgentCore Gateway** exposes two MCP tools,
  `CreateTicket` and `GetTicketStatus`, which the agent calls to create tickets
  immediately (inferring priority from context) or check on existing ones.
- **Deployment:** packaged and deployed to **AgentCore Runtime** via the
  `agentcore` CLI.

See [`my_agent.py`](./my_agent.py) for the full implementation.

## Guardrail design

Full write-up in [`docs/GUARDRAIL.md`](./docs/GUARDRAIL.md): four layers
covering content filtering, three denied topics (legal advice, budget/
procurement, HR/personnel), word filtering, and PII masking, plus the specific
test cases used to validate each layer actually fires.

## Enforcing retrieval in code

The system prompt tells the agent to search the Knowledge Base before answering a
policy question, but a prompt is an instruction, not a guarantee.
[`askit_hooks.py`](./askit_hooks.py) adds `RequireRetrievalHook`, a Strands hook that
enforces it:

1. It notes whether the user's message looks like a policy question (VPN, MFA,
   passwords, acceptable use, software approval, ...) and whether the `retrieve` tool
   ran successfully during the turn.
2. If a policy question is about to be answered without a successful `retrieve` call,
   it discards that answer (`AfterInvocationEvent.resume`) and tells the agent to
   retrieve first.
3. After two failed attempts it returns a fixed fallback offering a help desk ticket,
   instead of an answer from general knowledge.

Turns that already called another tool (e.g. `CreateTicket`) are not forced to
retrieve, so a ticket is never created twice. The policy check is a keyword heuristic
on the new user message only, so a follow-up that names no policy topic still relies on
the prompt. Needs `strands-agents>=1.30.0` for `AfterInvocationEvent.resume`.

```bash
pip install -r requirements-dev.txt
pytest
```

## What's in this repo, and what isn't

This was built in a temporary AWS Workshop Studio sandbox that auto-cleans up
at the end of the session. I saved what I could before it expired:

| File | Status |
|---|---|
| `my_agent.py` | Complete |
| `requirements.txt` | Complete |
| `docs/guardrail-config.partial.json` | Partial — the full `aws bedrock get-guardrail` export was cut off mid-copy before the sandbox closed. The complete configuration is documented by hand in `docs/GUARDRAIL.md`. |
| `.bedrock_agentcore.yaml` (AgentCore deployment config) | Not preserved — wasn't saved before the sandbox expired. |

I'm keeping this here as-is, gaps included, rather than reconstructing files to
look more complete than what actually survived the session.

## Validated behavior

During the workshop, I tested and confirmed:
- Policy Q&A correctly pulling from the Knowledge Base
- Ticket creation and status lookup through the Gateway MCP tools
- The denied-topics guardrail blocking a legal-advice request and a budget
  question
- PII masking on a message containing a fake SSN and email
- The custom word filter blocking a test "classified" topic
- Prompt-attack detection blocking an injection attempt

## Background

Built during AWS Workshop Studio's "Go Deeper: Build Your Own Guardrail"
session, which also covered AgentCore Identity, Observability, Code
Interpreter, and Browser at a higher level.
