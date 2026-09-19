# AskIT-Guardrail — Configuration Overview

AskIT is protected by a custom four-layer Amazon Bedrock Guardrail (`AskIT-Guardrail`,
ID `p1fiz8mn88d6`), applied to every request and response the agent handles.

> **Note on the JSON export:** the full configuration was pulled from AWS via
> `aws bedrock get-guardrail` during a time-limited AWS Workshop Studio sandbox.
> The copy of that output was cut short before the sandbox expired, so
> [`guardrail-config.partial.json`](./guardrail-config.partial.json) contains only
> the first two policy blocks as actually exported. The full four-layer design is
> documented below from the original build notes.

## Layer 1 — Content filters

Standard Bedrock content filtering across 5 harm categories, plus prompt-attack
detection, applied to both input and output.

## Layer 2 — Denied topics (3)

| Topic | What it blocks |
|---|---|
| Legal Advice | Legal opinions, guidance on legal proceedings, lawsuits, union grievances |
| Budget and Procurement | Budget recommendations, procurement guidance, spending decisions |
| HR / Personnel | Personnel guidance, HR case handling, employment decisions |

Each topic blocks both the triggering input and any model output that drifts into
the topic, so the agent can't be redirected into giving advice outside its scope
even if a user rephrases the request.

## Layer 3 — Word filters

- Profanity filtering (built-in Bedrock word list)
- Custom restricted terms specific to the AskIT use case (e.g. a blocked
  "classified" topic filter, validated in testing)

## Layer 4 — PII protection (3 entity types)

| Entity | Action |
|---|---|
| SSN | Masked |
| Email address | Masked |
| AWS access key | Blocked outright (not just masked) |

## Validation performed

During the workshop, each layer was exercised with a real test case to confirm it
actually fired as configured:

- Knowledge Base retrieval answering real IT policy questions
- Ticket creation and status lookup via the AgentCore Gateway MCP tools
- Denied-topics guardrail correctly blocking a legal-advice request and a
  budget question
- PII masking confirmed on a message containing a fake SSN/email
- Custom word filter blocking the "classified" test topic
- Prompt-attack pattern correctly blocked
