"""Translation layer between PilliVesh and sd-server's native sdcpp API.

This is the only module that knows sd-server field names. If the native API
changes, fix it here and the webapp/backend stay untouched.
"""
import json
import time
import urllib.error
import urllib.request

from runtime.model import image_router

BASE = image_router.BASE

TERMINAL = ("completed", "failed", "cancelled")


def _request(method, path, payload=None, timeout=15.0):
    data = None
    headers = {"User-Agent": "PilliVesh/1.0"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            body = json.loads(raw.decode("utf-8", "replace")) if raw else {}
            return resp.status, body
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            body = json.loads(raw)
            msg = body.get("error") or body.get("message") or raw
        except Exception:
            msg = raw
        raise ValueError("sd-server %s: %s" % (e.code, str(msg)[:300]))


def build_request(params):
    """Build a native /sdcpp/v1/img_gen body from a PilliVesh request."""
    prompt = str(params.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("Prompt is required")
    width = int(params.get("width") or 256)
    height = int(params.get("height") or 256)
    if width not in (128, 256, 384, 512) or height not in (128, 256, 384, 512):
        raise ValueError("Unsupported image size")
    steps = int(params.get("steps") or 10)
    if steps < 1 or steps > 30:
        raise ValueError("Steps must be 1..30")
    seed = int(params.get("seed") if params.get("seed") is not None else -1)
    cfg = params.get("cfg", 7.0)
    try:
        cfg = float(cfg)
    except (TypeError, ValueError):
        cfg = 7.0
    return {
        "prompt": prompt,
        "negative_prompt": str(params.get("negative_prompt") or ""),
        "width": width,
        "height": height,
        "seed": seed,
        "batch_count": 1,
        "preview": "none",
        "output_format": "png",
        "vae_tiling_params": {"enabled": max(width, height) >= 512},
        "sample_params": {
            "sample_steps": steps,
            "guidance": {"txt_cfg": cfg},
        },
    }


def generate(params, on_progress=None, poll_interval=0.5, timeout=3600.0):
    """Submit a job, poll it, and return the first generated PNG (base64)."""
    body = build_request(params)
    status, submitted = _request("POST", "/sdcpp/v1/img_gen", body)
    if status not in (200, 202) or not submitted.get("id"):
        raise ValueError("sd-server did not accept the generation job")
    job_id = submitted["id"]
    image_router.set_job_id(job_id)
    deadline = time.time() + timeout
    try:
        while time.time() < deadline:
            _, job = _request("GET", "/sdcpp/v1/jobs/" + job_id)
            state = job.get("status")
            progress = job.get("progress") or {}
            if on_progress and progress:
                try:
                    on_progress(dict(progress))
                except Exception:
                    pass
            if state in TERMINAL:
                if state == "completed":
                    result = job.get("result") or {}
                    images = result.get("images") or []
                    if not images or not images[0].get("b64_json"):
                        raise ValueError("sd-server returned no image")
                    return {
                        "image_b64": images[0]["b64_json"],
                        "output_format": result.get("output_format", "png"),
                        "elapsed_ms": int(job.get("completed") or 0)
                        - int(job.get("started") or 0),
                        "stage": progress.get("stage", ""),
                    }
                error = job.get("error") or {}
                if state == "cancelled":
                    raise ValueError("Generation cancelled")
                raise ValueError(str(error.get("message") or "Generation failed"))
            time.sleep(max(0.1, poll_interval))
        raise ValueError("Generation timed out")
    finally:
        image_router.set_job_id(None)


def cancel(job_id=None):
    target = job_id or image_router.current_job_id()
    if not target:
        return {"status": "no_job"}
    _, payload = _request(
        "POST", "/sdcpp/v1/jobs/" + target + "/cancel", {})
    return payload
