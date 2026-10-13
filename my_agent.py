"""AskIT — Federal Agency IT Support Assistant
Built with Strands Agents SDK, deployed to AgentCore Runtime.
"""
import os
from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.tools.mcp import MCPClient
from strands_tools import retrieve
from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
from askit_hooks import RequireRetrievalHook

# --- Initialize the AgentCore application ---
app = BedrockAgentCoreApp()

# --- Configure the foundation model with guardrail ---
model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-6",
    guardrail_id="p1fiz8mn88d6",
    guardrail_version="1"
)

# --- Connect the retrieve tool to the Knowledge Base ---
os.environ["KNOWLEDGE_BASE_ID"] = "QHUD2ZYPZM"
os.environ["AWS_REGION"] = "us-east-1"

# --- Connect to AgentCore Gateway for helpdesk tools (CreateTicket, GetTicketStatus) ---
GATEWAY_URL = "https://askit-gateway-lvyral13tr.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
gateway_mcp = MCPClient(
    lambda: aws_iam_streamablehttp_client(
        endpoint=GATEWAY_URL,
        aws_region=AWS_REGION,
        aws_service="bedrock-agentcore"
    )
)

# --- System prompt ---
SYSTEM_PROMPT = """You are AskIT, a federal agency IT support assistant. Your role is to help federal employees with technology-related questions and issues.

You can:
1. Answer questions about IT policies (acceptable use, VPN access, MFA setup, password requirements, software approval processes)
2. Provide step-by-step troubleshooting for common IT issues
3. Tell users who to contact for specific issues (help desk tiers, system owners, security team)
4. Create help desk tickets on behalf of users
5. Check the status of existing help desk tickets

Guidelines:
- Always be professional, clear, and concise
- Reference specific policy documents when answering policy questions
- ALWAYS use the retrieve tool to search the Knowledge Base before answering any policy-related question. Do not answer policy questions from general knowledge alone.
- For troubleshooting, provide numbered step-by-step instructions
- When creating tickets, create them immediately using the information provided. Infer priority from context (e.g., cannot work = high). Do not ask follow-up questions before creating the ticket.
- If you cannot resolve an issue, offer to create a help desk ticket
- Never provide information outside of IT support topics
- Never provide legal advice, financial advice, budget recommendations, or HR/personnel guidance
- Protect all personally identifiable information (PII)
"""

# --- Create the agent ---
# Tools: retrieve (Knowledge Base), gateway_mcp (CreateTicket, GetTicketStatus via MCP)
# Hooks: RequireRetrievalHook enforces "retrieve before answering a policy question" in code
agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[retrieve, gateway_mcp],
    hooks=[RequireRetrievalHook()]
)

# --- AgentCore Runtime entrypoint ---
@app.entrypoint
def invoke(payload):
    """Handle incoming requests from AgentCore Gateway / Chat UI."""
    user_message = payload.get("prompt", "Hello!")
    result = agent(user_message)
    return {"result": result.message}


if __name__ == "__main__":
    app.run()
