from contextlib import asynccontextmanager
from pathlib import Path
import secrets
from typing import Annotated
from fastapi.responses import RedirectResponse
from langchain_core.messages import AIMessage, HumanMessage
from starlette.middleware.sessions import SessionMiddleware


from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, Request as FastAPIRequest
from graph.graph import build_graph
from langchain.mcp import MCPAdapter
from langchain.tools import BaseTool
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from pydantic import BaseModel
from util import generate_pkce
from github_service import (
    REDIRECT_URI,
    SESSION_SECRET,
    build_github_authorization_url,
    exchange_code,
)
from DB.token_storage import oauth_db,token_db
load_dotenv()

class Request(BaseModel):
    user_id: str
    query: str | None = None


def get_tool_catalog(tools: list[BaseTool]) -> list[dict]:
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "schema": tool.args_schema,
        }
        for tool in tools
    ]


@asynccontextmanager
async def InitMCPServerTools(app: FastAPI):
    # Load the tools from MCP Servers model
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    config = {
        "mcpServers": {
            "math": {
                "command": "uv",
                "args": [
                    "run",
                    "--directory",
                    str(PROJECT_ROOT),
                    "python",
                    "mcp-servers/mathserver.py",
                ],
            },
            "web_search": {"url": "http://localhost:8002/mcp"},
        }
    }
    async with MCPAdapter(config) as adapter:
        app.state.tools = await adapter.list_tools()
        app.state.tool_catalog = get_tool_catalog(app.state.tools)
        app.state.agent = build_graph(app.state.tools, app.state.tool_catalog)

        yield


app = FastAPI(lifespan=InitMCPServerTools)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=False,  # Set True when using HTTPS in production
)


@app.post("/get-tools")
async def getTools():
    return [tool.name for tool in app.state.tools]


@app.post("/chat")
async def chat(req: Request):
    config: RunnableConfig = {
        "configurable": {
            "thread_id": req.user_id,
        }
    }
    state = await app.state.agent.ainvoke(
        {"messages": [req.query], "user_query": req.query or ""}, config
    )

    interrupts = state.get("__interrupt__", [])

    # print(interrupts)
    # [Interrupt(value={'tool_name': 'math_add_tool', 'tool_args': {'a': 2, 'b': 2}, 'message': 'Approve or reject this tool call.'}, id='2765923a41f772e77405a1397c591167')]

    if interrupts:
        interrupt = interrupts[0]

        return {
            "status": "interrupt",
            "thread_id": req.user_id,
            "interrupt": interrupt.value,
        }
    return {"result": state["messages"][-1].content, "status": "completed"}


@app.post("/resume")
async def chatR(req: Request):
    config: RunnableConfig = {
        "configurable": {
            "thread_id": req.user_id,
        }
    }
    state = await app.state.agent.ainvoke(Command(resume={"action": req.query}), config)
    interrupts = state.get("__interrupt__", [])

    if interrupts:
        interrupt = interrupts[0]

        return {
            "status": "interrupt",
            "thread_id": req.user_id,
            "interrupt": interrupt.value,
        }

    return {"result": state["messages"][-1].content, "status": "completed"}


@app.get("/github-auth")
def githubAuth(request: FastAPIRequest, user_id: Annotated[str | None, Header()]):
    verifier, challenge = generate_pkce()
    oauth_state = secrets.token_urlsafe(32)
    oauth_transactions={
        "code_verifier":verifier,
        "user_id":user_id
    }
    oauth_db[oauth_state]=oauth_transactions
    
    authorization_url = build_github_authorization_url(
        state=oauth_state,
        code_challenge=challenge,
    )

    return {"authorization_url":authorization_url}


@app.get("/callback/")
async def gitHubCallBack(request: FastAPIRequest , code: str = None, state: str = None):
    try:
        error = request.query_params.get("error")

        if error == "access_denied":
            return {"result": "Authorization cancelled, You declined GitHub authorization ", "status": "completed"}   


        if not code or not state :
            raise HTTPException(status_code=400, detail="Missing OAuth parameters")


        retrived_state = oauth_db.pop(state,None)
        if not retrived_state:
            raise HTTPException(status_code=400, detail="Missing State")

        verifier = retrived_state.get("code_verifier",None)
        user_id = retrived_state.get("user_id",None)

        if not verifier:
            raise HTTPException(status_code=400, detail="Missing PKCE verifier")

        token = exchange_code(code, verifier,user_id)


        config: RunnableConfig = {
            "configurable": {
                "thread_id": user_id,
            }
        }

        if  token and  token.strip():
            token_db[user_id]=token
            response = await app.state.agent.ainvoke(Command(resume={"action": "auth-Complete"}), config)
            return RedirectResponse(
            f"http://127.0.0.1:8501/?github_auth=complete&user_id={user_id}",
            status_code=303,
            )        
        else:
            response = await app.state.agent.ainvoke(Command(resume={"action": "auth-Failed"}), config)
            return RedirectResponse(
            f"http://127.0.0.1:8501/?github_auth=failed&user_id={user_id}",
            status_code=303,
            )
    except:
        return {"result": "GitHub Auth Failed", "status": "completed"}   


@app.get("/conversation/latest")
async def latest_messages(user_id: str):
    config = {"configurable": {"thread_id": user_id}}
    snapshot = await app.state.agent.aget_state(config)
    messages = snapshot.values.get("messages", [])
    latest_human = next(
        (message.content for message in reversed(messages) if isinstance(message,HumanMessage)),
        None,
    )
    latest_ai = next(
        (message.content for message in reversed(messages) if isinstance(message,AIMessage)),
        None,
    )

    return {
        "latest_human": latest_human,
        "latest_ai": latest_ai,
    }






