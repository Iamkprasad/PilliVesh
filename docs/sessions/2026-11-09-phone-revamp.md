# Session Summary — 2026-11-09 — PilliVesh phone revamp

## Objective
Revamp PilliVesh for localhost web + all catalog models using most efficient phone tech (keep stdlib llama.cpp CPU).

## Done
- Capped all model ctx to 4096 (was 8192/12288/131072) in catalog.py + local entry; router cap 16384→4096; runtime_config candidates [2048,4096].
- Router _spawn now: --threads <cpu_count> --parallel 1 --batch-size 512 --ubatch-size 128 --cache-type-k/v q8_0. Keeps --ctx-size, -dev none, --reasoning off for LFM3.
- app.py: TELEMETRY 5→30s, BENCH 30→300s; autoload prefers Qwen 0.5B (fastest) over first-installed.
- Added tests/test_router_phone.py (ctx cap + spawn flags); README ctx + efficiency note.
- Verified: 140 tests OK; router loads Qwen; localhost:8080 serves; /api/models lists all 5 + 4096 ctx; router unloaded after.

## Files changed
- runtime/model/router.py — phone spawn flags + 4096 cap.
- runtime/model/catalog.py — context 4096 everywhere.
- runtime/model/runtime_config.py — candidates [2048,4096].
- runtime/server/app.py — slower telemetry/bench, Qwen-first autoload.
- tests/test_router_phone.py — new test.
- README.md — ctx/efficiency note.
- SESSION-SUMMARY.md — this handoff.

## Decisions
- Kept stdlib llama.cpp CPU, rejected LiteRT (pip, GPU fails on Adreno, CPU worse).
- 4096 max ctx for RAM (was 8-12K → swap crash); Qwen default for speed.
- Single slot (--parallel 1), q8 KV cache for bandwidth.

## Verification
- `python3 -m unittest discover -s tests -q` — 140 tests, OK.
- `python3 -m runtime.model.router load qwen2.5-0.5b-q4km` — loaded pid..., /health ok.
- `curl 127.0.0.1:8080/` — HTML ok; `/api/models` — catalog with ctx 4096.
- Router unloaded after check (stopped, port free).

## Known issues / limits
- 4096 truncates long chats; memory summarization needed for >4K history.
- No Vulkan/NPU; CPU-only ~9-24 t/s gen. Gallery NPU speed needs native app.
- Uncommitted frontend/memory/tools edits left untouched.

## Next steps
- Benchmark 140-test suite again after thermal cool-down; compare probe before/after.
- Consider SmolLM2 download for smallest-model first-run test.
