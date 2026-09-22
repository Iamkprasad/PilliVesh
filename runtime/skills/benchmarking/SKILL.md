# Benchmarking Skill

## Purpose
Measure local model performance honestly and comparably on this phone.

## Activate When
- Running or interpreting LLM benchmarks
- Comparing models, quants, or context sizes
- Investigating slowdowns or thermal throttling
- Deciding which model to keep on-device

## Workflow
1. Record the starting state: free RAM, thermals, backend (Vulkan/CPU).
2. Run `benchmarks/llm_benchmark.py` via the existing module — do not invent
   ad-hoc timing loops that bypass metric parsing.
3. Read `results/benchmark_latest.json`: prompt tok/s, generation tok/s,
   elapsed, status. Never report numbers from memory or estimates.
4. Compare against `results/benchmark_history.jsonl`, not against desktop or
   published figures from other hardware.
5. Note confounders: hot thermals, low RAM, background apps.

## Rules
- One variable at a time (model, quant, context, or offload — never several).
- Do not present a failed benchmark (`status != success`) as a result.
- Small models first: validate the pipeline on 0.5B before timing 1B+.
- Keep raw logs; summarize, don't replace them.

## Verification
A benchmarking task is complete when `benchmark_latest.json` exists with
`status: success` and the metrics are quoted exactly from it.
