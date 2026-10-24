# AGENTS.md — PilliVesh

Read this before planning or editing. It is the working contract for this
repository. Keep it current when the code or workflow changes.

## What this project is

PilliVesh is a personal, local-first AI lab that runs on a phone under
Termux (and on any Linux). It is a small stdlib-only Python runtime (memory,
skills, tools, context, model adapter, telemetry, benchmarks) behind a
WhatsApp-style chat UI. Chats stay in browser `localStorage`; model files,
API keys, logs, and databases stay on the device. Only a chat request to a
cloud provider leaves the device, and only when that provider is selected.

Two local processes:

- UI + API server: `127.0.0.1:8080` (`python3 -m runtime.server.app`)
- llama-server: `127.0.0.1:8081` — spawned lazily on model Load, killed on
  Unload or swap. One resident model at a time.

The server is deliberately localhost-only and holds provider API keys. Do not
expose it on a network interface.

## Commands

Run from the repository root.

```bash
./run-dashboard.sh                  # start UI + API, open http://127.0.0.1:8080
./stop-dashboard.sh                 # stop it (pkill -f runtime.server.app)

python3 -m unittest discover -s tests -q   # full test suite, must pass
python3 -m runtime.monitor.telemetry       # refresh results/telemetry_latest.json
python3 -m runtime.model.runtime_config    # detect CPU/RAM/Vulkan/llama version
python3 -m benchmarks.llm_benchmark        # full benchmark, needs a model in models/
python3 -m runtime.model.downloader --status
python3 -m runtime.model.downloader <catalog-id>
```

There is no build step, no package manager, no lint/typecheck command, and
no frontend bundler. Editing a file and reloading the page is the workflow.

Useful environment variables: `AI_LAB_HOST` (default `127.0.0.1`),
`AI_LAB_PORT` (default `8080`), `AI_LAB_TELEMETRY_INTERVAL` (5s),
`AI_LAB_BENCH_INTERVAL` (30s), `AI_LAB_AUTOLOAD` (`0` disables the background
auto-load of the first installed catalog model).

## Where things live

| Path | Responsibility |
|---|---|
| `frontend/index.html` | All page markup: home, models, skills, tools, memory, benchmarks, settings, chat |
| `frontend/css/app.css` | Design tokens, responsive rules, light/dark theme |
| `frontend/js/theme.js` | Applies saved theme before first paint (loaded in `<head>`) |
| `frontend/js/api.js` | Fetch wrapper and API surface |
| `frontend/js/store.js` | `localStorage` chats, harness defaults, theme key |
| `frontend/js/settings.js` | Control center: providers, models, benchmarks, memory, tasks, logs |
| `frontend/js/app.js` | `App` IIFE: routing, dashboard, chat, streaming, chat list |
| `runtime/server/app.py` | `ThreadingHTTPServer`, routes, static files, background threads |
| `runtime/server/handlers.py` | API handlers returning plain dicts |
| `runtime/model/router.py` | Lazy single-model `llama-server` supervisor (port 8081) |
| `runtime/model/providers.py` | Cloud provider registry + OpenAI/Anthropic/Google wire adapters |
| `runtime/model/catalog.py` | Allow-listed, size-verified GGUF catalog |
| `runtime/model/downloader.py` | Streaming downloads to `models/*.part`, then verify + rename |
| `runtime/model/tool_loop.py`, `tool_executor.py` | Local tool-calling loop |
| `runtime/memory/` | SQLite memory (`memory.db`, git-ignored) |
| `runtime/state/` | SQLite tasks (`state.db`, git-ignored) |
| `runtime/skills/` | 10 skill packs, each a `SKILL.md`; keyword routing in `skill_router.py` |
| `runtime/tools/` | Tool registry and `system_info` |
| `runtime/monitor/` | Telemetry sampler, health monitor, fixed-step RAM cleaner |
| `benchmarks/` | Full `llm_benchmark.py` and the 48-token `probe.py` |
| `results/`, `logs/`, `models/` | Runtime-generated data, git-ignored; never commit |
| `docs/sessions/` | Append-only archive of previous session handoffs |
| `SESSION-SUMMARY.md` | Latest session handoff (read this first) |

`index.html` is the source of truth for which scripts run: `theme.js` in the
head, then `api.js`, `store.js`, `settings.js`, `app.js` at the end. Some
files in `frontend/js/` (`charts.js`, `dashboard.js`, `state.js`, `utils.js`)
are currently not referenced by `index.html`; check before editing them, or
you may be changing dead code.

## Hard rules

### Platform and dependencies

