from dotenv import load_dotenv
from graph.state import MessagesState
from langchain.chat_models import init_chat_model
from langchain.messages import AnyMessage
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate


def get_model():
    policy = ""
    from pathlib import Path

    cwd = Path.cwd()
    with open(cwd / "policy" / "policy_file.txt", "r", encoding="utf-8") as f:
        policy = f.read()

    model = init_chat_model("gpt-5.5")

    prompt = """
    User Query:{user_query}
    User Query needs to be within the scope of the System Policy Stated Above
    \n
    Last 5 Conversation History :
    {history}
    \n
    Continue or end the conversation based on the user Query and the message hostory. Be polite. 
    """
    template = ChatPromptTemplate(
        [("system", f"System Policy:{policy}"), ("human", prompt)]
    )
    model_chain = template | model
    return model_chain


def conversational_node(state: MessagesState):
    model_chain = get_model()
    messages: list[AnyMessage] = state.get("messages", [])
    last_5_messages = messages[-10:]
    history = []
    for message in last_5_messages:
        history.append(f"{type(message).__name__} - {message.content}")

    result = model_chain.invoke(
        {"user_query": state["user_query"], "history": "\n".join(history)}
    )
    print(isinstance(result, AIMessage))
    print(f"conversational Node: {result}")
    return {"messages": [result]}
