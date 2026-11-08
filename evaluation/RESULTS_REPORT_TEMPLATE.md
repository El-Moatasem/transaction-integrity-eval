# Results report — TEMPLATE (copy to results/RESULTS_REPORT.md only after real runs)

**Status:** No empirical model scores are supplied in the codebase. Copy this template and fill exclusively from authentic trial data.

## Frozen benchmark
- Source commit/release and SHA256 manifest:
- Task IDs included / excluded and rationale:
- Exact Harbor, Docker, Python, pytest and agent versions:
- Date range (UTC) and access configuration:
- Trial isolation / network controls verified:
- Number of fresh runs per task and model:

## Actual model comparison

| Exact model ID | Date UTC | Agent/version | Settings | Tasks | n per task | Passed/attempted | Observed pass@k | Observed pass^k | Actual cost | Actual runtime |
|---|---|---|---|---|---|---|---|---|---|---|

## Per-task analysis and evidence

| Task | Model/trial | Grade | Transcript/grade file path | Actual observed mistake or success | Why rubric accepts/rejects | Expert checked? |
|---|---|---|---|---|---|---|

## Main finding and interpretation

What is the important, **observed** capability gap? Explain why a payment/backend expert would care. Cite concrete failures and contrast with successful models/trials. If the runs do not show a real model limitation, say so.

## Quality controls and limitations

- Positive reference and independently correct variants tested:
- Deliberately wrong implementations rejected:
- Any discovered false-pass/false-fail and fix/retests:
- Trial-to-trial variability and infrastructure failures:
- Public reference answer contamination and egress mitigations:
- Cost, timing, reproducibility limitations:
- Human expertise / verification of task contracts:
