# PilliVesh Phone-First Multimodal Runtime

Status: Architecture proposal  
Target: Android ARM64 through Termux/Debian  
Execution policy: local-only, CPU-first, one heavy inference workload at a time  
Compatibility policy: preserve the existing stdlib server, plain-JS frontend, llama.cpp chat path, SQLite stores, and localhost-only security boundary.

## 1. Goals

PilliVesh should accept and produce text, images, audio, and video, and support interactive speech-to-speech conversations. The existing chat interface and runtime remain the product. Multimodal capabilities are added as adapters behind a common router; they are not separate applications.

Required capabilities:

- Text: existing chat, streaming, reasoning, and tool orchestration.
- Image: image upload, image description/question answering, OCR-oriented extraction.
- Audio input: recorded or selected audio, transcription, audio question answering where a compatible model exists.
- Audio output: text-to-speech and playable local audio.
- Video: local video selection, bounded frame extraction, timestamped frame analysis, optional audio-track transcription, combined summary.
- Realtime voice: microphone capture, streaming transcription or speech-native inference, interrupt/cancel, streamed speech output.

Non-goals for the first implementation:

- Cloud inference as a requirement.
- Background always-on microphone/camera capture.
- Multiple large models resident simultaneously.
- GPU/Vulkan as a dependency.
- Arbitrary shell commands or arbitrary model download URLs.
- Uploading media to remote services.

## 2. Existing repository contracts to preserve

The current application is a Python standard-library HTTP server in `runtime/server/app.py`, with request/business handlers in `runtime/server/handlers.py`. The frontend is plain HTML/CSS/JS under `frontend/`; API calls are centralized in `frontend/js/api.js`. Model discovery and allow-listed downloads live in `runtime/model/catalog.py`; runtime profile detection is in `runtime/model/runtime_config.py`.

Preserve:

- `127.0.0.1` binding, Host validation, same-origin POST validation, and current response envelope.
- Existing `/api/chat` request and NDJSON response semantics.
- Existing model catalog allow-list and one-resident-model policy.
- Existing lazy model loading and unload behavior.
- Existing local storage conventions: media goes under an ignored runtime data directory, never into Git.
- No third-party Python dependency at import/startup time. Optional backends must fail closed with a clear “not installed / unsupported” state.
- Do not replace the frontend framework or restructure the existing navigation.

## 3. Proposed package layout

Add the following modules incrementally:

```text
runtime/
  multimodal/
    __init__.py
    contracts.py          # Task, modality, result and capability data contracts
    registry.py           # Explicit adapter registry; no dynamic imports from user input
    router.py              # Capability selection and resource-aware scheduling
    media_store.py         # Local temp files, MIME/size validation, cleanup
    jobs.py                # Job state and cancellation bookkeeping
    adapters/
      __init__.py
      base.py              # Adapter interface
      llama_vision.py      # Only after a tested vision-capable llama.cpp path exists
      speech_to_text.py    # Optional local STT adapter
      text_to_speech.py    # Optional local TTS adapter
      lfm3_omni.py         # Experimental adapter, only after device validation
      minimind_o.py        # Experimental adapter, only after device validation
      mini_omni2.py        # Experimental adapter, only after device validation
    video/
      __init__.py
      frames.py            # Bounded frame extraction interface
      pipeline.py          # Frame + optional audio orchestration
  server/
    multimodal_handlers.py
frontend/
  js/
    media.js               # Browser media selection, recording and playback
    multimodal.js          # Capability UI and task lifecycle
  css/
    multimodal.css
```

This is a target layout, not a claim that those adapters are already implemented. Only add an adapter after its upstream runtime, model format, ARM64 support, dependencies, and memory footprint have been tested on the target phone.

## 4. Adapter contract

Every adapter declares capabilities and resource estimates before it can be selected.

Suggested normalized capability record:

