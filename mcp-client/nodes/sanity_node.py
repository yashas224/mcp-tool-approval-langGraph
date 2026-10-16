from typing import Literal

from dotenv import load_dotenv
from graph.state import MessagesState
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

load_dotenv()


class Rating(BaseModel):
    """Rating of the user query."""

    rating: str = Field(description="The User query rating out of 10")
    mcpServer: Literal["github", "non-github"] = Field(
        description="MCP server that can be used to server the request"
    )


policy = ""
from pathlib import Path

cwd = Path.cwd()
with open(cwd / "policy" / "policy_file.txt", "r", encoding="utf-8") as f:
    policy = f.read()

model = init_chat_model("gpt-5.5")
model = model.with_structured_output(Rating)
prompt = """
    User Query:{user_query}
    User Query needs to be within the scope of the System Policy Stated Above

    Rate the User Query from 1 to 10 based on how  close is it to the defined System Policy
    """
template = ChatPromptTemplate(
    [("system", f"System Policy:{policy}"), ("system", prompt)]
)
model_chain = template | model


def agentGaurdNode(state: MessagesState):
    rating: Rating = model_chain.invoke({"user_query": state["user_query"]})
    return {"query_rating": rating.rating, "mcpServer": rating.mcpServer}
