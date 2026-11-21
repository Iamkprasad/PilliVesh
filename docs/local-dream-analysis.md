# Local Dream reverse-engineering notes

Source reviewed: `E:\dream\local-Webdream` (Local Dream / local-webdream,
`xororz/local-dream`), README, `app/src/main/cpp/src/main.cpp`,
`RequestParser.hpp`, `CMakeLists.txt`, `app/build.gradle.kts`, and the official
guide at <https://ld-guide.chino.icu>. Licence: **CC BY-NC 4.0** — reference
only, do not copy code verbatim into a commercial product.

## What it is

An Android app (Jetpack Compose) wrapping a native C++ Stable Diffusion engine:

- `main.cpp` starts `cpp-httplib` on `127.0.0.1:8081` (or `0.0.0.0` with
  `--listen_all` in host mode). Endpoints: `POST /generate` (SSE progress +
  complete), `POST /upscale` (binary RGB in, JPEG out), `POST /tokenize`,
  `GET /health`. CORS is `*`.
- The Kotlin `BackendService` launches `libstable_diffusion_core.so` lazily
  when a model is selected, with fixed argv and a runtime lib dir extracted
  from APK assets. Host mode adds a control API on port 8808.
- Model packages are directories with marker files (`finished`, `npucustom`,
  `SDXL`, `ANIMA`, `ZIMAGE`, …) plus `config.json`; the catalog in `Model.kt`
  gates entries by SoC (`isSdxlCapableSoc`, `DitEngine.isSupportedDevice`).
- `--convert` turns a `.safetensors` checkpoint into MNN components using
  bundled `assets/cvtbase` (CLIP, UNet, VAE). SD1.5 NPU uses QNN context
  binaries + resolution patch files; SDXL/DiT need newer Snapdragon parts.

## Patterns applied to PilliVesh

| Local Dream mechanism | PilliVesh implementation |
|---|---|
| Lazy native process on fixed loopback port | `runtime/model/image_router.py` (`:8091`) |
| Model directory + allow-list + SoC/RAM gating | `runtime/model/image_catalog.py`, RAM gate in router |
| SSE `progress` / `complete`, raw/png/jpeg output | NDJSON `progress` / `done`, native PNG output |
| `--lowram`, per-stage release, single generation mutex, cancel on disconnect | One resident engine model, `_image_generation_lock`, cancel endpoint |
| `--convert` from safetensors | Deferred; GGUF/safetensors loaded directly by sd-server |
| Loopback default, explicit host mode | Existing PilliVesh Host/Origin checks remain |

## Why its core is not used here

`CMakeLists.txt` is Android-only: `MNN_BUILD_FOR_ANDROID`,
`PLATFORM_LIBS log android dl GLESv2 EGL`, QNN SDK headers, Qualcomm
`SampleApp` sources, `libQnnHtp.so` / `libQnnHtpV*Stub.so` for
`aarch64-android`. The artifact is an Android-linked ELF requiring Bionic and
DSP/FastRPC access. It cannot be dropped into a Debian PRoot guest.

The portable part is its upstream dependency, `stable-diffusion.cpp`, which
builds natively for Linux/arm64 with a CPU backend and ships `sd-server` with
a Web UI and HTTP API. That is the engine used by this project.

## Snapdragon 870 / SM8250 notes

- SoC: SM8250-AC, Hexagon 698 (V68), Adreno 650, up to 12 GB RAM.
- Local Dream maintainer answers conflict: issue #115 says "at least 888 or
  newer" (the 870 qualifies); issue #23 says SD fails on 888/older NPUs and
  only works on 8 Gen 1+. No confirmed SM8250 NPU success report was found.
- No public LLM `.pte` for V68 (ExecuTorch supports it in source only);
  llama.cpp's HTP backend ships V73+ skels. Qualcomm AI Hub precompiled
  assets target 8 Gen 3 / Elite. Consequently this build uses CPU inference.
- Useful threads: <https://github.com/avisre/snapdragon-npu-llm>,
  <https://github.com/soobujmiah/ternux/blob/main/guides/llama-htp-experimental.md>,
  <https://github.com/leejet/stable-diffusion.cpp/issues/584>.
