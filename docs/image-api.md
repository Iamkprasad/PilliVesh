# Image API contract — PilliVesh `/image/`

All endpoints are on the same localhost server as PilliVesh (`127.0.0.1:8080` by
default) and obey the same Host/Origin and body-size checks as `/api/chat`.

## Read endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/image/models` | Curated catalog + installed state + engine state |
| GET | `/api/image/status` | Image engine state (`running`, `pid`, `port`, `loaded_id`, current job) |
| GET | `/api/image/download/status` | Current download progress/state |
| GET | `/api/image/search?q=<text>` | Hugging Face repo search (read-only proxy) |
| GET | `/api/image/file/<id>.png` | Serve one generated PNG from `results/images/` |

## Write endpoints (POST, localhost + same-origin only)

| Method | Path | Body | Purpose |
|---|---|---|---|
| POST | `/api/image/load` | `{"id": "<catalog-id>"}` | Start `sd-server` with that SD1.5 model |
| POST | `/api/image/unload` | `{}` or `{"id": ...}` | Stop the engine and free RAM/port |
| POST | `/api/image/download` | `{"id": "<catalog-id>"}` | Stream a curated model into `models/image/` |
| POST | `/api/image/generate` | generation params | NDJSON stream of progress + result |
| POST | `/api/image/cancel` | `{}` | Cancel the current generation job |

## Generate request

```json
{
  "prompt": "a red robot in a garden",
  "negative_prompt": "blurry, lowres",
  "steps": 10,
  "width": 256,
  "height": 256,
  "seed": -1,
  "cfg": 7.0
}
```

`width`/`height` must be 128, 256, 384 or 512 (multiples of 64), steps 1–30.
The adapter maps these to the native `sd-server` `/sdcpp/v1/img_gen` schema.

## NDJSON events

Same convention as `/api/chat`:

```json
{"t":"progress","stage":"sampling","completed":3,"total":10,"unit":"steps"}
{"t":"done","id":"<uuid>","path":"/api/image/file/<uuid>.png","width":256,"height":256,"ms":12345}
{"t":"error","e":"message"}
```

Finalization (VAE decode + PNG encode) continues after sampling reaches `total`;
wait for `done`, not for sampling 100%.

## Download/search rules

- Downloads use **catalog ids only**; the browser never sends a URL.
- The server accepts only curated `huggingface.co` `.gguf` URLs, streams to
  `models/image/<file>.part`, verifies size (and sha256 when configured), then
  renames.
- `search` proxies `https://huggingface.co/api/models` with a sanitised query.
  Results not in the catalog show a copyable source link and instructions to add
  an entry to `runtime/model/image_catalog.py`; they are never downloaded.
