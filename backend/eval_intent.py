"""意图识别评测脚本。

数据文件：仓库根目录 eval/cases.csv（共 210 条，7 类意图各 30 条）。
split 列把数据固定分为 dev / test（约 7:3）：
- 调 prompt、改规则时只看 dev；
- 最终对外报数字只看 test，避免过拟合。
多轮补充用例（如只回“下午三点”）带 prev_intent 列，评测时复用
classifier.apply_prev_intent，与 nodes.route_intent 的线上逻辑保持一致。

用法（在 backend/ 目录下运行）：
    python eval_intent.py                    # 默认 LLM 引擎，只跑 dev
    python eval_intent.py --split test       # 最终验收，只报测试集
    python eval_intent.py --split all        # dev / test 分开报
    python eval_intent.py --engine rule      # 纯关键词规则基线
    python eval_intent.py --show-error 0     # 打印全部错例
"""
import argparse
import csv
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from app.agent.classifier import apply_prev_intent, detect_intent, detect_intent_llm

CASES_PATH = Path(__file__).resolve().parents[1] / "eval" / "cases.csv"
INTENTS = ["book", "query", "cancel", "list_my", "list_scenarios", "configure", "chitchat"]
MAX_WORKERS = 8


def load_cases():
    if not CASES_PATH.exists():
        raise SystemExit(f"找不到评测数据：{CASES_PATH}")
    with CASES_PATH.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def predict(row, engine):
    if engine == "rule":
        got = detect_intent(row["text"])
    else:
        got = detect_intent_llm(row["text"])
    prev_intent = (row.get("prev_intent") or "").strip()
    if prev_intent:
        got = apply_prev_intent(got, prev_intent, missing=True)
    return got


def run_suite(rows, engine):
    results = [None] * len(rows)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        future_to_idx = {pool.submit(predict, row, engine): i for i, row in enumerate(rows)}
        for fut in as_completed(future_to_idx):
            idx = future_to_idx[fut]
            try:
                results[idx] = fut.result()
            except Exception as exc:
                results[idx] = f"<error:{exc}>"
    return results


def report(name, rows, results, show_error, engine):
    total = len(rows)
    print(f"\n=== {name} / engine={engine} ===")
    if not total:
        print("无样本")
        return
    ok = sum(1 for r, g in zip(rows, results) if r["intent"] == g)
    print(f"样本：{total}  正确：{ok}  准确率：{ok / total:.1%}")

    labels = [i for i in INTENTS if any(r["intent"] == i for r in rows)]
    print("\n每类指标：")
    print(f"{'intent':<16}{'support':>8}{'precision':>11}{'recall':>9}{'f1':>8}")
    for label in labels:
        tp = sum(1 for r, g in zip(rows, results) if r["intent"] == label and g == label)
        fp = sum(1 for r, g in zip(rows, results) if r["intent"] != label and g == label)
        fn = sum(1 for r, g in zip(rows, results) if r["intent"] == label and g != label)
        support = tp + fn
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        print(f"{label:<16}{support:>8}{precision:>11.1%}{recall:>9.1%}{f1:>8.1%}")

    cols = labels + sorted({g for g in results if g not in labels})
    print("\n混淆矩阵（行=真实，列=预测）：")
    print(f"{'':<16}" + "".join(f"{c:>16}" for c in cols))
    for label in labels:
        row_counts = Counter(g for r, g in zip(rows, results) if r["intent"] == label)
        print(f"{label:<16}" + "".join(f"{row_counts.get(c, 0):>16}" for c in cols))

    print("\n按 hard_type 分组准确率：")
    groups = {}
    for r, g in zip(rows, results):
        groups.setdefault(r["hard_type"] or "unknown", []).append(r["intent"] == g)
    for hard_type, hits in sorted(groups.items()):
        print(f"  {hard_type:<14}{sum(hits)}/{len(hits)} = {sum(hits) / len(hits):.1%}")

    wrong = [(r, g) for r, g in zip(rows, results) if r["intent"] != g]
    print(f"\n错例：{len(wrong)} 条")
    shown = wrong if show_error == 0 else wrong[:show_error]
    for r, got in shown:
        extra = f"（上一轮={r['prev_intent']}）" if r.get("prev_intent") else ""
        print(f"  [{r['id']}] {r['text']}  正确={r['intent']} 识别={got}{extra}")


def main():
    parser = argparse.ArgumentParser(description="意图识别评测")
    parser.add_argument(
        "--split",
        choices=["dev", "test", "all"],
        default="dev",
        help="评测哪个集合；默认 dev，调 prompt 时不要看 test",
    )
    parser.add_argument(
        "--show-error",
        type=int,
        default=20,
        help="最多打印多少条错例，0 表示全部，默认 20",
    )
    parser.add_argument(
        "--engine",
        choices=["llm", "rule"],
        default="llm",
        help="分类引擎：llm 调 DeepSeek（默认），rule 为纯关键词规则基线",
    )
    args = parser.parse_args()

    rows = load_cases()
    splits = ["dev", "test"] if args.split == "all" else [args.split]
    start = time.time()
    for split in splits:
        subset = [r for r in rows if r["split"] == split]
        if split == "test" and args.split == "all":
            print("\n注意：test 集只用于最终验收，不要据此回头调 prompt。")
        results = run_suite(subset, args.engine)
        report(split, subset, results, args.show_error, args.engine)
    print(f"\n耗时：{time.time() - start:.1f}s（并发={MAX_WORKERS}）")


if __name__ == "__main__":
    main()