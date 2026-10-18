#  node 1 - get the access token for user
# node 2 - construct the AGENT and invoke based on user Quer


from typing import TypedDict

from graph.state import SubGraphState
from langgraph.graph import END, StateGraph
from nodes.github_token_validator_node import git_token_validator_node
from nodes.github_execution_node import github_execution_node

def auth_check(state: SubGraphState):
    if state["github_auth_token_validated"]:
        if state["github_auth_flow"]:
            return "github_auth_flow"
        return "authenticated"
    if state["auth_retry"] ==2:
        state["auth_retry"] =1
        return "authenticated-failed"
    state["auth_retry"] +=1
    return "auth-retry"
sub_graph_builder = StateGraph(SubGraphState)
sub_graph_builder.add_node("github_token_validator_node", git_token_validator_node)
sub_graph_builder.add_node("github_execution_node", github_execution_node)

sub_graph_builder.set_entry_point("github_token_validator_node")
sub_graph_builder.add_conditional_edges("github_token_validator_node",auth_check,
                                        {   "github_auth_flow":END,
                                            "authenticated":"github_execution_node",
                                            "auth-retry":"github_token_validator_node",
                                            "authenticated-failed":END
                                        })
sub_graph_builder.add_edge("github_execution_node", END)
github_sub_graph = sub_graph_builder.compile()
