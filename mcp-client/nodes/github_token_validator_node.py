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
    isValid= is_token_valid(token_db.get(user_id,None))
    return {
        "git_hub_session_completed":False,
        "github_auth_token_validated":isValid,
        "auth_retry":0
    }

            
            


        





