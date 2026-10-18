from fastmcp import Client
from fastmcp.client.auth import BearerAuth
from graph.state import SubGraphState
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.mcp import MCPAdapter
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, interrupt
from langgraph.checkpoint.memory import InMemorySaver

from DB.token_storage import oauth_db, token_db

GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/"
github_checkpointer = InMemorySaver()       # module level, shared across requests


async def github_execution_node(state: SubGraphState, config: RunnableConfig):
    user_id = config["configurable"]["thread_id"]
    state["user_id"]=user_id
    

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
            checkpointer=github_checkpointer
        )
        config = {"configurable": {"thread_id": user_id}}

        response = await agent.ainvoke(
            {"messages": state["github_messages"]}, config=config
        )
        print(response)
        if "__interrupt__" in response:
            decision = interrupt(response["__interrupt__"][0].value)
            if decision.get("action")== "approved":
                final_decission= {
                    "decisions": [
                        {
                            "type": "approve",
                        }
                    ]
                }
            else:
                final_decission= {
                    "decisions": [
                        {
                            "type": "reject",
                            "message": "User rejected this action. Do not retry this tool call.",
                        }
                    ]
                }

            result = await agent.ainvoke(Command(resume=final_decission), config)
            return {"messages": result["messages"],
                    "github_answer": result["messages"][-1],
                    "git_hub_session_completed":True
                    }