# Session Summary — 2026-11-09 — Termux cleanup + model bench + LiteRT rejection

## Objective
Reduce Termux/Debian 13GB footprint, benchmark PilliVesh models (Qwen/LFM3/SparkX), evaluate Google AI Edge Gallery/LiteRT for speed.

## Done
- Cleaned Termux/Debian: ~/.gradle, /tmp/opencode (Chrome profiles), npm caches, /home/openclaw, agy/freebuff binaries, chromium pkg + autoremove, docs/locale/apt lists. Freed ~4.4G (89G->84G used).
- Deleted dead projects: OpenDots, 3dGenie, PilliVeh, voice-agent (331M), antigravity-api, html-anime.
- Downloaded + benchmarked Spark-X2.6-1.7B GGUF (XHToken, spark2_5, 1.7GB, Apache-2.0) via llama.cpp b11960: loads, probe 40.9/9.8 t/s, math 126 with reasoning on, weak quantum explanation. Then removed (user request).
- Compared Qwen 0.5B (92.8/24.2 t/s fresh, coding ✅, math ✅) vs LFM3 1.7B (44.6/6.5, best quantum explanation) vs SparkX: Qwen wins on phone, LFM3 runner-up.
- Evaluated LiteRT (Gallery tech): installed litert-lm-api 0.19.1, tested FunctionGemma 270M (function-call only) + Gemma3 1B int4 CPU (math wrong → 28, palindrome bug, quantum ok, 4-10s/query) and GPU (fails: 151MB buffer > 128MB Adreno limit). CPU LiteRT not faster/better than llama.cpp here; then uninstalled pip + deleted models/litert (830M) to honor stdlib-only rule.

## Files changed
- SESSION-SUMMARY.md — this handoff.
- docs/sessions/2026-11-06-lfm3-bringup.md — archived prior summary.
- models/litert/* — deleted (gitignored, no tracked change).

## Decisions
- Keep PilliVesh stdlib-only llama.cpp CPU path; do NOT add LiteRT dep (AGENTS.md forbids pip). Gallery speed comes from native app + NPU/GPU, not CPU Python.
- Keep Qwen as default, LFM3 opt-in; do not autoload SparkX.
- Deleted projects/cache as listed; kept PilliVesh, bimaniti, what-if-blogs.

## Verification
- `python3 -m unittest discover -s tests -q` — 138 tests, OK.
- `python3 -c "import litert_lm"` — ModuleNotFoundError after uninstall (intended).
- `ls models/` — only LFM3 + Qwen remain.

## Known issues / limits
- No Vulkan; CPU-only ~2-24 t/s, throttles under swap (59MB free, 3GB swap during bench).
- LiteRT GPU path fails on Adreno; CPU path not superior. To use Gallery tech properly, run the Gallery APK separately or amend AGENTS.md to allow optional litert dep.
- Uncommitted user files in tree (frontend, memory, tools) left untouched.

## Next steps
- Apply ctx cap 2048 + threads/slots limit in router if user approves (not yet applied).
- Or: download SmolLM2/Llama/Gemma catalog models if full 6-model bench wanted.
