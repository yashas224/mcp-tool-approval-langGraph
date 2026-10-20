from fastmcp import Client
from fastmcp.client.auth import BearerAuth
from graph.state import SubGraphState
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.mcp import MCPAdapter
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, interrupt

from DB.token_storage import oauth_db, token_db

GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/"
github_checkpointer = InMemorySaver()  # module level, shared across requests


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
