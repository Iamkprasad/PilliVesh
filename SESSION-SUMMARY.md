# Session Summary — 2026-11-09 — PilliVesh advanced

## Objective
Recheck and make PilliVesh advanced for localhost web, all models, max phone efficiency (stdlib llama.cpp).

## Done
- Recheck: 140 tests OK, Qwen probe 18.6/3.5 throttled, runtime_profile stale ([2048,4096,8192), ctx fixed 4096.
- Advanced router: threads = cpu-2 (6), added --threads-batch, --flash-attn on, --parallel 1, batch 512/ubatch 128, q8 KV (kept). Adaptive ctx: 2048 if <1.8 GB free else 4096.
- Refreshed runtime_profile ([2048,4096]); added adaptive ctx test.
- Verified: 141 tests OK; Qwen probe **86.5/25.0 t/s** (was 18.6/3.5), UI 5 models at 4096, router unloaded.

## Files changed
- runtime/model/router.py — threads/flash/adaptive ctx.
- tests/test_router_phone.py — flash + adaptive test.
- README.md — advanced tuning note.
- SESSION-SUMMARY.md — this handoff.

## Decisions
- Kept stdlib CPU; no LiteRT/Vulkan (fails Adreno).
- cpu-2 threads leaves 2 cores for OS/UI; flash-attn on for prompt speed.
- Adaptive ctx instead of fixed: saves swap when RAM tight.

## Verification
- `python3 -m unittest discover -s tests -q` — 141 tests, OK.
- `probe` — 86.5/25.0 t/s, 2.43s (vs 18.6/3.5 before).
- `curl /api/models` — 5 models, all 4096.
- Router unloaded, /tmp UI stopped.

## Known issues / limits
- CPU-only; NPU needs native Gallery app. Swap still possible if many apps open.
- 2048 ctx truncates long chats (<1.8 GB case).
- Uncommitted frontend/memory/tools untouched.

## Next steps
- Cool-down bench compare; try SmolLM2 download as fastest first-run.
