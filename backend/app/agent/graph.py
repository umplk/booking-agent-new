from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    ask_missing,
    call_tool,
    extract_slots,
    respond,
    route_after_intent,
    route_intent,
    slot_status,
)
from app.agent.state import BookingState

checkpointer = InMemorySaver()

builder = StateGraph(BookingState)
builder.add_node("route_intent", route_intent)
builder.add_node("extract_slots", extract_slots)
builder.add_node("ask_missing", ask_missing)
builder.add_node("call_tool", call_tool)
builder.add_node("respond", respond)

builder.add_edge(START, "route_intent")
builder.add_conditional_edges(
    "route_intent",
    route_after_intent,
    {"proceed": "extract_slots", "done": END},
)
builder.add_conditional_edges(
    "extract_slots",
    slot_status,
    {"complete": "call_tool", "missing": "ask_missing"},
)
builder.add_edge("call_tool", "respond")
builder.add_edge("ask_missing", END)
builder.add_edge("respond", END)

graph = builder.compile(checkpointer=checkpointer)