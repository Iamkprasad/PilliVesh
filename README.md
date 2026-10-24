# PilliVesh

My personal, portable, local-first AI lab that lives entirely on my phone.

PilliVesh is a small local AI runtime (memory, skills, tools, context, model
adapter, telemetry, benchmarks) behind a WhatsApp-style chat UI. Chat with a
local GGUF model or a cloud provider from the same screen; API keys stay on the
device. No accounts, no build step. It runs on Termux/Android and is designed to
be cloned onto another phone and work with two scripts.

## Quick start

### Requirements

| Need              | Details                                                        | Required? |
|-------------------|----------------------------------------------------------------|-----------|
| Android + Termux (or any Linux) | Primary target is a phone; works on tablet/desktop Linux too | Yes |
| Python 3.8+       | Stdlib only — zero pip packages to install                    | Yes |
| `git`             | To clone the repo (`pkg install git` on Termux)                | Yes |
| A browser         | Any modern mobile or desktop browser for the chat UI           | Yes |
| `llama-cli` (llama.cpp, Vulkan build) | GPU detection, version detection, benchmarks | Recommended — without it the UI still runs but shows GPU/model as unavailable |
| Free RAM ~2 GB+   | For running small local models; the UI itself needs almost nothing | For models only |
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

- **Chat-first UI** — WhatsApp-style chat list, bubbles, date chips, delivery
  ticks, search, copy, rename/clear/export/delete, and a mobile list/chat
  switch. Chats live in `localStorage`; nothing leaves the device.
- **Overview dashboard** — live RAM/available memory, the resident model and
  quant, the latest light-probe speed, and quick actions for a benchmark, a
  new chat, or model management, all above the chat search.
- **Control center** — Providers, Harness, Models, System, and Benchmarks in
  one drawer, reachable from the sidebar or the header.
- **Provider picker** — switch between the built-in local model and any saved
  cloud provider per chat. The header shows the active model and whether it is
  ready.
- **Cloud providers** — OpenAI-compatible APIs (OpenAI, OpenRouter, DeepSeek,
  Groq, Mistral, custom), Anthropic, and Google Gemini. Add a key in
  Control center → Providers; the local server proxies the request.
- **Local models** — download, load, unload, and benchmark phone-sized GGUF
  models in Control center → Models. One model is resident at a time; loading
  is lazy so idle battery drain is zero.
- **Harness controls** — system prompt, temperature, max tokens, and a
  read-only tool toggle (device inspection) in Control center → Harness.
- **System panel** — collapsible Device, Runtime controls, Tasks, Logs, and
  Memory cards in Control center → System: CPU/RAM/GPU telemetry, task
  counts and details, grouped/searchable event logs, searchable memory,
  free-RAM cleanup, and a stop-server button.
- **Streaming replies** — local and cloud responses stream token by token over
  NDJSON; the red button cancels a generation.
- **Light/dark theme** — saved in `localStorage` and applied before first paint.
- **PWA-ready** — `manifest.json` + icon included; use your browser's
  "Add to Home screen" to install PilliVesh like a native app.
- **Free up RAM** — a fixed cleanup: flush dirty pages, release page cache on
  large `.gguf` files, reap zombies, kill stale `llama-cli` leftovers, then
  best-effort `am kill-all` (background apps only). Each step reports
  success/failure honestly — stock Android without root cannot drop the global
  page cache.
- **Model efficiency / TPS** — while a model is resident the server runs a
  **light probe** every ~30s (`POST /v1/chat/completions`, up to 48 tokens)
  and records prompt/generation tok/s + latency into `results/benchmark_*`
  and `results/model_stats/<id>.jsonl`. **Run light benchmark** forces a
  sample; the Benchmarks tab shows readiness, the real result, history, and a
  comparison against the previous run of the same model. The 48-token probe
  is a quick health check, not a full benchmark suite, and PilliVesh never
  loads or switches a model just to run it.
- **Live refresh** — telemetry is sampled on the server every 5 seconds
  (daemon thread); if a source disappears the UI shows an unavailable state
  instead of crashing.
- **Auto-load model** — on start the first installed catalog model is loaded in
  the background (disable with `AI_LAB_AUTOLOAD=0`) so chat and the opencode
  local provider work without a manual Load.

Everything displayed is real data from the local runtime. When there is no
model, no benchmark, or no sensor, the UI says so honestly.

## Cloud providers & API keys

Open **Control center → Providers**, choose a preset (or fill in a custom
provider), and paste the API key. Supported wire formats:

- `openai` — OpenAI, OpenRouter, DeepSeek, Groq, Mistral, or any compatible
  endpoint.
- `anthropic` — Anthropic Messages API.
- `google` — Google Gemini `generateContent` API.

