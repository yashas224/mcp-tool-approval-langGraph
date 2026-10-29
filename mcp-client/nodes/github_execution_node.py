import json

from fastmcp import Client
from fastmcp.client.auth import BearerAuth
from graph.state import SubGraphState
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.mcp import MCPAdapter
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, interrupt
from DB.checkpoint import github_checkpointer
from DB.token_storage import oauth_db, token_db

GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/"


def _form_content(user_reply: str, schema: dict) -> dict:
    # A JSON object reply is used as is, e.g. {"date": "2026-09-14"}
    try:
        parsed = json.loads(user_reply)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    # Plain text reply goes into the first field the server asked for
    fields = list(schema.get("properties", {}))
    return {fields[0]: user_reply} if fields else {}

async def github_execution_node(state: SubGraphState, config: RunnableConfig):
    user_id = config["configurable"]["thread_id"]
    state["user_id"] = user_id

    access_token = token_db.get(user_id)
    async with MCPAdapter(
        Client(GITHUB_MCP_URL, auth=BearerAuth(token=access_token)),
    ) as client:
        tools = await client.list_tools()
        agent = create_agent(
            model="openai:gpt-5.5",
            tools=tools,
            middleware=[
                HumanInTheLoopMiddleware(
                    interrupt_on={tool.name: True for tool in tools}
                )
            ],
            checkpointer=github_checkpointer,
            system_prompt="You are an github MCP assistant that only selects and invokes tools linked"
        )
        config = {"configurable": {"thread_id": user_id}}

        github_agent_state = await agent.aget_state(config)
        if github_agent_state.next:
            # when intrupt , next != empty
            pending = next(
                (i.value for t in github_agent_state.tasks for i in t.interrupts), None
            )
        else:
            # Empty () means the graph is complete. Its a new run for the agent
            response = await agent.ainvoke(
                {"messages": state["messages"]}, config=config
            )
            if "__interrupt__" not in response:
                return {
                    "messages": response["messages"],
                    "github_answer": response["messages"][-1],
                    "git_hub_session_completed": True,
                }
            pending = response["__interrupt__"][0].value

        decision = interrupt(pending)
        result={}

        if "action_requests" in pending:
        #  Langchain Agent HITL request
            action_count = len(pending["action_requests"])
            if decision.get("action") == "approved":
                decisions = [{"type": "approve"} for _ in range(action_count)]
            else:
                decisions = [
                    {
                        "type": "reject",
                        "message": "You rejected this action. Do not retry this tool call.",
                    }
                    for _ in range(action_count)
                ]
            final_decission = {"decisions": decisions}
            result = await agent.ainvoke(Command(resume=final_decission), config)
        elif pending.get("type") == "mcp_elicitation":
            # MCP server asked for input mid tool call; the user's reply is in decision["action"]
            user_reply = str(decision.get("action", "")).strip()
            responses = {}
            for req in pending["requests"]:
                if user_reply.lower() in ("decline", "cancel"):
                    responses[req["key"]] = {"action": user_reply.lower()}
                elif req["mode"] == "url":
                    # User visited the URL, nothing to send back
                    responses[req["key"]] = {"action": "accept"}
                else:
                    responses[req["key"]] = {
                        "action": "accept",
                        "content": _form_content(decision["user_message"], req["requested_schema"]),
                    }
            # Answers are keyed by the server's own request key
            final_decission = {"responses": responses}
            result=await agent.ainvoke(
            Command(resume=final_decission), config
            )

        is_interrupt = False
        if "__interrupt__" in result:
            is_interrupt = True
            return {"git_hub_approval_pending": is_interrupt}
        return {
            "messages": result["messages"],
            "github_answer": result["messages"][-1],
            "git_hub_session_completed": True,
            "git_hub_approval_pending": is_interrupt,
        }
