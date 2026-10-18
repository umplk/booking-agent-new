import json
import os
import urllib.error
import urllib.request

base_url = os.getenv("CODEARTS_BASE_URL", "").rstrip("/")
api_key = os.getenv("CODEARTS_API_KEY", "")
model = os.getenv("CODEARTS_MODEL", "deepseek-chat")

if not base_url or not api_key:
    print("请先设置环境变量：")
    print("  CODEARTS_BASE_URL  模型服务地址（OpenAI 兼容，不含 /chat/completions）")
    print("  CODEARTS_API_KEY   API Key")
    print("  CODEARTS_MODEL     模型名（默认 deepseek-chat）")
    raise SystemExit(1)

url = base_url + "/chat/completions"

tools = [
    {
        "type": "function",
        "function": {
            "name": "query_available_seats",
            "description": "查询某日期时段可用的自习座位",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "日期，YYYY-MM-DD"},
                    "start_time": {"type": "string", "description": "开始时间，HH:MM"},
                    "duration_hours": {"type": "integer", "description": "时长（小时）"},
                },
                "required": ["date", "start_time"],
            },
        },
    }
]

payload = {
    "model": model,
    "messages": [
        {"role": "system", "content": "你是自习室预约助手，查询座位时必须调用工具。"},
        {"role": "user", "content": "帮我查一下明天下午3点、3小时，有没有靠窗的座位"},
    ],
    "tools": tools,
    "tool_choice": "auto",
    "stream": False,
}

req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    },
    method="POST",
)

print("请求地址:", url)
print("模型:", model)
print("-" * 60)

try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode("utf-8")
        print("HTTP", resp.status)
        data = json.loads(body)
        msg = data["choices"][0]["message"]
        if msg.get("tool_calls"):
            print("<<< 支持 function calling，模型返回了工具调用 >>>")
            print(json.dumps(msg["tool_calls"], ensure_ascii=False, indent=2))
        else:
            print("<<< 未返回 tool_calls，仅文本回复 >>>")
            print(msg.get("content"))
except urllib.error.HTTPError as e:
    print("HTTP 错误", e.code)
    print(e.read().decode("utf-8"))
except Exception as e:
    print("请求失败:", e)