```json
{
  "id": "adapter-id",
  "display_name": "Adapter name",
  "modalities_in": ["text", "image"],
  "modalities_out": ["text"],
  "tasks": ["chat", "image_question_answering"],
  "streaming": false,
  "requires": {
    "backend": "cpu",
    "packages": [],
    "model_ids": []
  },
  "resources": {
    "estimated_peak_ram_mb": null,
    "disk_mb": null,
    "resident_slots": 1
  },
  "status": "unavailable"
}
```

Status values: `available`, `installed`, `loaded`, `busy`, `unsupported`, `unavailable`, `error`.

The adapter interface should expose:

- `capabilities()`
- `preflight(task, device_profile)`
- `run(task, cancel_token, progress_callback)`
- `cancel(task_id)`
- `close()`

Adapters return a normalized result containing task id, status, text, optional media artifact references, model/adapter id, timestamps, and structured error details. Never return arbitrary filesystem paths to the browser.

## 5. Model routing and device policy

The router selects by requested task and declared capabilities, not by model name alone.

Selection order:

1. Verify that an installed adapter supports every required input and output modality.
2. Check that its model files and backend dependencies are present.
3. Check current available RAM and the adapter's declared peak-RAM estimate plus a configurable safety reserve.
4. Check whether another exclusive inference job is running.
5. Prefer CPU-compatible adapters on this device.
6. If no adapter passes preflight, return a precise unsupported/unavailable explanation; do not silently switch to cloud.

Only one memory-heavy model/job should be active by default. Video processing is sequential and bounded. Audio and image jobs must release temporary buffers and unload optional model processes after their configured idle timeout. The existing text model should not be evicted without an explicit policy decision.

Initial device profile should use actual telemetry rather than hard-coded assumptions. Treat Vulkan as disabled by default on the known Termux build until a repeatable device test passes. Do not infer GPU capability from the presence of an Adreno device alone.

## 6. Model evaluation plan

The models shown in the supplied comparison images are candidates, not confirmed phone-compatible engines.

| Candidate | Intended role | Integration status |
|---|---|---|
| LFM3-Omni-2B | Unified text/image/audio/video and speech | Experimental; validate runtime, format, ARM64 dependencies, RAM and thermal behaviour |
| MiniMind-O | Compact speech-native multimodal path | Experimental; validate complete runtime footprint, not just trainable backbone count |
| Mini-Omni2 | Speech-to-speech with image understanding | Experimental; validate Python/runtime dependencies and actual device performance |
| Existing GGUF text model | Text chat and fallback | Keep existing path unchanged |

A model's parameter count is not its peak RAM requirement. Include weights, KV cache, vision/audio encoders, codecs, tokenizer, runtime libraries, temporary media buffers, and Android process overhead in every measurement. Do not list a candidate as supported until a real device test succeeds.

## 7. Local media lifecycle and security

- Accept only explicitly supported MIME types and verify file signatures where practical; do not trust the browser-provided filename or MIME value.
- Enforce configurable upload limits before reading the full request body.
- Generate server-side random media IDs and safe filenames. Never join a user-provided path to the filesystem.
- Store temporary media below an ignored directory such as `results/media/tmp/`; set restrictive permissions where supported.
- Keep browser-visible references opaque (media IDs), not absolute paths.
- Clean temporary files after completion, cancellation, startup recovery, and a bounded retention period.
- Never execute uploaded files.
- Never pass user text or filenames to a shell. If an external media binary is eventually required, call a fixed executable with a fixed argument structure and validated paths; no shell interpolation.
- Keep all routes localhost-only and apply existing Host and Origin checks to every new POST route.
- Do not log media contents, API keys, audio transcripts by default, or raw file paths.
- The user must explicitly start microphone recording; show recording state and provide stop/cancel.

## 8. API proposal

Keep the existing JSON envelope `{success, data}` / `{success, error}`.

Read endpoints:

- `GET /api/multimodal/capabilities` — adapters, supported modalities, status and honest availability.
- `GET /api/multimodal/jobs?id=...` — task state and progress.
- `GET /api/multimodal/media/{opaque_id}` — serve only validated output artifacts through an allow-listed media store.

Write endpoints:

