# Git for prompts

Version prompt text and evaluation cases, import recorded model outputs, and see which assertions regressed across prompts or models. Everything runs locally with Python 3.11+ and no runtime dependencies or paid APIs.

## Quick start

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
python scripts/demo.py
cat reports/report.md
```

The demo uses **synthetic recorded outputs**, not live model responses. It creates two prompt versions, links their history, imports two runs, and detects both a changed classification (`account` → `billing`) and a refund-policy regression. The classification score falls from 1 to 0; the refund score falls from 1 to 1/3. It also checks a passing identical-run comparison. Artifacts in `reports/` include a store, run IDs and JSON/Markdown evidence. The script checks actual CLI return codes and results and exits successfully only if the expected regression is found.

## Version and compare your own prompts

Create a suite:

```json
{"cases":[{"id":"greet","input":"Hi","checks":[{"contains":"hello"},{"max_chars":80}]}]}
```

```sh
V1=$(promptgit snapshot --prompt prompt.txt --suite suite.json)
# Run the prompt with each case input yourself and save outputs.json:
# {"greet":"hello world"}
R1=$(promptgit record --snapshot "$V1" --model local-model-v1 --outputs outputs.json)
# Edit prompt.txt; save new recorded outputs as candidate.json.
V2=$(promptgit snapshot --prompt prompt.txt --suite suite.json --parent "$V1")
R2=$(promptgit record --snapshot "$V2" --model local-model-v2 --outputs candidate.json)
promptgit diff "$R1" "$R2" --format markdown --output comparison.md
```

`record --metadata metadata.json` attaches a JSON object for provider settings, seeds, generation date or other provenance. Model labels, outputs and metadata are user supplied and cannot be independently authenticated. No prompt rendering or model execution occurs. Case `input` is the documented input the producer must have used; the tool cannot verify that claim.

`show ID --kind snapshot` or `show ID --kind run` verifies and displays an object. Use `--store PATH` **before** the subcommand to select a store (default `.promptgit`). Copy the whole store to share immutable objects, or explicitly version its `objects/` directory in your own repository after reviewing contents. This project's default ignore rules keep local prompts/outputs out of commits.

## What the diff means

* Prompt text and output unified diffs show exact changes.
* JSON Pointer field changes describe structured output changes. Object-key order and whitespace do not create changes. Arrays are replaced as whole ordered values. JSON numeric spellings such as `1` and `1.0` differ intentionally.
* Token Jaccard overlap compares case-folded word sets. It is **lexical**, not an embedding or LLM judgment. Reordered words and negated statements can have very high overlap and opposite meanings.
* Domain assertions express expected meaning: `contains`, `not_contains`, `equals`, `max_chars`, and `json_equals`. Text matching is case sensitive; `max_chars` counts Python Unicode code points. Each case's score is the unweighted fraction of checks passing. All check outcomes appear in the JSON report.
* A case regresses when its score drops by more than `--tolerance` (0 by default, range 0–1). The guard checks each case, so an improvement elsewhere cannot hide a drop. Equal scores can still conceal a changed set of passing assertions: review check-level evidence.
* Removed cases or changed input/checks fail the guard as coverage changes. Added cases are marked added and do not gate the comparison; baseline them explicitly after review. Matching case IDs alone never suffices for comparability.

Exit codes: **0** no detected regression; **1** regression/coverage change; **2** invalid input or storage error. A passing report does not prove output quality: baseline failures that remain failures do not count as a drop. Do not use lexical similarity as an acceptance threshold. Change one variable at a time for attribution; changing prompt and model simultaneously cannot identify the cause.

## GitHub Action

The composite action compares existing recorded runs and writes a Markdown job summary, failing on regressions. It does not generate outputs. Reports work without write permissions. Optional `comment: 'true'` plus `token: ${{ github.token }}` and `pull-requests: write` explicitly enables one summary comment per run for same-repository `pull_request` events. Fork PRs and other event types are rejected. Comment publication is implemented and HTTP-contract tested with a fake transport; it has not been exercised against the live posting endpoint. No message or comment is sent by this project build.

```yaml
permissions:
  contents: read
steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-python@v5
    with:
      python-version: '3.11'
  - uses: Soumil-Makhija/git-for-prompts@main # pin a reviewed commit in production
    with:
      store: evaluation-store
      base: FULL_BASE_RUN_SHA256
      candidate: FULL_CANDIDATE_RUN_SHA256
      report: promptgit-report.md
```

The store must already contain both runs and their snapshots; fetch/store review is the caller's responsibility. Only use public-safe fixture data on public CI. Inputs travel through environment variables, following [GitHub's composite metadata documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/metadata-syntax) and [context documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts). The action uses the setup Python directly, without installing dependencies. Keep any report parent directory present. CI tests the action on identical runs and unit-tests pass, fail and invalid-input paths through its entrypoint. Default report-only execution never needs a write token. Optional comments include only fixed text, counts and immutable IDs, avoiding untrusted output and notification mentions. Comment publication uses [GitHub's documented issue-comment endpoint](https://docs.github.com/en/rest/issues/comments#create-an-issue-comment); failures return exit 2. Keep this opt-in disabled for unreviewed code; do not use `pull_request_target` to execute PR code. GitHub.com is supported for publication; GitHub Enterprise endpoints are not implemented.

## Architecture and limits

`promptgit/core.py` validates suites, stores SHA-256-addressed canonical JSON, verifies object hashes on load, and scores comparisons. Snapshot IDs bind prompt text, suite and parent; run IDs bind snapshot, model, full outputs and metadata. Identical content deduplicates. IDs require full 64-character lowercase hashes; no mutable aliases, branches, merge machinery, timestamps or remote synchronization are hidden in the store. Parents preserve lineage but this is not an implementation of Git itself. Import requires every case exactly once; duplicate JSON input keys and nonfinite values are rejected by the CLI. Objects are trusted local files, not signed attestations; hashes detect edits, not dishonest provenance. No encryption or access-control layer is provided. Store writes are not a multi-object transaction; interrupted writes may need recovery from a backup. Avoid concurrent writers.

No embeddings, live providers, open-ended natural language reasoning, repeated-sampling significance tests, JSON Schema, custom-code judges or multi-turn adapters are implemented. This is an offline evidence tool for recorded single-output cases. Semantic findings are limited to explicit domain assertions and structured JSON differences. These finite fixtures do not measure model accuracy. No real model evaluation or performance benchmark is claimed. Large outputs are loaded into memory. Reports contain full prompts and outputs; review them before sharing.

## Development

```sh
python -m unittest discover -s tests -v
python -m compileall -q promptgit scripts
python -m pip wheel . --no-deps -w dist
python -m pip install --no-deps dist/*.whl
python scripts/demo.py /tmp/promptgit-evidence
```

CI runs tests, installation, a separate-directory installed CLI example and the composite action on Python 3.11/3.14 on Linux/macOS. Fixtures are synthetic and deterministic. Tests include integrity failures, lineage/deduplication, incomplete runs, suite drift, tolerance, structured JSON paths/types, safe report fences, subprocess CLI behavior and action summaries.
