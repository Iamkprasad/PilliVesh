"""Best-effort RAM cleanup — fixed steps only, never arbitrary shell.

Every step is hard-coded below. The API only ever runs these operations;
there is no way to pass in a command. Failures are reported honestly so the
dashboard can show what actually happened on this device (Termux without
root cannot drop caches or kill other apps' processes on stock Android).
"""
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT / "models"

# Skip tiny files — not worth touching.
MIN_CACHE_FILE_MB = 50


def _memory():
    from runtime.monitor.telemetry import memory_info
    return memory_info()


def _run(cmd, timeout=8):
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, check=False,
        )
        out = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
        return r.returncode, out
    except FileNotFoundError:
        return 127, f"not found: {cmd[0]}"
    except Exception as e:
        return -1, str(e)


def _step_sync():
    try:
        os.sync()
        return True, "flushed dirty pages"
    except Exception as e:
        return False, str(e)


def _step_drop_caches():
    """Needs root; fails cleanly on stock Termux/Android."""
    try:
        Path("/proc/sys/vm/drop_caches").write_text("3\n", encoding="ascii")
        return True, "page cache dropped"
    except Exception as e:
        return False, str(e)


def _step_android_kill_background():
    """Ask Android to kill cached/background processes only (not foreground).

    Uses /system/bin/am when PATH lacks `am`. May fail without shell
    permissions — reported as-is.
    """
    for am in ("/system/bin/am", "am"):
        code, out = _run([am, "kill-all"], timeout=10)
        if code == 0:
            return True, (out or "background processes cleared")[:200]
        if code != 127:
            # Binary exists but rejected (SecurityException, etc.)
            return False, (out or f"{am} exit {code}")[:200]
    return False, "am not available"


def _step_release_model_cache():
    """Drop page cache for large local .gguf files (no root; posix_fadvise)."""
    if not hasattr(os, "posix_fadvise") or not hasattr(os, "POSIX_FADV_DONTNEED"):
        return False, "posix_fadvise unavailable"
    released, freed_est = 0, 0
    try:
        if not MODELS_DIR.exists():
            return True, "no models directory"
        for p in sorted(MODELS_DIR.iterdir()):
            if not p.is_file() or p.suffix.lower() not in (".gguf", ".part"):
                continue
            try:
                size = p.stat().st_size
            except Exception:
                continue
            if size < MIN_CACHE_FILE_MB * 1024 * 1024:
                continue
            try:
                fd = os.open(p, os.O_RDONLY)
                try:
                    os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
                finally:
                    os.close(fd)
                released += 1
                freed_est += size
            except Exception:
                continue
    except Exception as e:
        return False, str(e)
    if released:
        mb = freed_est // (1024 * 1024)
        return True, f"{released} file(s), ~{mb} MB cache released"
    return True, "no large model files to release"


def _step_reap_zombies():
    """SIGKILL defunct (Z state) children so the parent can reap them."""
    killed = 0
    try:
        r = subprocess.run(
            ["ps", "-A", "-o", "pid=,stat=,comm="],
            capture_output=True, text=True, timeout=5, check=False,
        )
        for line in (r.stdout or "").splitlines():
            parts = line.split(None, 2)
            if len(parts) < 2 or not parts[1].startswith("Z"):
                continue
            pid = int(parts[0])
            if pid == os.getpid():
                continue
            try:
                os.kill(pid, 9)
                killed += 1
            except Exception:
                pass
    except Exception:
        pass
    return True, f"{killed} zombie(s)"


def _step_kill_stale_inferencers():
    """Kill leftover llama-cli / benchmark processes from prior runs."""
    killed = 0
    try:
        r = subprocess.run(
            ["pgrep", "-f", "llama-cli"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if not line.isdigit():
                continue
            pid = int(line)
            if pid == os.getpid():
                continue
            try:
                os.kill(pid, 9)
                killed += 1
            except Exception:
                pass
    except Exception:
        pass
    return True, f"{killed} stale llama-cli"


def free_ram():
    """Run all fixed cleanup steps. Returns before/after memory + per-step results."""
    before = _memory()
    actions = []

    steps = [
        ("sync", _step_sync),
        ("release_model_cache", _step_release_model_cache),
        ("reap_zombies", _step_reap_zombies),
        ("kill_stale_inferencers", _step_kill_stale_inferencers),
        ("android_kill_background", _step_android_kill_background),
        ("drop_caches", _step_drop_caches),
    ]
    for name, fn in steps:
        t0 = time.time()
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, str(e)
        actions.append({
            "name": name,
            "ok": bool(ok),
            "detail": detail,
            "ms": round((time.time() - t0) * 1000, 1),
        })

    # Small pause so the kernel can reclaim before we sample.
    time.sleep(0.3)
    after = _memory()

    # Refresh telemetry snapshot so the dashboard reflects new numbers.
    try:
        from runtime.monitor.telemetry import save as _save
        _save()
    except Exception:
        pass

    before_av = before.get("available_mb")
    after_av = after.get("available_mb")
    freed = None
    if isinstance(before_av, int) and isinstance(after_av, int):
        freed = after_av - before_av

    return {
        "before": before,
        "after": after,
        "freed_mb": freed,
        "actions": actions,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(free_ram(), indent=2))
