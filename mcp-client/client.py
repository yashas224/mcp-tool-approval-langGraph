import json
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi import Request as FastAPIRequest
from fastapi.responses import RedirectResponse
from github_service import (
    REDIRECT_URI,
    SESSION_SECRET,
    build_github_authorization_url,
    exchange_code,
    get_github_user,
)
from graph.graph import build_graph
from langchain.mcp import MCPAdapter
from langchain.tools import BaseTool
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from DB.token_storage import oauth_db, token_db
from DB.checkpoint import github_checkpointer, checkpointer
from util import generate_pkce

load_dotenv()


class Request(BaseModel):
    user_id: str
    query: str | None = None
    user_message: str | None = None


def get_tool_catalog(tools: list[BaseTool]) -> list[dict]:
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "schema": tool.args_schema,
        }
        for tool in tools
    ]


def github_result(state: dict) -> str | None:
    if state.get("mcpServer") != "github":
        return None
    if not state.get("github_auth_token_validated"):
        return "GitHub authorization failed. Authorize GitHub again and retry your request."
    if state.get("github_auth_flow"):
        return "GitHub authorization succeeded. Rerun your GitHub query."
    if not state.get("git_hub_session_completed"):
        return "The GitHub request could not be completed. Please try again."
    answer = state.get("github_answer")
    return answer.content if answer else "GitHub request completed."


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
    return {
        "result": github_result(state) or state["messages"][-1].content,
        "status": "completed",
    }


@app.post("/resume")
async def chatR(req: Request):
    config: RunnableConfig = {
        "configurable": {
            "thread_id": req.user_id,
        }
    }
    state = await app.state.agent.ainvoke(Command(resume={"action": req.query,"user_message":req.user_message}), config)
    interrupts = state.get("__interrupt__", [])

    if interrupts:
        interrupt = interrupts[0]

        return {
            "status": "interrupt",
            "thread_id": req.user_id,
            "interrupt": interrupt.value,
        }

    return {
        "result": github_result(state) or state["messages"][-1].content,
        "status": "completed",
    }


@app.get("/github-auth")
def githubAuth(request: FastAPIRequest, user_id: str):
    verifier, challenge = generate_pkce()
    oauth_state = secrets.token_urlsafe(32)
    oauth_transactions = {"code_verifier": verifier, "user_id": user_id}
    oauth_db[oauth_state] = oauth_transactions
    request.session["oauth"]= {
        "state":oauth_state,
        "oauth_transactions":oauth_transactions


    }
    authorization_url = build_github_authorization_url(
        state=oauth_state,
        code_challenge=challenge,
    )

    return   RedirectResponse(
                authorization_url,
        status_code=302,

    )


@app.get("/callback/")
async def gitHubCallBack(request: FastAPIRequest, code: str = None, state: str = None):
    try:
        error = request.query_params.get("error")

        if error == "access_denied":
            return {
                "result": "Authorization cancelled, You declined GitHub authorization ",
                "status": "completed",
            }

        if not code or not state:
            raise HTTPException(status_code=400, detail="Missing OAuth parameters")

        retrived_state = request.session.pop("oauth", None)
        if not retrived_state or not secrets.compare_digest(
            retrived_state["state"], state
        ):
            raise HTTPException(status_code=400, detail="Missing State")

        verifier = retrived_state.get("oauth_transactions").get("code_verifier", None)
        user_id = retrived_state.get("oauth_transactions").get("user_id", None)

        if not verifier:
            raise HTTPException(status_code=400, detail="Missing PKCE verifier")

        token = exchange_code(code, verifier, user_id)

        config: RunnableConfig = {
            "configurable": {
                "thread_id": user_id,
            }
        }

        if token and token.strip():
            token_db[user_id] = token
            response = await app.state.agent.ainvoke(
                Command(resume={"action": "auth-Complete"}), config
            )
            return RedirectResponse(
                f"http://127.0.0.1:8501/?github_auth=complete&user_id={user_id}",
                status_code=303,
            )
        else:
            response = await app.state.agent.ainvoke(
                Command(resume={"action": "auth-Failed"}), config
            )
            return RedirectResponse(
                f"http://127.0.0.1:8501/?github_auth=failed&user_id={user_id}",
                status_code=303,
            )
    except Exception:
        # user_id may not be known yet (e.g. state mismatch), so leave it out
        return RedirectResponse(
            "http://127.0.0.1:8501/?github_auth=failed",
            status_code=303,
        )


def getGitHubUser(user_id: str):
    token = token_db.get(user_id, None)
    if token:
        userJson = get_github_user(token=token)
        return userJson
    else:
        return None


@app.get("/conversation/latest")
async def latest_messages(
    user_id: str, userJson: Annotated[dict, Depends(getGitHubUser)]
):
    
    config = {"configurable": {"thread_id": user_id}}
    snapshot = await app.state.agent.aget_state(config)
    github_query = snapshot.values.get("user_query", "")
    auth_result = (
        f"Successfully authorized : GitHub Account:  {userJson["name"]}, {userJson["login"]}"
        if userJson
        else "Authorization Failed"
    )

    return {
        "result": auth_result,
        "github_query": github_query,
        "install_url": os.getenv("github_app_install_url") if userJson else None,
    }


@app.delete("/delete-checkpoint")
def deleteCheckpoint(user_id: str):
    github_checkpointer.delete_thread(user_id)
    checkpointer.delete_thread(user_id)

    return {
        "result": "Cleared Agent context",
    }
