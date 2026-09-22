# Git-GitHub Skill

## Purpose
Keep the PilliVesh repository clean, committable, and portable via git.

## Activate When
- Committing or pushing changes
- Reviewing what will be committed
- Managing branches, remotes, or history
- Preparing a repo for cloning on another phone

## Workflow
1. Inspect first: `git status`, `git diff`, `git log --oneline -10`.
2. Stage only intended files; never commit secrets, databases (`*.db`),
   generated snapshots (`results/`, `logs/`), or downloaded models.
3. Write a concise commit message describing the change, not the process.
4. Push to the correct remote/branch; verify with `git status` after.
5. After cloning fresh, confirm `./run-dashboard.sh` regenerates runtime data.

## Rules
- Do not rewrite published history (no force-push, no amend of pushed commits)
  unless explicitly requested.
- Do not commit credentials, tokens, or personal data; scan diffs for them.
- Do not commit `__pycache__`, `.venv`, or editor/OS files (`.gitignore`
  covers them — keep it that way).
- One logical change per commit.

## Verification
A git task is complete when `git status` shows the expected tree state and
`git log` shows the new commit (for commits), or the remote reflects the push.
