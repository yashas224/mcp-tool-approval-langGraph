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


def github_token_interupt_node(state: SubGraphState):
    approved = interrupt(
            {
                "MCP Server": "GitHub",
                "message": "GitHub authorization required",
            }
        )
    if approved["action"] == "auth-Failed":
        return {
                    "github_auth_flow":True,
                    "auth_retry" :state.get("auth_retry",0)+1,
                    }
    else:
        return {"github_auth_token_validated":True,
                "github_auth_flow":True,
                "github_messages":HumanMessage(content=state["user_query"]),
                "auth_retry":0}
            
            


        





