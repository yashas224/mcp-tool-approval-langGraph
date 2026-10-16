from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from graph.state import SubGraphState
from DB.token_storage import oauth_db,token_db
from langgraph.types import interrupt

from fastmcp import Client
from fastmcp.client.auth import BearerAuth
GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/"
async def git_hub_node(state: SubGraphState,config: RunnableConfig):
    user_id = config["configurable"]["thread_id"]
    access_token=token_db.get(user_id)
    if not access_token:
        approved = interrupt( {
                    "MCP Server": "GitHub",
                    "message": "GitHub authorization required",
                })

        if approved["action"] == "auth-failed":
            return {"messages": [HumanMessage(content="Git Hub Authorization Failed")]}
        access_token=token_db.get(user_id)


    print(f"Access Token {access_token}")
    async with Client(
        GITHUB_MCP_URL, 
        auth=BearerAuth(token=access_token),
    ) as client:
        tools= await client.list_tools()
        print(f"Tools {tools}")
        


    #  build MCP client
    # build Langchain Agent
    # invoke agent with user_query
        

