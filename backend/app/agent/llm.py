from langchain_deepseek import ChatDeepSeek

from app.config import settings

llm = ChatDeepSeek(
    model=settings.DEEPSEEK_MODEL,
    api_key=settings.DEEPSEEK_API_KEY or None,
    temperature=0.3,
    request_timeout=settings.LLM_TIMEOUT_SECONDS,
    max_retries=settings.LLM_MAX_RETRIES,
)