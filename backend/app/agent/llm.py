from langchain_deepseek import ChatDeepSeek

from app.config import settings

llm = ChatDeepSeek(
    model=settings.DEEPSEEK_MODEL,
    api_key=settings.DEEPSEEK_API_KEY or None,
    temperature=0.3,
)