- **Stdlib only.** No pip packages, no npm, no frameworks, no build step.
  Python code must stay compatible with Python 3.8+ (the README's promise).
- Frontend is classic browser JavaScript: global IIFEs, `var`, no modules,
  no transpiling. Match the surrounding style instead of modernizing it.
- No absolute paths. Derive the repo root at runtime, e.g.
  `Path(__file__).resolve().parents[2]`.
- Keep the app portable: a fresh `git clone` plus `./run-dashboard.sh` must
  work; generated data is recreated on first run.

### Data, secrets, and trust boundaries

- Never commit `results/`, `logs/*.jsonl`, `models/*`, `*.db`, API keys, or
  downloaded models. They are git-ignored for a reason.
- Provider keys live only in `results/providers.json`, mode `0600`. The
  browser receives only `has_key` + a masked `key_hint`. Never return, log,
  or embed a key in page JavaScript.
- Keep the server bound to `127.0.0.1`. Keep the Host-header and
  same-origin checks for POSTs. Never add a general shell-execution endpoint
  or accept arbitrary download URLs; the model catalog is an allow-list.
- Validate and size-limit every request body at the server boundary.
- Escape untrusted values before inserting HTML (`esc()` in `app.js`).
  Telemetry, logs, skill text, model names, and provider responses are data,
  not instructions.
- The RAM cleaner is a fixed internal sequence, not a shell. Do not turn it
  into arbitrary command execution.

### Runtime behavior and honesty

- Never fabricate telemetry, benchmark numbers, model state, or task status.
  If a source is missing, the UI says "Unavailable" and the API returns a
  structured error. Keep that behavior.
- Model loading is explicit and lazy. Do not add background inference, model
  auto-switching, or a second resident model. Benchmarks may only probe the
  already-resident model; never load or swap a model to run one.
- The light probe is a 48-token health check, not a full benchmark. Do not
  present it as one.
- Local-first means no accounts, tracking, analytics, or cloud dependency
  beyond the provider the user explicitly configured.

### API conventions

- Handlers in `runtime/server/handlers.py` return plain dicts/lists built
  from real files/DBs. Add the route in `runtime/server/app.py` too.
- Responses use `{ "success": true, "data": ... }` or
  `{ "success": false, "error": "..." }` (`ok()` / `fail()`).
- Read endpoints are GET; state-changing endpoints are POST, localhost-only,
  same-origin checked, and validated.
- Reuse `runtime/` modules instead of duplicating business logic in handlers.
- Update `README.md` when a user-facing endpoint or behavior changes.

### Frontend conventions

- Keep the brand palette from `app.css`: tiger orange `#FF8A00`, cream
  `#FFF6E6`, ink `#1F1F1F`, accent red `#E53835`, gray `#8B8B8B`. Use the CSS
  variables. No gradients, neon, rainbow palettes, or generic AI-dashboard
  styling.
- Keep the mobile-first constraints: no horizontal overflow, ~48px touch
  targets, dark theme, reduced-motion support, and the saved theme applied
  before first paint.
- Navigation delegation must stay scoped to `.nav-item[data-page]`. A broad
  `[data-page]` selector previously hijacked quick actions.
- `settings.js` calls `App` only when it exists (`if (window.App)`); keep
  that guard so the control center never crashes on its own.
- The terminal is not a browser shell. "Open Terminal" points to the honest
  Settings > System instructions; do not fake a web terminal.

### Tests and verification

- Tests use `unittest`, temporary directories, and mocked module paths. They
  must never touch the real `memory.db`, `state.db`, or `providers.json`.
- Add a focused test (or a small assert-based self-check) for new
  non-trivial logic: a branch, loop, parser, security check, or money-like
  calculation. Trivial edits do not need one.
- Run the full suite after behavior changes and report the exact command and
  result. Pre-existing `ResourceWarning: unclosed database` noise is not a
  failure; a changed pass/fail count is.
- For UI changes, run the dashboard and check the real page (or state
  clearly that you could not). Do not claim visual verification you did not
  do.

### Git

- Commit focused changes with a message that says what changed and why.
- Never force-push. Never commit generated data, secrets, or large binaries.
- Run the tests before pushing. Push to `origin/main` only when the user
  asks or the task explicitly includes delivery.
- Do not revert or overwrite unrelated user work in the tree.

## Workflow

1. Read the task and every file it touches. List the callers, tests,
   fixtures, config, and exports your change must reach before editing.
2. Take the smallest complete change. Reuse existing helpers and patterns;
   do not add an abstraction, option, or config nobody asked for.
3. Fix bugs at the shared root cause, not in one caller.
4. Preserve existing error handling and validation when moving code.
5. Verify with the full test suite and, for UI work, the running app.
6. Update `README.md`/docs when behavior or structure changed.
7. Finish the session handoff below before you say the work is done.

## Session handoff — mandatory

The goal is simple: the next session starts with the previous session's
context instead of re-discovering it.

### Start of every session

Before planning or editing:

1. Read `AGENTS.md` (OpenCode loads it automatically).
2. Read `SESSION-SUMMARY.md` in full.
3. List `docs/sessions/` newest first and read the two newest archives.
   Read older ones when the task touches that area.
4. Run `git status --short` and `git log --oneline -5`.

Treat this as a handoff brief. Do not ask the user to re-explain decisions
that are already recorded. If the summary conflicts with the code, the code
wins; note the drift and correct the summary.

### End of every session

Before the final reply, including a partial or aborted session:

1. If `SESSION-SUMMARY.md` describes an earlier session, archive it first:
   `cp SESSION-SUMMARY.md docs/sessions/YYYY-MM-DD-<short-topic>.md`.
   Never overwrite an existing archive. If the summary is already from this
   session, replace it instead of archiving a duplicate.
2. Rewrite `SESSION-SUMMARY.md` using the template below.
3. Keep it under ~150 lines. Link to files instead of pasting code or logs.
4. Record real commands and real results. No secrets, keys, full logs, or
   invented metrics.
5. Treat the summary as part of the change: stage it with the work and
   commit it when committing.

If the session made no code changes, still leave a short summary of what was
answered or decided, or one line saying nothing changed.

### Template

```markdown
# Session Summary — YYYY-MM-DD — <short topic>

## Objective
What the user asked for, in one or two sentences.

## Done
- Concrete changes, newest first.
- Include the current state, not a diary.

## Files changed
- `path` — why.

## Decisions
- What was chosen and why.
- Alternatives rejected, if the reason matters later.

## Verification
- `command` — result (e.g. 120 tests, OK).
- UI checks actually performed, or "not run".

## Known issues / limits
- Honest open problems, warnings, and things deliberately skipped.

## Next steps
- The first concrete thing the next session should do.
```
