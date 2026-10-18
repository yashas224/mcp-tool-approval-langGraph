#  node 1 - get the access token for user
# node 2 - construct the AGENT and invoke based on user Quer


from typing import TypedDict

from graph.state import SubGraphState
from langgraph.graph import END, StateGraph
from nodes.github_node import git_hub_node

sub_graph_builder = StateGraph(SubGraphState)
sub_graph_builder.add_node("github_node", git_hub_node)
sub_graph_builder.set_entry_point("github_node")
sub_graph_builder.add_edge("github_node", END)
github_sub_graph = sub_graph_builder.compile()
