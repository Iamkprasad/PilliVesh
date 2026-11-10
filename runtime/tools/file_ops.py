"""Read-only file and directory inspection tools.

All paths are bounded to the repository root so the model cannot read
arbitrary files on the device. No shell, no subprocess, no write access.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _safe_path(path):
    """Resolve `path` relative to ROOT and reject anything outside it."""
    if not path or not isinstance(path, str):
        raise ValueError("path is required")
    target = (ROOT / path).resolve()
    try:
        target.relative_to(ROOT.resolve())
    except ValueError:
        raise ValueError("path escapes the project root")
    return target


def file_read(path):
    """Read a text file inside the project root. Returns (content, error)."""
    try:
        target = _safe_path(path)
    except ValueError as e:
        return "", str(e)
    if not target.is_file():
        return "", "file not found: " + path
    try:
        return target.read_text(encoding="utf-8", errors="replace"), None
    except OSError as e:
        return "", "cannot read " + path + ": " + str(e)


def list_dir(path="."):
    """List entries in a directory inside the project root. Returns (entries, error)."""
    try:
        target = _safe_path(path if path else ".")
    except ValueError as e:
        return [], str(e)
    if not target.is_dir():
        return [], "directory not found: " + str(path)
    try:
        entries = []
        for child in sorted(target.iterdir()):
            entries.append({
                "name": child.name,
                "type": "dir" if child.is_dir() else "file",
                "size": child.stat().st_size if child.is_file() else None,
            })
        return entries, None
    except OSError as e:
        return [], "cannot list " + str(path) + ": " + str(e)


if __name__ == "__main__":
    content, err = file_read("README.md")
    if err:
        print("ERR:", err)
    else:
        print(content[:200])
    entries, err = list_dir("runtime")
    if err:
        print("ERR:", err)
    else:
        for e in entries[:5]:
            print(e["type"], e["name"], e.get("size"))
