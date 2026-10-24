# Session Summary — 2026-10-24 — Agent rules + session handoff

## Objective
Add repository-specific agent rules and a mandatory session handoff protocol,
so every new session reads the previous session's work before starting.

## Done
- Added `AGENTS.md`: project map, commands, hard rules (stdlib-only,
  localhost/security, honest telemetry, lazy model policy, API/frontend
  conventions, tests, git) and the session handoff protocol.
- Archived the previous frontend-redesign handoff to
  `docs/sessions/2026-10-24-frontend-redesign.md`.
- Rewrote this file as the rolling handoff and added the summary template to
  `AGENTS.md`.
- Updated the README project layout to mention `AGENTS.md`,
  `SESSION-SUMMARY.md`, `docs/sessions/`, and `tests/`.
- Committed and pushed the prior uncommitted redesign work together with
  these docs.

## Files changed
- `AGENTS.md` — new working contract and session protocol.
- `docs/sessions/2026-10-24-frontend-redesign.md` — archived prior summary.
- `SESSION-SUMMARY.md` — this handoff.
- `README.md` — project layout.
- Previous session's redesign files (frontend, runtime, tests, docs, brand
  assets) are included in the same push; see `git log -1 --stat`.

## Decisions
- Used `AGENTS.md`, because OpenCode auto-loads that filename (not
  `agent.md`).
- Kept one rolling `SESSION-SUMMARY.md` plus an append-only
  `docs/sessions/` archive: the next session reads the latest handoff and
  the two newest archives, avoiding an ever-growing context file.
- Made the handoff mandatory for partial sessions too, so stopping mid-task
  still leaves a usable state.

## Verification
- `python3 -m unittest discover -s tests -q` — 120 tests, OK
  (pre-existing `ResourceWarning: unclosed database` noise).
- Docs-only change otherwise; the UI was not re-run this session.

## Known issues / limits
- The redesign work committed in this push was already uncommitted in the
  tree at session start; it was verified by the test suite but not visually
  reviewed in this session.
- `frontend/js/charts.js`, `dashboard.js`, `state.js`, and `utils.js` are
  currently not referenced by `index.html`; do not assume they run.
- Session handoff is a rule, not automation; a session that skips the final
  summary will break continuity.

## Next steps
- Run `./run-dashboard.sh` and visually verify the redesigned pages before
  the next UI change.
- If the previous redesign needs follow-up, read
  `docs/sessions/2026-10-24-frontend-redesign.md` first.
