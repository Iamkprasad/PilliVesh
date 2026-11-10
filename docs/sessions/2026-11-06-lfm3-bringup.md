# Session Summary — 2026-11-06 — LFM3 1.7B bring-up

## Objective
Evaluate and, if viable, bring up LFM3 1.7B text model in PilliVesh on the phone.

## Done
- Proved Termux llama 0.7.0 cannot load LFM3 (`unknown model architecture: 'lfm3'`); Termux pkg repo still tops out at 0.7.0, so no pkg upgrade path.
- Installed upstream llama.cpp b11960 Android ARM64 (`0.8.0-dev`, commit 8642541b2) as `llama-server.b11960`/`llama-cli.b11960` in Termux prefix, with wrappers exporting `LD_LIBRARY_PATH` and backend `.so` files copied alongside the binaries (`$ORIGIN` discovery). 0.7.0 files backed up in `~/.backup/llama-0.7.0/`.
- Fixed LFM3 bring-up: catalog now `context 4096`, `min_ram_mb 1200`, `disable_reasoning true`; router passes `--reasoning off` for it (otherwise reply lands in `reasoning_content` with empty `message.content`, UI shows "[empty response]").
- Verified end-to-end via router load (port 8081) + chat completions + `benchmarks.probe` light probes. Model left unloaded (battery-lazy default). Kept as opt-in, not autoload.
- Updated `README.md` model table (added Gemma 3 1B + LFM3 with RAM/llama-version notes).

## Files changed
- `runtime/model/catalog.py` — LFM3 entry: 4096 ctx, 1200 min RAM, disable_reasoning.
- `runtime/model/router.py` — `_spawn(..., disable_reasoning)` passes `--reasoning off`.
- `README.md` — model table + LFM3 llama-version note.
- `SESSION-SUMMARY.md` — this handoff; `docs/sessions/2026-11-05-close-listening-ports.md` — archive.

## Decisions
- Side-installed upstream b11960 instead of overwriting Termux pkg files silently (wrappers + backup, reversible).
- 4096 ctx (not 8192) + 1200 min RAM: both fit measured RAM (loads at ~1.3 GB free); 8192/1600 was over-strict and self-blocking.
- `--reasoning off` only for LFM3: without it all chat output is hidden in `reasoning_content`; keeps old-binary compatibility for other models.
- Did not change autoload: SmolLM2 360M stays default.

## Verification
- `llama-cli --version` — `0.8.0-dev (b11960)` (after install).
- `python3 -m runtime.model.router load lfm3-1.7b-qad-q4_0` — loaded, `/health` ok, chat returns prose.
- `python3 -m benchmarks.probe` — 2 samples: prompt 7.74/gen 5.0 tok/s (13.0s) then prompt 3.56/gen 2.15 tok/s (26.5s); high variance (thermal/RAM), slower than SmolLM2 baseline (gen 6.17).
- `python3 -m unittest discover -s tests -q` — 132 tests, OK. UI/dashboard not re-run visually.

## Known issues / limits
- Speed is CPU-only at ~2–5 tok/s generation; expect slow replies on this phone.
- New binaries depend on wrappers + copied `.so` in bin/lib; a `pkg upgrade llama.cpp` would clobber them (restore from `~/.backup/llama-0.7.0/` or re-install b11960).
- Unrelated uncommitted changes in tree (frontend, memory, tools) left untouched and uncommitted.

## Next steps
- Test tool-calling/structured output from LFM3 through `/api/chat` and compare answers vs Qwen2.5 0.5B before considering it default.
- If keeping permanently, document install steps in README "Portability notes" so a fresh clone knows why plain `pkg install llama.cpp` fails for LFM3.
