# Session Summary — 2026-11-21 — Image Studio build

## Objective
Build PilliVesh's new `/image` webapp from scratch (chat untouched), add a
local image engine and model download/search flow, and defer the full test run
to the end.

## Done
- Added standalone `image_web/` (mobile-first HTML/CSS/JS, no framework): model
  cards with Download/Load/Unload, Hugging Face search box, prompt/steps/size/
  seed form, NDJSON progress, result preview and localStorage gallery.
- Added `/api/image/*` routes in `runtime/server/app.py` and handlers in
  `runtime/server/handlers.py`: models, status, load, unload, download (+status),
  HF search, generate (NDJSON stream), cancel, and validated image file serving.
- Added `runtime/model/image_catalog.py` (allow-listed SD1.5 GGUF models),
  `image_router.py` (lazy `sd-server` supervisor on `127.0.0.1:8091`), and
  `image_adapter.py` (native `/sdcpp/v1/img_gen` → job polling → PNG).
- Added `bin/install-image-engine.sh` (build stable-diffusion.cpp CPU in Debian)
  and `bin/check-image.sh`.
- Documented the API (`docs/image-api.md`) and the reverse-engineering findings
  (`docs/local-dream-analysis.md`); updated README and AGENTS.md.
- Added 17 focused tests for catalog, router, adapter and handlers.
- Updated `.gitignore` for `bin/sd-server` and `results/images/`.

## Files changed
- `image_web/` — new webapp (index.html, css/app.css, js/api.js, js/app.js).
- `runtime/model/image_{catalog,router,adapter}.py` — new backend modules.
- `runtime/server/app.py`, `runtime/server/handlers.py` — routes and handlers.
- `bin/install-image-engine.sh`, `bin/check-image.sh`, `docs/image-api.md`,
  `docs/local-dream-analysis.md`, `README.md`, `AGENTS.md`, `.gitignore`.
- `tests/test_image_*.py` — four new test modules.

## Decisions
- Engine: `stable-diffusion.cpp` `sd-server`, CPU backend, installed as an
  external binary. local-webdream's own core is reference only (Android/Bionic
  + QNN; CC BY-NC).
- Downloads are catalog-id-only; HF search is read-only. No arbitrary URLs.
- Chat (`llama-server :8081`) and its frontend are unchanged.
- NPU is out of scope on SM8250/Hexagon V68 (conflicting maintainer answers,
  no public V68 LLM artifact, llama.cpp HTP needs v73+).

## Verification
- `python -m compileall -q <changed python files>` — OK.
- `python -m unittest discover -s tests -p 'test_image_*.py' -q` — 17 tests, OK.
- `python -m unittest discover -s tests -q` — 141 tests, 2 failures + 3 errors,
  all pre-existing Windows/platform issues (symlink privilege, POSIX 0600 mode,
  missing on-device GGUF, blocked web fetch).
- Filtered full run excluding those 5 platform tests — 153 tests, OK.
- Live HTTP smoke test on port 18080: `/api/health`, `/api/image/models`,
  `/api/image/status`, `/image/`, `/image/js/app.js` all returned 200.

## Known issues / limits
- Engine binary and model were not installed here (no phone in this workspace);
  `bin/install-image-engine.sh` is unverified on-device.
- Real generation/cancel flow against sd-server was tested with mocks only.
- CPU image generation on the 870 will be slow; default 256×256 / 10 steps.
- Archive of the previous summary: `docs/sessions/2026-11-21-image-studio-handoff.md`.

## Next steps
- On the phone: run `chmod +x bin/*.sh` once, then `bin/install-image-engine.sh`,
  download SD1.5 Q8 from the Models card, Load it, generate one 256×256 image,
  then unload and re-run the full suite (the 5 platform-specific tests should
  pass there).
