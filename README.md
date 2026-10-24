# Git for prompts

Offline content-addressed prompt snapshots, recorded outputs and evidence-based regression diffs. Python 3.11+, no runtime dependencies and no paid APIs.

Core milestone: `python3 -m unittest discover -s tests -v`.
Snapshots bind prompt text, evaluation cases and an optional parent. Runs bind a snapshot, model label, outputs and metadata. SHA-256 integrity is verified on reads. Assertions score each case; removed or changed baseline cases fail comparison rather than silently reducing coverage.

Token overlap is descriptive lexical evidence, not a proof of semantic equivalence. CLI and full workflow follow in the next milestone.
