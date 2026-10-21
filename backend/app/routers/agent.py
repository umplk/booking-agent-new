import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from app.agent.graph import graph
from app.models.user import User
from app.utils.deps import get_current_user

router = APIRouter(prefix="/api/agent", tags=["AI 智能体"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: Optional[str] = Field(default=None)


@router.post("/chat", summary="AI 智能体对话（SSE，支持多轮记忆）")
async def chat(req: ChatRequest, current_user: User = Depends(get_current_user)):
    session_id = req.session_id or uuid.uuid4().hex
    user_id = current_user.id

    async def event_stream():
        config = {"configurable": {"thread_id": session_id, "user_id": user_id}}
        try:
            result = await graph.ainvoke(
                {"messages": [HumanMessage(content=req.message)]},
                config=config,
            )
            messages = result.get("messages") or []
            for m in reversed(messages):
                if isinstance(m, AIMessage):
                    content = m.content
                    if isinstance(content, str) and content:
                        payload = {"session_id": session_id, "content": content}
                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    break
        except Exception as exc:
            payload = {"session_id": session_id, "error": str(exc)}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        finally:
            payload = {"session_id": session_id, "done": True}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )