# Git for prompts

Offline content-addressed prompt snapshots, recorded outputs and evidence-based regression diffs. Python 3.11+, no runtime dependencies and no paid APIs.

Core milestone: `python3 -m unittest discover -s tests -v`.
Snapshots bind prompt text, evaluation cases and an optional parent. Runs bind a snapshot, model label, outputs and metadata. SHA-256 integrity is verified on reads. Assertions score each case; removed or changed baseline cases fail comparison rather than silently reducing coverage.

Token overlap is descriptive lexical evidence, not a proof of semantic equivalence. CLI and full workflow follow in the next milestone.

## CLI

`python3 -m promptgit snapshot --prompt prompt.txt --suite suite.json` prints a version ID. Use `--parent ID` for lineage.

A suite is `{"cases":[{"id":"greet","input":"Hi","checks":[{"contains":"hello"}]}]}`.
Import recorded outputs with `python3 -m promptgit record --snapshot ID --model MODEL --outputs outputs.json`, where outputs is `{"greet":"hello world"}`. This prints a run ID. Compare two runs with `python3 -m promptgit diff BASE_RUN CANDIDATE_RUN --format markdown`. Use `--format json` for machine-readable scores and failed assertions. Exit codes: 0 passed, 1 regression or changed/removed baseline cases, 2 invalid input. `--tolerance 0.1` allows at most a 0.1 score drop per case. `show ID --kind snapshot` verifies and displays stored data.

No provider is called: model labels and metadata are user-supplied provenance. Each case's score is the fraction of its checks passing. Supported checks: `contains`, `not_contains`, `equals`, `max_chars`, `json_equals`. Comparisons use identical baseline cases; changed input/checks require explicit baseline review. Runs can compare different prompts, models, or both; simultaneous changes cannot establish attribution.
