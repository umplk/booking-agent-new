"""意图识别评测脚本。放在 backend/ 目录下，运行：python eval_intent.py"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.agent.classifier import detect_intent_llm

# (用户说的话, 正确意图)
CASES = [
    # ---- book 预约（6）----
    ("帮我约明天9:00-10:00的自习室A1", "book"),
    ("我想订后天下午两点到四点的会议室", "book"),
    ("周五晚上7点约个座位，学习两小时", "book"),
    ("自习室场景明天约一下B1，9:00到11:00", "book"),       # 难：含“场景”
    ("我想预约明天上午的羽毛球场地", "book"),
    ("帮我把明天10点的自习室订上", "book"),

    # ---- query 查询空位（6）----
    ("帮我查一下明天自习室还有空位吗", "query"),
    ("查一下周三会议室的空闲时段", "query"),
    ("后天下午会议室能约吗", "query"),
    ("今天晚上自习室还剩几个位置", "query"),
    ("帮我看看周六有没有空的羽毛球场", "query"),
    ("明天9点到11点A1有人预约吗", "query"),               # 难：含“预约”

    # ---- cancel 取消（5）----
    ("取消预约号3", "cancel"),
    ("我不去了，帮我退掉明天的自习室", "cancel"),
    ("把预约号12取消一下", "cancel"),
    ("明天的会议室我去不了了，帮我取消", "cancel"),
    ("cancel reservation 5", "cancel"),

    # ---- list_my 我的预约（4）----
    ("我的预约有哪些", "list_my"),
    ("帮我看看我都约了什么", "list_my"),
    ("查一下我的预约记录", "list_my"),
    ("我订了哪些东西", "list_my"),

    # ---- list_scenarios 场景列表（3）----
    ("有哪些场景可以预约", "list_scenarios"),
    ("你们有什么可以约的", "list_scenarios"),
    ("列出所有场景", "list_scenarios"),

    # ---- configure 生成资源（2）----
    ("帮我生成5个羽毛球场地", "configure"),
    ("在自习室场景下新建资源，6个单人座位", "configure"),  # 难：含“场景”

    # ---- chitchat 闲聊（4）----
    ("你好", "chitchat"),
    ("谢谢你", "chitchat"),
    ("今天天气怎么样", "chitchat"),
    ("你是谁", "chitchat"),
]

MAX_WORKERS = 8

if __name__ == "__main__":
    start = time.time()
    results = [None] * len(CASES)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        future_to_idx = {
            pool.submit(detect_intent_llm, text): idx
            for idx, (text, _) in enumerate(CASES)
        }
        for fut in as_completed(future_to_idx):
            idx = future_to_idx[fut]
            try:
                results[idx] = fut.result()
            except Exception as exc:
                results[idx] = f"<error:{exc}>"

    ok = 0
    for (text, want), got in zip(CASES, results):
        if got == want:
            ok += 1
        else:
            print(f"错：{text}\n    正确={want}  识别成={got}")

    total = len(CASES)
    elapsed = time.time() - start
    print(f"\n准确率：{ok}/{total} = {ok / total:.0%}")
    print(f"耗时：{elapsed:.1f}s（并发={MAX_WORKERS}）")
