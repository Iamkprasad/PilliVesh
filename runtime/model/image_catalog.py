"""Curated, allow-listed SD1.5 image models for PilliVesh's /image page.

Only ids in this list can be downloaded, loaded or generated from. No arbitrary
URLs are accepted from the browser (matches AGENTS.md and the chat catalog).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT / "models" / "image"

HF = "https://huggingface.co"

CATALOG = [
    {
        "id": "sd15-q8",
        "name": "SD 1.5 Q8 (GGUF)",
        "filename": "stable-diffusion-v1-5-pruned-emaonly-Q8_0.gguf",
        "repo": "second-state/stable-diffusion-v1-5-GGUF",
        "url": (
            HF + "/second-state/stable-diffusion-v1-5-GGUF/resolve/main/"
            "stable-diffusion-v1-5-pruned-emaonly-Q8_0.gguf"
        ),
        "source_url": HF + "/second-state/stable-diffusion-v1-5-GGUF",
        "size_mb": 1100,
        "min_ram_mb": 2500,
        "width": 256,
        "height": 256,
        "steps": 10,
        "cfg": 7.0,
        "license": "CreativeML OpenRAIL-M",
        "notes": "First model to install. ~1.1 GB, best quality/size on phone CPU.",
        "sha256": None,
    },
    {
        "id": "sd15-q4km",
        "name": "SD 1.5 Q4_K_M (GGUF)",
        "filename": "stable-diffusion-v1-5-pruned-emaonly-Q4_K_M.gguf",
        "repo": "second-state/stable-diffusion-v1-5-GGUF",
        "url": (
            HF + "/second-state/stable-diffusion-v1-5-GGUF/resolve/main/"
            "stable-diffusion-v1-5-pruned-emaonly-Q4_K_M.gguf"
        ),
        "source_url": HF + "/second-state/stable-diffusion-v1-5-GGUF",
        "size_mb": 700,
        "min_ram_mb": 1800,
        "width": 256,
        "height": 256,
        "steps": 10,
        "cfg": 7.0,
        "license": "CreativeML OpenRAIL-M",
        "notes": "Smaller fallback for low free RAM.",
        "sha256": None,
    },
]

ALLOWED_SIZES = (128, 256, 384, 512)


def list_models():
    """Return catalog entries with installed state."""
    result = []
    for entry in CATALOG:
        item = dict(entry)
        path = MODELS_DIR / entry["filename"]
        item["installed"] = path.is_file()
        item["local_size_mb"] = (path.stat().st_size // (1024 * 1024)
                                 if path.is_file() else 0)
        result.append(item)
    return result


def get_model(model_id):
    for entry in CATALOG:
        if entry["id"] == model_id:
            return dict(entry)
    raise ValueError("Unknown image model id: %s" % model_id)


def model_path(model_id):
    entry = get_model(model_id)
    return MODELS_DIR / entry["filename"]


def is_safe_download_url(url):
    """Never fetch anything other than a curated HF GGUF file."""
    if not isinstance(url, str) or not url.startswith(HF + "/"):
        return False
    if not url.lower().split("?")[0].endswith(".gguf"):
        return False
    return ".." not in url and "\\" not in url


if __name__ == "__main__":
    for entry in list_models():
        print("%s: %s %s (~%s MB)" % (
            entry["id"], entry["name"],
            "installed" if entry["installed"] else "not installed",
            entry["size_mb"],
        ))
