from graph.state import MessagesState
from langchain.agents import create_agent
from pydantic import BaseModel, Field


class ToolProposal(BaseModel):
    tool_selected: str | None = Field(
        default=None,
        description="The selected tool name, or null when no tool is needed.",
    )
    tool_args: dict = Field(
        default_factory=dict, description="Arguments for the selected tool."
    )
    tool_call_exist: bool = Field(description="true  when there is a tool call present")


def create_tool_selector_node(toolSchema):
    system_prompt = f"""
    You select, but never execute, MCP tools.

    Available tools:
    {toolSchema}

    For each user request:
    - Only select the tool name that can be used to answer the question
    - select exactly one available tool only when it is needed.
    - Set tool_args to an object that satisfies that tool's input schema.
    - If no tool is needed, set tool_call_exist false.
    - Never invent a tool name.
    - If unknown queries come use  Web search to understand more.
    """
    agent = create_agent(
        model="openai:gpt-5.5",
        response_format=ToolProposal,
        system_prompt=system_prompt,
    )

    def tool_selector_node(state: MessagesState):
        existing_messages = state["messages"]
        result = agent.invoke({"messages": existing_messages})
        toolProposal: ToolProposal = result["structured_response"]
        return {
            "messages": result["messages"][len(existing_messages) :],
            "tool_selected": toolProposal.tool_selected,
            "tool_args": toolProposal.tool_args,
            "tool_call_exist": toolProposal.tool_call_exist,
            "tool_approved": "pending",
        }

    return tool_selector_node