- `POST /api/multimodal/upload` — bounded multipart upload; return opaque media id.
- `POST /api/multimodal/run` — JSON task request referencing media ids and selected task; returns job id.
- `POST /api/multimodal/cancel` — cancel a job by opaque job id.
- `POST /api/multimodal/recording/transcribe` — optional browser-recorded audio submission through the same upload/task pipeline.

Video is a task type, not an unrestricted new execution path: the video pipeline validates the file, extracts a bounded number of frames at a bounded interval/resolution, optionally extracts audio, then schedules sequential image/audio tasks and combines timestamped results.

For large media, do not use the current 256 KiB JSON body reader. Implement a separate bounded streaming multipart reader or a tested standard-library-compatible upload parser. Enforce a maximum total byte count while streaming, not after buffering the entire body.

## 9. Frontend experience

Add a compact attachment/action tray to the existing composer:

- Text
- Image
- Audio
- Video
- Voice conversation

The controls must be capability-aware. Unsupported controls should explain why they are unavailable, not pretend to work. Use browser-native file input and MediaRecorder where available; feature-detect APIs. Audio playback uses a local output artifact URL. Show upload progress, processing state, cancellation, and a clear result. Preserve existing mobile chat layout and accessibility.

Do not build a separate multimodal dashboard. Add a small capability status area to the existing Models or System control center.

## 10. Implementation phases and acceptance criteria

### Phase 0 — Architecture and safety foundation
- Add contracts, registry, router, media store and tests.
- Add capability endpoint reporting all modalities as unavailable until an adapter is actually installed.
- No changes to existing chat behavior.
- Test localhost/Host/Origin protections, upload size limits, path traversal, invalid MIME/signature, cleanup and cancellation.

### Phase 1 — Image input
- Select and validate images; enforce dimensions and byte limits.
- Integrate one vision adapter only after ARM64/CPU verification.
- Test a local image question and screenshot/OCR-oriented extraction.
- Text-only chat must still work when no vision adapter is installed.

### Phase 2 — Audio input
- Browser recording and audio file selection.
- Integrate a local STT adapter with measured RAM, latency and language support.
- Return transcript and allow the user to submit it to the existing chat flow.

### Phase 3 — Speech output
- Add a local TTS adapter and playable output artifacts.
- Add cancellation and cleanup.
- Measure first-audio latency and real-time factor.

### Phase 4 — Video
- Add bounded frame extraction and timestamped summaries.
- Add optional audio-track transcription.
- Enforce frame count, duration, resolution and processing-time limits.

### Phase 5 — Realtime speech-to-speech
- Prefer a tested speech-native model that supports incremental input/output and interruption.
- If no single local model passes the device gate, compose local STT -> existing text engine -> local TTS and label it as a cascaded pipeline, not native speech-to-speech.
- Measure end-to-end latency, peak RAM, thermals and interruption response.

Each phase is independently usable and must preserve the existing text-only application.

## 11. Test strategy

Use Python stdlib `unittest` so the base install remains dependency-free.

- Contract and registry tests with fake adapters.
- Router tests for missing modalities, RAM rejection, exclusive execution and cancellation.
- Media store tests for MIME mismatch, size limit, traversal attempts, opaque ids and cleanup.
- HTTP tests for Host/Origin checks and all new route limits.
- Frontend tests/manual checklist for file picker, MediaRecorder feature detection, upload progress, cancellation, and mobile layout.
- Device acceptance tests on the Motorola Edge 20 Pro: cold start, peak available RAM before/after, inference latency, tokens/sec or audio real-time factor, thermal behaviour, process cleanup, and battery use.

Record measurements in the existing benchmark/results conventions. Report unavailable metrics as unavailable, not zero.

## 12. Rollout and compatibility

The first implementation should ship behind a feature flag such as `AI_LAB_MULTIMODAL=1`, default off until the media store and route tests pass. The capability endpoint may remain readable while the feature is off. Existing `/api/chat`, provider configuration, model loading, memory, skills, tools and dashboard startup must continue to work unchanged.

No new Python package is required for the architecture foundation. Optional inference and media packages are isolated behind adapters and installed only for the phase being validated.
