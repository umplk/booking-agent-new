import csv
import unittest
from collections import Counter
from pathlib import Path

CASES_PATH = Path(__file__).resolve().parents[2] / "eval" / "cases.csv"

INTENTS = {"book", "query", "cancel", "list_my", "list_scenarios", "configure", "chitchat"}
SPLITS = {"dev", "test"}
HARD_TYPES = {"normal", "colloquial", "distractor", "typo", "elliptical", "multiturn"}
REQUIRED_COLUMNS = {"id", "text", "intent", "split", "hard_type", "context", "prev_intent", "note"}


class EvalCasesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with CASES_PATH.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            cls.columns = set(reader.fieldnames or [])
            cls.rows = list(reader)

    def test_columns(self):
        self.assertTrue(
            REQUIRED_COLUMNS.issubset(self.columns),
            f"缺少列：{REQUIRED_COLUMNS - self.columns}",
        )

    def test_size_in_range(self):
        self.assertGreaterEqual(len(self.rows), 150)
        self.assertLessEqual(len(self.rows), 300)

    def test_ids_unique_and_text_not_empty(self):
        ids = [r["id"] for r in self.rows]
        self.assertEqual(len(ids), len(set(ids)), "存在重复 id")
        for r in self.rows:
            self.assertTrue(r["text"].strip(), f"{r['id']} 的 text 为空")

    def test_enum_values(self):
        for r in self.rows:
            self.assertIn(r["intent"], INTENTS, f"{r['id']} 意图非法：{r['intent']}")
            self.assertIn(r["split"], SPLITS, f"{r['id']} split 非法：{r['split']}")
            self.assertIn(r["hard_type"], HARD_TYPES, f"{r['id']} hard_type 非法：{r['hard_type']}")

    def test_each_intent_has_at_least_20(self):
        counter = Counter(r["intent"] for r in self.rows)
        for intent in INTENTS:
            self.assertGreaterEqual(counter[intent], 20, f"{intent} 仅 {counter[intent]} 条")

    def test_split_ratio_about_7_to_3(self):
        total = len(self.rows)
        test_count = sum(1 for r in self.rows if r["split"] == "test")
        self.assertAlmostEqual(test_count / total, 0.3, delta=0.03, msg="test 占比应约 30%")
        for intent in INTENTS:
            subset = [r for r in self.rows if r["intent"] == intent]
            test_subset = sum(1 for r in subset if r["split"] == "test")
            self.assertAlmostEqual(
                test_subset / len(subset), 0.3, delta=0.05,
                msg=f"{intent} 的 test 占比偏离 30%",
            )

    def test_multiturn_rows_have_context_and_prev_intent(self):
        for r in self.rows:
            if r["hard_type"] == "multiturn":
                self.assertTrue(r["context"].strip(), f"{r['id']} 多轮用例缺 context")
                self.assertIn(r["prev_intent"], INTENTS, f"{r['id']} 多轮用例 prev_intent 非法")
            else:
                self.assertFalse(r["prev_intent"].strip(), f"{r['id']} 非多轮用例不应有 prev_intent")

    def test_hard_cases_ratio(self):
        hard = sum(1 for r in self.rows if r["hard_type"] != "normal")
        self.assertGreaterEqual(hard / len(self.rows), 0.4, "难例占比应不低于 40%")


if __name__ == "__main__":
    unittest.main()