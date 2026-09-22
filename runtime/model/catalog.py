"""Curated model catalog for PilliVesh.

Allow-list only: the downloader and API refuse anything not listed here.
All entries are small instruction-tuned GGUFs verified to exist upstream
and suitable for a ~2 GB RAM phone. No shell, no arbitrary URLs.
"""

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
]


def list_models():
    return [dict(entry) for entry in CATALOG]


def get_model(model_id):
    for entry in CATALOG:
        if entry["id"] == model_id:
            return dict(entry)
    raise ValueError(f"Unknown model id: {model_id}")


if __name__ == "__main__":
    for entry in list_models():
        print(f"{entry['id']}: {entry['name']} {entry['quant']} "
              f"~{entry['size_mb']} MB")
