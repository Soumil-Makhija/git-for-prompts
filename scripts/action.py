"""Composite action entrypoint, independently testable without GitHub access."""
import os
import json
import sys
from pathlib import Path
from promptgit.cli import main
from promptgit.core import Store, compare
from promptgit.github_comment import publish

def run():
    args = ['--store', os.environ['PROMPTGIT_STORE'], 'diff', os.environ['PROMPTGIT_BASE'],
            os.environ['PROMPTGIT_CANDIDATE'], '--output', os.environ['PROMPTGIT_REPORT']]
    code = main(args)
    if code in (0, 1):
        summary = os.environ.get('GITHUB_STEP_SUMMARY')
        if summary:
            with open(summary, 'a', encoding='utf-8') as f:
                f.write(Path(os.environ['PROMPTGIT_REPORT']).read_text(encoding='utf-8'))
        if os.environ.get('PROMPTGIT_COMMENT', 'false') == 'true':
            try:
                if os.environ.get('GITHUB_EVENT_NAME') != 'pull_request':
                    raise ValueError('comment publication only supports pull_request events')
                report = compare(Store(os.environ['PROMPTGIT_STORE']), os.environ['PROMPTGIT_BASE'], os.environ['PROMPTGIT_CANDIDATE'])
                # Fixed wording plus counts/hex IDs; do not publish untrusted text or mentions.
                body = ("Prompt regression guard: " + ("PASS" if report['passed'] else "FAIL") +
                        f"\n\n{len(report['regressions'])} case regressions/coverage changes in {len(report['cases'])} cases." +
                        "\n\nBase: " + report['base'] + "\nCandidate: " + report['candidate'] +
                        "\n\nSee the Actions job summary for detailed evidence.")
                publish(json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text()),
                        os.environ['GITHUB_REPOSITORY'], os.environ.get('PROMPTGIT_TOKEN', ''), body)
            except (OSError, ValueError, KeyError) as exc:
                print(f'promptgit: comment publication failed: {type(exc).__name__}', file=sys.stderr)
                return 2
    return code

if __name__ == '__main__':
    raise SystemExit(run())
