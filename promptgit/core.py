"""Content addressed snapshots and deliberately explicit, deterministic scoring."""
import hashlib
import json
import math
import re
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def validate_suite(suite):
    if not isinstance(suite, dict) or set(suite) != {"cases"} or not isinstance(suite["cases"], list) or not suite["cases"]:
        raise ValueError("suite must contain a nonempty cases list")
    ids = set()
    for case in suite["cases"]:
        if not isinstance(case, dict) or set(case) != {"id", "input", "checks"}:
            raise ValueError("each case requires id, input and checks")
        if not isinstance(case["id"], str) or not case["id"] or case["id"] in ids:
            raise ValueError("case IDs must be unique nonempty strings")
        ids.add(case["id"])
        if not isinstance(case["input"], str) or not isinstance(case["checks"], list) or not case["checks"]:
            raise ValueError("case input must be text and checks nonempty")
        for check in case["checks"]:
            if not isinstance(check, dict) or len(check) != 1:
                raise ValueError("each check must have exactly one operator")
            op, arg = next(iter(check.items()))
            if op in {"contains", "not_contains", "equals"}:
                if not isinstance(arg, str):
                    raise ValueError("text check arguments must be strings")
            elif op == "json_equals":
                canonical(arg)
            elif op == "max_chars":
                if type(arg) is not int or arg < 0:
                    raise ValueError("max_chars must be a nonnegative integer")
            else:
                raise ValueError(f"unknown check: {op}")
    return suite


def evaluate(output, checks):
    results = []
    for check in checks:
        op, arg = next(iter(check.items()))
        if op == "contains":
            passed = arg in output
        elif op == "not_contains":
            passed = arg not in output
        elif op == "equals":
            passed = output == arg
        elif op == "max_chars":
            passed = len(output) <= arg
        elif op == "json_equals":
            try:
                passed = canonical(json.loads(output)) == canonical(arg)
            except (ValueError, TypeError):
                passed = False
        else:
            raise ValueError(f"unknown check: {op}")
        results.append({"check": check, "passed": passed})
    return {"score": sum(r["passed"] for r in results) / len(results), "checks": results}


class Store:
    def __init__(self, root):
        self.root = Path(root)

    def put(self, kind, data):
        obj = {"schema": 1, "kind": kind, "data": data}
        oid = digest(obj)
        directory = self.root / "objects"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (oid + ".json")
        encoded = canonical(obj) + "\n"
        try:
            with path.open("x", encoding="utf-8") as f:
                f.write(encoded)
        except FileExistsError:
            if path.read_text(encoding="utf-8") != encoded:
                raise ValueError("existing object is corrupt")
        return oid

    def get(self, oid, kind):
        if not re.fullmatch(r"[0-9a-f]{64}", oid):
            raise ValueError("expected full 64-character object ID")
        obj = json.loads((self.root / "objects" / (oid + ".json")).read_text(encoding="utf-8"))
        if digest(obj) != oid or obj.get("schema") != 1 or obj.get("kind") != kind:
            raise ValueError("object integrity or type check failed")
        return obj["data"]

    def snapshot(self, prompt, suite, parent=None):
        validate_suite(suite)
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be nonempty text")
        if parent:
            self.get(parent, "snapshot")
        return self.put("snapshot", {"prompt": prompt, "suite": suite, "parent": parent})

    def record(self, snapshot, model, outputs, metadata=None):
        version = self.get(snapshot, "snapshot")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model label is required")
        expected = {c["id"] for c in version["suite"]["cases"]}
        if not isinstance(outputs, dict) or set(outputs) != expected or any(not isinstance(v, str) for v in outputs.values()):
            raise ValueError("outputs must contain exactly one text output for every case ID")
        if metadata is not None and not isinstance(metadata, dict):
            raise ValueError("metadata must be an object")
        return self.put("run", {"snapshot": snapshot, "model": model, "outputs": outputs, "metadata": metadata or {}})


def json_changes(before, after, path=""):
    """JSON Pointer paths, treating arrays as ordered values."""
    if canonical(before) == canonical(after):
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        changes = []
        for key in sorted(set(before) | set(after)):
            child = path + "/" + key.replace("~", "~0").replace("/", "~1")
            if key not in before:
                changes.append({"path": child, "change": "added", "after": after[key]})
            elif key not in after:
                changes.append({"path": child, "change": "removed", "before": before[key]})
            else:
                changes.extend(json_changes(before[key], after[key], child))
        return changes
    return [{"path": path, "change": "replaced", "before": before, "after": after}]


def text_evidence(before, after):
    def tokens(text):
        return set(re.findall(r"\w+", text.casefold()))
    a, b = tokens(before), tokens(after)
    result = {"changed": before != after, "token_jaccard": len(a & b) / len(a | b) if a | b else 1.0}
    try:
        left, right = json.loads(before), json.loads(after)
        result["json_equal"] = canonical(left) == canonical(right)
        result["json_changes"] = json_changes(left, right)
    except (ValueError, TypeError):
        result["json_equal"] = None
        result["json_changes"] = None
    return result


def compare(store, base_id, candidate_id, tolerance=0.0):
    if not math.isfinite(tolerance) or not 0 <= tolerance <= 1:
        raise ValueError("tolerance must be between 0 and 1")
    base, candidate = store.get(base_id, "run"), store.get(candidate_id, "run")
    old, new = store.get(base["snapshot"], "snapshot"), store.get(candidate["snapshot"], "snapshot")
    old_cases = {c["id"]: c for c in old["suite"]["cases"]}
    new_cases = {c["id"]: c for c in new["suite"]["cases"]}
    rows, regressions = [], []
    for cid in sorted(set(old_cases) | set(new_cases)):
        if cid not in old_cases:
            rows.append({"id": cid, "status": "added"})
            continue
        if cid not in new_cases:
            rows.append({"id": cid, "status": "removed"})
            regressions.append(cid)
            continue
        if old_cases[cid] != new_cases[cid]:
            rows.append({"id": cid, "status": "suite_changed"})
            regressions.append(cid)
            continue
        left, right = base["outputs"][cid], candidate["outputs"][cid]
        a, b = evaluate(left, old_cases[cid]["checks"]), evaluate(right, old_cases[cid]["checks"])
        regression = a["score"] - b["score"] > tolerance + 1e-12
        if regression:
            regressions.append(cid)
        rows.append({"id": cid, "status": "compared", "base": a, "candidate": b,
                     "delta": b["score"] - a["score"], "regression": regression,
                     "before": left, "after": right, **text_evidence(left, right)})
    return {"schema": 1, "base": base_id, "candidate": candidate_id,
            "base_model": base["model"], "candidate_model": candidate["model"],
            "prompt_changed": old["prompt"] != new["prompt"],
            "base_prompt": old["prompt"], "candidate_prompt": new["prompt"],
            "base_metadata": base["metadata"], "candidate_metadata": candidate["metadata"],
            "tolerance": tolerance,
            "regressions": regressions, "passed": not regressions, "cases": rows}
