"""The CLI never executes prompts or sends data to providers."""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path
from .core import Store, compare


def read_json(path):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError(f"duplicate JSON key: {key}")
            obj[key] = value
        return obj
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"invalid JSON constant: {x}")))


def markdown(report):
    lines = ["# Prompt regression report", "", f"Result: {'PASS' if report['passed'] else 'FAIL'}",
             f"Base: {report['base']}", f"Candidate: {report['candidate']}",
             "", "Token overlap describes wording only; assertions define regression. Outputs below are untrusted recorded text."]
    prompt_diff = '\n'.join(difflib.unified_diff(report['base_prompt'].splitlines(), report['candidate_prompt'].splitlines(), fromfile='base prompt', tofile='candidate prompt', lineterm=''))
    fence = '`' * max(3, 1 + max([len(x) for x in re.findall(r'`+', prompt_diff)] or [0]))
    lines.extend(["", "## Prompt changes", fence + 'diff', prompt_diff, fence])
    for row in report["cases"]:
        # Inline JSON encoding keeps IDs single-line and escapes control characters.
        label = json.dumps(row['id'], ensure_ascii=True).replace('<', '&lt;').replace('>', '&gt;').replace('`', '&#96;')
        lines.extend(["", f"## Case {label}: {row['status']}"])
        if row["status"] == "compared":
            lines.extend([f"Score: {row['base']['score']:.3f} → {row['candidate']['score']:.3f}; delta {row['delta']:+.3f}",
                          f"Token Jaccard: {row['token_jaccard']:.3f}; JSON equivalent: {row['json_equal']}"])
            diff = '\n'.join(difflib.unified_diff(row['before'].splitlines(), row['after'].splitlines(), fromfile='base', tofile='candidate', lineterm=''))
            # Dynamic fence prevents output text from closing the code block.
            longest = max([len(part) for part in re.findall(r'`+', diff)] or [0])
            fence = '`' * max(3, longest + 1)
            lines.extend(["", fence + 'diff', diff, fence])
            if row['json_changes'] is not None:
                lines.extend(["", "Structured JSON changes:", "```json", json.dumps(row['json_changes'], ensure_ascii=True, indent=2).replace('`', r'\u0060'), "```"])
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description="Version prompts and compare recorded outputs offline")
    parser.add_argument('--store', default='.promptgit', help='object store directory (default .promptgit)')
    sub = parser.add_subparsers(dest='command', required=True)
    snap = sub.add_parser('snapshot', help='save prompt, cases and optional parent; print immutable ID')
    snap.add_argument('--prompt', required=True); snap.add_argument('--suite', required=True); snap.add_argument('--parent')
    record = sub.add_parser('record', help='import complete recorded outputs; print run ID')
    record.add_argument('--snapshot', required=True); record.add_argument('--model', required=True)
    record.add_argument('--outputs', required=True); record.add_argument('--metadata')
    show = sub.add_parser('show', help='read and verify an immutable object')
    show.add_argument('id'); show.add_argument('--kind', choices=['snapshot','run'], required=True)
    diff = sub.add_parser('diff', help='compare runs; exit 1 for regression, 2 for invalid input')
    diff.add_argument('base'); diff.add_argument('candidate'); diff.add_argument('--tolerance', type=float, default=0)
    diff.add_argument('--format', choices=['json','markdown'], default='markdown'); diff.add_argument('--output')
    args = parser.parse_args(argv)
    store = Store(args.store)
    try:
        if args.command == 'snapshot':
            print(store.snapshot(Path(args.prompt).read_text(encoding='utf-8'), read_json(args.suite), args.parent))
        elif args.command == 'record':
            print(store.record(args.snapshot, args.model, read_json(args.outputs), read_json(args.metadata) if args.metadata else None))
        elif args.command == 'show':
            print(json.dumps(store.get(args.id, args.kind), ensure_ascii=False, indent=2))
        else:
            report = compare(store, args.base, args.candidate, args.tolerance)
            result = json.dumps(report, ensure_ascii=False, indent=2) + '\n' if args.format == 'json' else markdown(report)
            if args.output:
                Path(args.output).write_text(result, encoding='utf-8')
            else:
                print(result, end='')
            return 0 if report['passed'] else 1
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f'promptgit: {exc}', file=sys.stderr)
        return 2
    return 0

if __name__ == '__main__':
    sys.exit(main())
