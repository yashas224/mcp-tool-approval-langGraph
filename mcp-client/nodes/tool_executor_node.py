from graph.state import MessagesState
from langchain_core.messages import AIMessage


def create_tool_executor_node(tools):
    all_tools = tools

    async def tool_executor_node(state: MessagesState):
        tool_selected = state["tool_selected"]
        tool_args = state["tool_args"]
        tool = [tool for tool in all_tools if tool.name == tool_selected]
        if not tool:
            answer = f"No suitable tool found: {tool_selected}"
        else:
            tool_result = await tool[0].ainvoke(tool_args)
            answer = str(tool_result)

        return {
            "messages": [AIMessage(content=f"Tool {tool_selected} result: {answer}")],
            "result": answer,
        }

    return tool_executor_node