Keys are stored server-side in `results/providers.json` with mode `0600`. The
browser only receives a masked hint (`has_key`, `key_hint`); the key itself is
never returned to the browser and never embedded in page JavaScript. Chat
requests are proxied by the local server, which attaches the key. **Test**
makes one small request and reports the provider's own error message. **Delete**
removes the provider and its key. The radio button selects the default provider
for new chats; each chat can override it in the header picker.

`results/` is git-ignored, so keys are not committed accidentally. The server
binds to `127.0.0.1` and rejects cross-origin POSTs plus non-local Host headers
because it holds those keys; do not expose the port to your network.

## Using the local model in opencode

opencode is configured (global `~/.config/opencode/opencode.jsonc`) with an
OpenAI-compatible provider named **`llamacpp`** pointing at the resident
server:

- baseURL: `http://127.0.0.1:8081/v1` (model port **8081**, not the
  UI server’s 8080)
- default model: `llamacpp/smollm2-360m` (tool calling enabled)
- llama-server must be running — auto-load on startup, or press **Load** in
  Control center → Models

In the opencode TUI, pick the model with `/models` → **LLaMA.cpp (local)**
if the session is on a cloud provider. Only one model is resident at a time.

## Local API (localhost only)

The UI talks to a tiny stdlib HTTP server (`runtime/server/`):

| Endpoint            | Source                                  |
|---------------------|-----------------------------------------|
| `/api/telemetry`    | `results/telemetry_latest.json`         |
| `/api/benchmark`    | `results/benchmark_latest.json` + history |
| `/api/model-stats`  | summaries from `results/model_stats/`   |
| `/api/logs`         | `logs/runtime.jsonl` (`type`, `q`, `offset`, `limit`) |
| `/api/memory`       | `runtime/memory/memory.db` (created on first read) |
| `/api/skills`       | `runtime/skills/*/SKILL.md`             |
| `/api/tools`        | tool registry (`runtime/tools/`)        |
| `/api/tasks`        | `runtime/state/state.db` + status counts |
| `/api/diagnostics`  | profile, `models/`, file presence       |
| `/api/models`       | catalog + installed + download + loaded + per-model stats |
| `/api/providers`    | public provider list, presets, local model state, active id |
| `/api/health`       | liveness probe                          |

Write endpoints (POST, still localhost-only): `/api/models/download`
(starts an allow-listed model download), `/api/models/load` (spawns a
battery-lazy `llama-server` for one catalog model — RAM-gated, swaps any
resident model; fires a benchmark probe on success), `/api/models/unload`
(kills the process; stops the router when the last model leaves),
`/api/models/router/stop` (force-kill), `/api/chat` (OpenAI-style messages;
pass `"provider": "<id>"` to use a saved provider, or `"stream": true` for an
NDJSON token stream), `/api/providers` (`{"action": "save" | "delete" |
"active" | "test"}` — the key is accepted only on `save`), `/api/benchmark/run`
(light probe vs the resident model; optional `{"id"}`), `/api/memory/free`
(best-effort RAM cleanup — fixed internal steps only, no shell input), and
`/api/server/stop` (shuts the UI server down). Tasks have create/status/run/
result endpoints under `/api/tasks/`.

There is deliberately no remote control, no accounts, and no general
shell-execution endpoint. It binds to `127.0.0.1` only, rejects
cross-origin POSTs, and refuses non-local Host headers. Skills, tools,
diagnostics, and model stats remain
readable over the API even though the chat UI focuses on providers, models,
tasks, logs, and memory.

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

Drop a `.gguf` model into `models/` and the runtime, benchmark, and chat UI
pick it up automatically (`model_downloaded` is detected, not configured).

### Models (curated, phone-sized)

No hunting for download links — PilliVesh ships an allow-listed catalog
(`runtime/model/catalog.py`, all entries verified upstream). Install from the
Control center → Models screen, or from the shell:

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
the runtime profile refreshes and the UI flips to "Installed".

### Skills

10 skills live in `runtime/skills/` (each a `SKILL.md`, auto-discovered):
coding, debugging, linux, research, planning, reasoning, plus termux-android,
benchmarking, git-github, and model-ops. Keyword routing lives in
`skill_router.py` — add keywords there when you add a skill.

## Project layout

```text
.
├── frontend/            # chat UI (plain HTML/CSS/JS, no framework)
│   ├── index.html
│   ├── css/app.css
│   └── js/{api,store,settings,app,theme}.js
├── runtime/             # the AI runtime behind the UI
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
├── tests/               # stdlib unittest suite
├── docs/                # brand reference; docs/sessions/ archives past handoffs
├── AGENTS.md            # agent rules + session handoff protocol
├── SESSION-SUMMARY.md   # latest session handoff (read this first)
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

Personal project, built incrementally on-device. The UI and API are local-only:
allow-listed model download/load, RAM cleanup, and chat against a resident model
or a saved cloud provider. Remote access, accounts, and general shell execution
are intentionally not included.
