from langchain.agents import create_agent
from langchain_deepseek import ChatDeepSeek
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.tools import TOOLS
from app.config import settings

SYSTEM_PROMPT = (
    "你是校园图书馆自习室预约智能助手。"
    "你可以调用工具帮用户：查询自习室、查询某日可选座位、按偏好智能推荐座位、创建预约、查询预约、取消预约。"
    "回答一律使用简体中文，简洁友好。"
    "当用户提到'今天''明天''后天''下周几'等相对时间时，必须先调用 get_current_datetime 工具获取当前日期，再换算成具体日期（YYYY-MM-DD）。"
    "当用户要预约座位但缺少日期或时间等信息时，先向用户确认清楚再操作。"
    "预约成功后，明确告诉用户预约号、座位编号和时段。"
    "不要编造工具没有返回的数据。"
)

llm = ChatDeepSeek(
    model=settings.DEEPSEEK_MODEL,
    api_key=settings.DEEPSEEK_API_KEY or None,
    temperature=0.7,
    streaming=True,
)

checkpointer = InMemorySaver()

graph = create_agent(
    model=llm,
    tools=TOOLS,
    system_prompt=SYSTEM_PROMPT,
    checkpointer=checkpointer,
)