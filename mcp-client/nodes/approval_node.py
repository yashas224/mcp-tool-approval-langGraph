from graph.state import MessagesState
from langchain_core.messages import HumanMessage
from langgraph.types import interrupt


def approval_node(state: MessagesState):
    tool_selected = state["tool_selected"]
    tool_args = state["tool_args"]
    total_tools = state.get("total_tools", 0)
    approved = interrupt(
        {
            "tool_name": tool_selected,
            "tool_args": tool_args,
            "message": "Approve or reject this tool call.",
        }
    )

    if approved.get("action") == "approved":
        return {
            "tool_approved": "approved",
            "total_tools": total_tools + 1,
            "messages": [HumanMessage(content=f"Tool {tool_selected} usage approved")],
        }
    else:
        return {
            "tool_approved": "not-approved",
            "result": "The requested tool call was rejected.",
            "messages": [HumanMessage(content=f"Tool {tool_selected} usage Rejected")],
        }
