# PilliVesh

My personal, portable, local-first AI lab that lives entirely on my phone.

PilliVesh is a small local AI runtime (memory, skills, tools, context, model
adapter, telemetry, benchmarks) plus a mobile-first control-center dashboard.
No cloud, no accounts, no build step. It runs on Termux/Android and is designed
to be cloned onto another phone and work with two scripts.

## Quick start

### Requirements

| Need              | Details                                                        | Required? |
|-------------------|----------------------------------------------------------------|-----------|
| Android + Termux (or any Linux) | Primary target is a phone; works on tablet/desktop Linux too | Yes |
| Python 3.8+       | Stdlib only — zero pip packages to install                    | Yes |
| `git`             | To clone the repo (`pkg install git` on Termux)                | Yes |
| A browser         | Any modern mobile or desktop browser for the dashboard         | Yes |
| `llama-cli` (llama.cpp, Vulkan build) | GPU detection, version detection, benchmarks | Recommended — without it the dashboard still runs but shows GPU/model as unavailable |
| Free RAM ~2 GB+   | For running small local models; the dashboard itself needs almost nothing | For models only |
| Disk space        | ~5 MB for the repo; +1–4 GB free if you download a `.gguf` model | Model space as needed |

### Install & run

```bash
pkg install python git   # Termux only, once
git clone <your-repo-url> ai-lab
cd ai-lab
./run-dashboard.sh
# Open: http://127.0.0.1:8080
```

Stop it with `Ctrl+C`, or from another shell:

```bash
./stop-dashboard.sh
```

## What you get

- **Home** — CPU, RAM/swap with usage bars, GPU (Adreno/Vulkan), grouped
  thermals (CPU/GPU/Battery/Skin/DDR/NPU), runtime summary, benchmark status.
- **Runtime** — backend, `llama.cpp` version (auto-detected, never hard-coded),
  model state, raw GPU/Vulkan output, diagnostics.
- **Memory** — searchable SQLite-backed assistant memory
  (procedural / semantic / episodic / project).
