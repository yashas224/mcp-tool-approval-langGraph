#  node 1 - get the access token for user
# node 2 - construct the AGENT and invoke based on user Quer


from typing import TypedDict

from langchain_core.runnables import RunnableConfig

from graph.state import SubGraphState
from langgraph.graph import END, START, StateGraph
from nodes.github_token_validator_node import git_token_validator_node
from nodes.github_execution_node import github_execution_node
from nodes.github_token_interupt_node import github_token_interupt_node
from github_service import is_token_valid
from DB.token_storage import oauth_db, token_db


def auth_check(state: SubGraphState):
    if state["github_auth_token_validated"]:
        if state["github_auth_flow"]:
            return "github_auth_flow"
        return "authenticated"
    if state["auth_retry"] ==2:
        return "authenticated-failed"
    return "auth-retry"
def route_after_execution(state):
    return "pending_aproval" if state.get("github_approval_pending") else "task_complete"

def is_token_valid_condition(state: SubGraphState, config: RunnableConfig):
    user_id = config["configurable"]["thread_id"]
    if state["github_auth_token_validated"]:
        return "token-valid"
    else:
        return "invalid-token"
sub_graph_builder = StateGraph(SubGraphState)
sub_graph_builder.add_node("github_token_validator_node", git_token_validator_node)
sub_graph_builder.add_node("github_execution_node", github_execution_node)
sub_graph_builder.add_node("github_token_interupt_node",github_token_interupt_node)

sub_graph_builder.set_entry_point("github_token_validator_node")
sub_graph_builder.add_conditional_edges("github_token_validator_node",is_token_valid_condition,
                                  {"invalid-token":"github_token_interupt_node",
                                   "token-valid":"github_execution_node"})

sub_graph_builder.add_conditional_edges("github_token_interupt_node",auth_check,
                                        {   "github_auth_flow":END,
                                            "authenticated":"github_execution_node",
                                            "auth-retry":"github_token_interupt_node",
                                            "authenticated-failed":END
                                        })
sub_graph_builder.add_edge("github_execution_node",route_after_execution,{
"pending_aproval":"github_execution_node",
"task_complete":END
} )
github_sub_graph = sub_graph_builder.compile()


github_sub_graph.get_graph().draw_mermaid_png(output_file_path="github-subgraph.png")
