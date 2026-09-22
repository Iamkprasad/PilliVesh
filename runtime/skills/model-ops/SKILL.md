# Model-Ops Skill

## Purpose
Choose, download, and run GGUF models that actually fit this phone.

## Activate When
- Picking a model or quant for ~2 GB available RAM
- Downloading a model into `models/`
- Deciding context size or GPU offload settings
- Diagnosing out-of-memory or slow inference

## Workflow
1. Check current headroom first: `available_mb` from telemetry and
   `runtime_profile.json` (`ram_available_mb`).
2. Pick from `runtime/model/catalog.py` (allow-listed, verified upstream).
   Rule of thumb: model file + ~0.5 GB overhead must fit in available RAM.
   When unsure, start with the smallest entry (SmolLM2 360M).
3. Download via the Models screen or
   `python3 -m runtime.model.downloader <model-id>` — never hand-rolled
   `curl` one-liners that bypass size verification.
4. Confirm: file present in `models/`, profile shows `model_downloaded`,
   dashboard Model reads "Installed".
5. Validate with `benchmarks/llm_benchmark.py` before relying on the model.

## Rules
- Never download a model larger than free storage (`df` first).
- Never invent model URLs; only catalog entries may be fetched.
- Prefer Q4_K_M quants on this device; Q8 only for sub-0.5B models.
- Match context size to RAM: 2048 first, larger only with headroom.

## Verification
A model-ops task is complete when the model file exists with its full
expected size, the dashboard reports it installed, and a success benchmark
exists — or a clear diagnosis explains why not.
