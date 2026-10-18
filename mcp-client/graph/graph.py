from graph.github_subgraph import github_sub_graph
from graph.state import MessagesState
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph
from nodes.approval_node import approval_node
from nodes.conversational_node import conversational_node
from nodes.sanity_node import agentGaurdNode
from nodes.tool_executor_node import create_tool_executor_node
from nodes.tool_selector_node import create_tool_selector_node


def build_graph(tools, tool_catalog):
    def tool_call_present(state: MessagesState):
        tool_exists = state["tool_call_exist"]
        if tool_exists:
            return "approval"
        else:
            return "no-tool-selected"

    def approved_tool_execution(state: MessagesState):
        if state["tool_approved"] == "approved":
            return "call-approved"
        else:
            return "call-rejected"

    def is_github_mcpserver_operation(state: MessagesState):
        if state["mcpServer"] == "github":
            return "github-op"
        else:
            return "non-github-op"

    def github_completion(state: MessagesState):
        if not state["github_auth_token_validated"]:
            return "github-auth-failed"
        elif not state["git_hub_session_completed"]:
            return "github-op-failed"
        elif state["github_auth_flow"]:
            return "github_auth_flow"
        
        return "github-op-cmpleted"

    checkpointer = InMemorySaver()
    agent_builder = (
        StateGraph(MessagesState)
        .add_node("agent_gaurd_node", agentGaurdNode)
        .add_node(
            "tool_selector_node", create_tool_selector_node(toolSchema=tool_catalog)
        )
        .add_node("approval_node", approval_node)
        .add_node("tool_executor_node", create_tool_executor_node(tools=tools))
        .add_node("conversational_node", conversational_node)
        .add_node("github-subgraph", github_sub_graph)
        .set_entry_point("agent_gaurd_node")
        .add_conditional_edges(
            "agent_gaurd_node",
            is_github_mcpserver_operation,
            {"github-op": "github-subgraph", "non-github-op": "tool_selector_node"},
        )
        .add_conditional_edges(
            "tool_selector_node",
            tool_call_present,
            {"approval": "approval_node", "no-tool-selected": "conversational_node"},
        )
        .add_conditional_edges("github-subgraph","conversational_node")
        .add_conditional_edges(
            "approval_node",
            approved_tool_execution,
            {
                "call-approved": "tool_executor_node",
                "call-rejected": "conversational_node",
            },
        )
        .add_edge("tool_executor_node", "tool_selector_node")
        .add_edge("conversational_node", END)
    )

    agent = agent_builder.compile(checkpointer=checkpointer)
    agent.get_graph().draw_mermaid_png(output_file_path="graph-image.png")

    return agent
