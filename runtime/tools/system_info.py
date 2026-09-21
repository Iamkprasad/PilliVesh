import os
import subprocess


def run():
    info = {}

    info["cpu_cores"] = os.cpu_count()

    try:
        result = subprocess.run(
            ["free", "-h"],
            capture_output=True,
            text=True,
            check=True,
        )
        info["memory"] = result.stdout
    except Exception as e:
        info["memory"] = f"error: {e}"

    try:
        result = subprocess.run(
            ["llama-cli", "--list-devices"],
            capture_output=True,
            text=True,
            check=False,
        )
        info["gpu"] = result.stdout
    except Exception as e:
        info["gpu"] = f"error: {e}"

    return info


if __name__ == "__main__":
    for key, value in run().items():
        print(f"\n=== {key.upper()} ===")
        print(value)
