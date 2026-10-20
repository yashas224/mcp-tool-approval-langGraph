import operator
from typing import Annotated, TypedDict

from langchain.messages import AnyMessage
from langgraph.graph.message import add_messages


class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    user_query: str
    result: str
    query_rating: int
    mcpServer: str
    github_answer: AnyMessage

    tool_selected: str
    tool_call_exist: bool
    tool_args: dict
    total_tools: int
    tool_approved: str

    github_auth_flow: bool
    github_auth_token_validated: bool
    git_hub_session_completed: bool
    github_messages: Annotated[list[AnyMessage], add_messages]


class SubGraphState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    github_auth_flow: bool
    github_messages: Annotated[list[AnyMessage], add_messages]
    user_query: str
    github_answer: AnyMessage
    git_hub_session_completed: bool
    user_id: str
    github_auth_token_validated: bool
    auth_retry: int
    git_hub_approval_pending: bool
