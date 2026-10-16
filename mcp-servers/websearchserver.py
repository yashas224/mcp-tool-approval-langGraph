from typing import Any

from dotenv import load_dotenv
from fastmcp import FastMCP
from langchain_tavily import TavilySearch

mcp = FastMCP("WebSearchMCPServerRemote")
load_dotenv()


@mcp.tool(name="tavilyWebSearch")
def webSearch(query: str) -> Any:
    """
    Gets the Web Search results by invokin tavily API
    """
    tool = TavilySearch(max_results=1, topic="general")

    respponse = tool.invoke({"query": query})
    return respponse


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8002)
