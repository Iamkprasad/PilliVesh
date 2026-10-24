"""Curated model catalog for PilliVesh.

Allow-list only: the downloader and API refuse anything not listed here.
All entries are small instruction-tuned GGUFs verified to exist upstream
and suitable for a ~2 GB RAM phone. No shell, no arbitrary URLs.

Local models (regular .gguf files or valid symlinks resolving to regular
.gguf files) in the approved models directories are discovered at runtime
and appended to the catalog without download URLs.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT / "models"
HANDY_COMPUTER_MODELS_DIR = Path(
    "/data/data/com.termux/files/home/storage/shared/HandyComputer/models"
)
APPROVED_MODEL_DIRS = (MODELS_DIR, HANDY_COMPUTER_MODELS_DIR)

CATALOG = [
    {
        "id": "smollm2-360m-q8",
        "name": "SmolLM2 360M",
        "quant": "Q8_0",
        "repo": "HuggingFaceTB/SmolLM2-360M-Instruct-GGUF",
        "filename": "smollm2-360m-instruct-q8_0.gguf",
        "url": (
            "https://huggingface.co/HuggingFaceTB/SmolLM2-360M-Instruct-GGUF"
            "/resolve/main/smollm2-360m-instruct-q8_0.gguf"
        ),
        "size_mb": 386,
        "min_ram_mb": 1000,
        "context": 8192,
        "notes": "Smallest download. Best first model for this phone.",
    },
    {
        "id": "qwen2.5-0.5b-q4km",
        "name": "Qwen2.5 0.5B",
        "quant": "Q4_K_M",
        "repo": "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
        "filename": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "url": (
            "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF"
            "/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf"
        ),
        "size_mb": 400,
        "min_ram_mb": 1200,
        "context": 8192,
        "notes": "Good balance of size and quality. Apache-2.0 license.",
    },
    {
        "id": "llama-3.2-1b-q4km",
        "name": "Llama 3.2 1B",
        "quant": "Q4_K_M",
        "repo": "bartowski/Llama-3.2-1B-Instruct-GGUF",
        "filename": "Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "url": (
            "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF"
            "/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf"
        ),
        "size_mb": 800,
        "min_ram_mb": 1800,
        "context": 131072,
        "notes": "Largest of the three. Needs ~1.8 GB free RAM.",
    },
    {
        "id": "gemma-3-1b-it-heretic-q4km",
        "name": "Gemma 3 1B IT Heretic",
        "quant": "Q4_K_M",
        "repo": "mradermacher/gemma-3-1b-it-heretic-abliterated-uncensored-GGUF",
        "filename": "gemma-3-1b-it-heretic-abliterated-uncensored.Q4_K_M.gguf",
        "url": (
            "https://huggingface.co/mradermacher/"
            "gemma-3-1b-it-heretic-abliterated-uncensored-GGUF"
            "/resolve/main/"
            "gemma-3-1b-it-heretic-abliterated-uncensored.Q4_K_M.gguf"
        ),
        "size_mb": 806,
        "min_ram_mb": 1200,
        "context": 8192,
        "notes": "Abliterated uncensored Gemma 3 1B. Q4_K_M quant.",
    },
]


def _is_safe_gguf(path):
    """Return True if path is a regular .gguf file or a symlink resolving to one."""
    try:
        if not path.is_file():
            return False
        if path.suffix.lower() != ".gguf":
            return False
        # Resolve symlinks and verify target is a regular file.
        resolved = path.resolve()
        if not resolved.is_file():
            return False
        if resolved.suffix.lower() != ".gguf":
            return False
        # Ensure resolved path is within an approved directory.
        for approved in APPROVED_MODEL_DIRS:
            try:
                resolved.relative_to(approved.resolve())
                return True
            except ValueError:
                continue
        return False
    except (OSError, ValueError):
        return False


def _local_model_entry(path):
    """Build a catalog entry for a locally discovered GGUF file."""
    resolved = path.resolve()
    size_bytes = resolved.stat().st_size
    size_mb = max(1, size_bytes // (1024 * 1024))
    # Derive a readable name from the filename.
    stem = resolved.stem
    name = stem.replace("_", " ").replace("-", " ").title()
    # Derive quant from filename if possible.
    quant = "Unknown"
    lower = stem.lower()
    for q in ("q8_0", "q4_k_m", "q4_0", "q5_k_m", "q3_k_m", "q6_k"):
        if q in lower:
            quant = q.upper().replace("_", "_")
            break
    return {
        "id": f"local-{stem.lower().replace(' ', '-').replace('_', '-')}",
        "name": name,
        "quant": quant,
        "repo": "local",
        "filename": resolved.name,
        "url": None,
        "size_mb": size_mb,
        "min_ram_mb": max(512, size_mb + 256),
        "context": 8192,
        "notes": "Local model (no download).",
        "local": True,
        "path": str(resolved),
    }


def _discover_local_models():
    """Discover local GGUF models in approved directories.

    Only regular .gguf files or valid symlinks resolving to regular .gguf
    files inside approved directories are accepted.  Broken symlinks,
    directories, and path-traversal attempts are rejected.
    """
    found = []
    seen_ids = set()
    for approved in APPROVED_MODEL_DIRS:
        try:
            if not approved.exists():
                continue
            for entry in sorted(approved.iterdir()):
                # Reject path traversal: name must be a simple basename.
                if entry.name != entry.name.strip() or ".." in entry.name or "/" in entry.name:
                    continue
                if not _is_safe_gguf(entry):
                    continue
                local_entry = _local_model_entry(entry)
                if local_entry["id"] in seen_ids:
                    continue
                seen_ids.add(local_entry["id"])
                found.append(local_entry)
        except (OSError, ValueError):
            continue
    return found


def list_models():
    """Return catalog models including locally discovered ones."""
    result = [dict(entry) for entry in CATALOG]
    # Avoid duplicates: skip local entries whose filename matches a catalog entry.
    catalog_filenames = {e["filename"] for e in result}
    for local in _discover_local_models():
        if local["filename"] not in catalog_filenames:
            result.append(local)
    return result


def get_model(model_id):
    for entry in list_models():
        if entry["id"] == model_id:
            return dict(entry)
    raise ValueError(f"Unknown model id: {model_id}")


if __name__ == "__main__":
    for entry in list_models():
        print(f"{entry['id']}: {entry['name']} {entry['quant']} "
              f"~{entry['size_mb']} MB"
              + (" (local)" if entry.get("local") else ""))