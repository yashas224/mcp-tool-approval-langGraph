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
from github_service import is_token_valid


def git_token_validator_node(state: SubGraphState, config: RunnableConfig):
    user_id = config["configurable"]["thread_id"]
    access_token = token_db.get(user_id)
    state["github_auth_token_validated"]=False
    state["git_hub_session_completed"]=False
    state["github_messages"]= HumanMessage(content=state["user_query"])

    if is_token_valid(token=access_token):
        state["github_auth_flow"]=False
        return {"github_auth_token_validated": True}
    else:
        state["github_auth_flow"]=True
        approved = interrupt(
            {
                "MCP Server": "GitHub",
                "message": "GitHub authorization required",
            }
        )
        if approved["action"] == "auth-failed":
            return {"github_auth_token_validated": False}
        return {"github_auth_token_validated": True}
            
            


        





