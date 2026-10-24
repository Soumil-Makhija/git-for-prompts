import json
import tempfile
import unittest
from pathlib import Path
from promptgit.core import Store, compare, evaluate, text_evidence, validate_suite

SUITE = {"cases": [{"id": "greeting", "input": "Hi", "checks": [{"contains": "hello"}, {"not_contains": "secret"}]}]}

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(self.tmp.name)
        self.version = self.store.snapshot("Be kind", SUITE)

    def test_content_addressing_and_lineage(self):
        self.assertEqual(self.version, self.store.snapshot("Be kind", SUITE))
        child = self.store.snapshot("Be brief", SUITE, self.version)
        self.assertEqual(self.store.get(child, "snapshot")["parent"], self.version)
        self.assertNotEqual(child, self.version)

    def test_integrity(self):
        path = Path(self.tmp.name) / "objects" / (self.version + ".json")
        obj = json.loads(path.read_text()); obj["data"]["prompt"] = "tampered"
        path.write_text(json.dumps(obj))
        with self.assertRaisesRegex(ValueError, "integrity"):
            self.store.get(self.version, "snapshot")
        with self.assertRaisesRegex(ValueError, "corrupt"):
            self.store.snapshot("Be kind", SUITE)

    def test_invalid_record(self):
        for outputs in [{}, {"greeting": 3}, {"greeting": "hi", "extra": "x"}]:
            with self.assertRaises(ValueError):
                self.store.record(self.version, "fixture", outputs)
        with self.assertRaises(ValueError):
            self.store.get("../../oops", "snapshot")

    def test_regression_and_model_change(self):
        a = self.store.record(self.version, "v1", {"greeting": "hello"})
        b = self.store.record(self.version, "v2", {"greeting": "secret"})
        result = compare(self.store, a, b)
        self.assertEqual(result["regressions"], ["greeting"])
        self.assertEqual(result["cases"][0]["delta"], -1)
        self.assertTrue(compare(self.store, a, b, 1)["passed"])
        self.assertTrue(compare(self.store, b, a)["passed"])

    def test_suite_drift_is_not_silent(self):
        a = self.store.record(self.version, "a", {"greeting": "hello"})
        for suite, outputs, status in [
            ({"cases": [{"id": "new", "input": "Hi", "checks": [{"equals": "hi"}]}]}, {"new": "hi"}, "removed"),
            ({"cases": [{"id": "greeting", "input": "Different", "checks": [{"equals": "hi"}]}]}, {"greeting": "hi"}, "suite_changed")]:
            v = self.store.snapshot("p", suite)
            b = self.store.record(v, "b", outputs)
            report = compare(self.store, a, b)
            self.assertFalse(report["passed"])
            self.assertEqual(report["cases"][0]["status"], status)

    def test_checks(self):
        checks = [{"equals": "{}"}, {"json_equals": {}}, {"max_chars": 2}]
        self.assertEqual(evaluate("{}", checks)["score"], 1)
        self.assertEqual(evaluate("x", checks)["score"], 1/3)
        self.assertEqual(evaluate("true", [{"json_equals": 1}])["score"], 0)

    def test_evidence_not_semantic_oracle(self):
        self.assertEqual(text_evidence("a b", "b a")["token_jaccard"], 1)
        self.assertTrue(text_evidence('{"a":1,"b":2}', '{"b":2, "a":1}')["json_equal"])
        self.assertIsNone(text_evidence("x", "y")["json_equal"])

    def test_validation(self):
        for suite in [{}, {"cases": []}, {"cases": SUITE["cases"] * 2}, {"cases": [{"id": "a", "input": "x", "checks": [{"regex": "x"}]}]}]:
            with self.assertRaises(ValueError): validate_suite(suite)
        a = self.store.record(self.version, "a", {"greeting": "hello"})
        for t in [-1, 2, float("nan")]:
            with self.assertRaises(ValueError): compare(self.store, a, a, t)

if __name__ == "__main__": unittest.main()
