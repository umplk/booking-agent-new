from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class BookingState(TypedDict):
    messages: Annotated[list, add_messages]
    intent: str
    slots: dict
    missing: list
    tool_result: str
    reply: str