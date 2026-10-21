from importlib.metadata import version

from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import HumanMessage, AIMessage

print("langgraph", version("langgraph"))

class S(TypedDict):
    messages: Annotated[list, add_messages]
    x: str

g = StateGraph(S)

def n1(s):
    return {"x": "a"}

def n2(s):
    return {"messages": [AIMessage(content="hi")]}

g.add_node("n1", n1)
g.add_node("n2", n2)
g.add_edge(START, "n1")
g.add_edge("n1", "n2")
g.add_edge("n2", END)
app = g.compile(checkpointer=InMemorySaver())
out = app.invoke({"messages": [HumanMessage(content="hi")]}, config={"configurable": {"thread_id": "t"}})
print("OK", out["x"], out["messages"][-1].content)