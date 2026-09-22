# Termux-Android Skill

## Purpose
Operate correctly on Android via Termux, where paths, packages, and hardware
access differ from desktop Linux.

## Activate When
- Installing packages or tools
- Accessing storage, sensors, or device info
- Debugging "works on Linux, fails on Termux" problems
- Managing background processes or battery behavior

## Workflow
1. Prefer `pkg` over `apt` for Termux-native packages.
2. Never hard-code `/data/data/com.termux/...` paths in project code; derive
   them at runtime (`$HOME`, `$PREFIX`, `Path(__file__)`).
3. Check hardware via `/sys/class/thermal`, `free`, `getprop` — not `/proc`
   assumptions from desktop guides.
4. Keep background work foreground-friendly: Termux may kill idle sessions;
   prefer short jobs and persistent logs over daemons.
5. Verify on-device; emulator behavior often differs (GPU, thermal zones).

## Rules
- Do not assume systemd, sudo, or root exists.
- Do not write outside the repo except to approved temp/cache locations.
- Keep storage use visible: models and datasets live in known directories
  (`models/`); check `df` before large downloads.
- Ask before changing system-level settings (governors, wakelocks).

## Verification
A Termux-Android task is complete when the exact commands have been run on
the device and their output inspected — not merely reasoned about.