- **Logs** — recent runtime events with type filters; click a row for details.
- **More** — skills (reads each skill's `SKILL.md`), registered tools, project
  tasks, model downloads, diagnostics, and server settings.
- **Inbuilt graphs** — dependency-free SVG charts (no chart library): CPU/GPU/
  battery thermals and RAM history on Home, benchmark history once a model
  runs. History accumulates in `results/telemetry_history.jsonl` and
  `results/benchmark_history.jsonl` automatically.
- **PWA-ready** — `manifest.json` + icon included; use your browser's
  "Add to Home screen" to install PilliVesh like a native app.
- **Export diagnostics** — one tap in Diagnostics copies (or downloads) a
  plain-text report of CPU/RAM/GPU/model state for sharing or debugging.
- **Free up RAM** — Home button runs a fixed cleanup: flush dirty pages,
  release page cache on large `.gguf` files, reap zombies, kill stale
  `llama-cli` leftovers, then best-effort `am kill-all` (background apps only).
  Each step reports success/failure honestly — stock Android without root
  cannot drop the global page cache.
- **Load / Unload model** — More → Models shows `[ LOAD ]` / `[ UNLOAD ]`
  (and a `[RESIDENT]` chip). Load spawns a lazy pure-CPU `llama-server` only
  when you ask; Unload kills it so idle battery drain is zero. One model
  resident at a time; loading another swaps cleanly. RAM is checked against
  each catalog entry's `min_ram_mb` first.
- **Chat** — Chat tab talks to the resident model through `POST /api/chat`
  (proxied to `llama-server` on `127.0.0.1:8081`). Clear history, open the
  llama Web UI, Enter to send. Status line tells you when nothing is loaded.
- **Color themes** — More → Settings picks Green / Pink / Yellow / Blue /
  Red phosphor themes (Terminal CLI style). Choice persists in
  `localStorage` and applies before first paint.
- **Live refresh** — telemetry re-polls every 5 seconds and updates in place;
  if a source disappears the UI shows an unavailable state instead of crashing.

Everything displayed is real data from the local runtime. When there is no
model, no benchmark, or no sensor, the UI says so honestly.

## Local API (localhost only)

The dashboard talks to a tiny stdlib HTTP server (`runtime/server/`):

| Endpoint            | Source                                  |
|---------------------|-----------------------------------------|
| `/api/telemetry`    | `results/telemetry_latest.json`         |
| `/api/benchmark`    | `results/benchmark_latest.json` + history |
| `/api/logs`         | `logs/runtime.jsonl`                    |
| `/api/memory`       | `runtime/memory/memory.db`              |
| `/api/skills`       | `runtime/skills/*/SKILL.md`             |
| `/api/tools`        | tool registry (`runtime/tools/`)        |
| `/api/tasks`        | `runtime/state/state.db`                |
| `/api/diagnostics`  | profile, `models/`, file presence       |
| `/api/models`       | catalog + installed + download + loaded |
| `/api/health`       | liveness probe                          |

Write endpoints (POST, still localhost-only): `/api/models/download`
(starts an allow-listed model download), `/api/models/load` (spawns a
battery-lazy `llama-server` for one catalog model — RAM-gated, swaps any
resident model), `/api/models/unload` (kills the process; stops the router
when the last model leaves), `/api/models/router/stop` (force-kill),
`/api/chat` (OpenAI-style messages, proxied to the resident model on
port 8081 — fails clearly when nothing is loaded), `/api/memory/free`
(best-effort RAM cleanup — fixed internal steps only, no shell input),
and `/api/server/stop` (shuts the dashboard down).
There is deliberately no remote control, no auth, and no general
shell-execution endpoint. It binds to `127.0.0.1` only.

Model load is intentionally lazy: nothing runs in the background until you
press **Load**, and **Unload** (or swapping models) kills `llama-server` so
the phone's battery is not drained while idle. Only one model is resident
at a time (`--models-max` equivalent). On this Termux build the server runs
pure-CPU (`-dev none`) because the packaged Vulkan backend segfaults while
loading GGUFs.

## Handy runtime commands

```bash
python3 -m runtime.model.runtime_config   # detect CPU/RAM/Vulkan/llama version
python3 -m runtime.monitor.telemetry      # refresh results/telemetry_latest.json
python3 -m runtime.monitor.monitor        # health check + event log
python3 -m benchmarks.llm_benchmark       # benchmark (needs a model in models/)
python3 -m runtime.orchestrator           # run the runtime once (system_info demo)
./bin/system-info.sh                      # full device report
```

Drop a `.gguf` model into `models/` and the runtime, benchmark, and dashboard
pick it up automatically (`model_downloaded` is detected, not configured).

### Models (curated, phone-sized)

No hunting for download links — PilliVesh ships an allow-listed catalog
(`runtime/model/catalog.py`, all entries verified upstream). Install from the
dashboard's More → Models screen, or from the shell:

```bash
python3 -m runtime.model.downloader smollm2-360m-q8   # ~386 MB, smallest first
python3 -m runtime.model.downloader --status          # progress / state
```

| Model | Quant | Size | Needs free RAM |
|---|---|---|---|
| SmolLM2 360M | Q8_0 | ~386 MB | ~1.0 GB |
| Qwen2.5 0.5B | Q4_K_M | ~400 MB | ~1.2 GB |
| Llama 3.2 1B | Q4_K_M | ~800 MB | ~1.8 GB |

Downloads stream to `models/*.part`, are size-verified, then moved into place;
only catalog ids are accepted (arbitrary URLs are refused). After a download
the runtime profile refreshes and the dashboard flips to "Installed".

### Skills

10 skills live in `runtime/skills/` (each a `SKILL.md`, auto-discovered):
coding, debugging, linux, research, planning, reasoning, plus termux-android,
benchmarking, git-github, and model-ops. Keyword routing lives in
`skill_router.py` — add keywords there when you add a skill.

## Project layout

```text
.
├── frontend/            # dashboard (plain HTML/CSS/JS, no framework)
│   ├── index.html
│   ├── css/app.css
│   └── js/{api,state,utils,dashboard,charts,app}.js
├── runtime/             # the AI runtime the dashboard observes
│   ├── server/          # localhost API + static file server
│   ├── memory/          # SQLite memory (db is local-only, git-ignored)
│   ├── state/           # SQLite tasks (local-only, git-ignored)
│   ├── skills/          # skill packs, each with SKILL.md
│   ├── tools/           # tool registry (system_info + future tools)
│   ├── model/           # adapter, interface, runtime config detection
│   ├── monitor/         # telemetry + health monitor
│   ├── context/         # context builder
│   └── orchestrator.py  # ties skills/tools/memory together
├── benchmarks/          # llm_benchmark.py (+ history jsonl at runtime)
├── results/             # generated snapshots (git-ignored)
├── logs/                # runtime.jsonl event log (git-ignored)
├── models/              # your .gguf files live here (git-ignored)
├── bin/                 # device/bench shell helpers
├── run-dashboard.sh
└── stop-dashboard.sh
```

## Portability notes

- No absolute paths in code — the repo root is always derived at runtime
  (`Path(__file__).resolve().parents[...]`).
- Generated data (`*.db`, `results/*.json`, `logs/*.jsonl`, `models/*`,
  `__pycache__`) is git-ignored; a fresh clone regenerates it on first run.
- To move phones: `git clone`, copy your `models/*.gguf` over, run
  `./run-dashboard.sh`. Done.

## Status

Personal project, built incrementally on-device. The dashboard is local-only:
read views, allow-listed model download/load, RAM cleanup, and chat against a
resident model — agents, remote access, and tuning controls are intentionally
not included.
