#!/usr/bin/env bash
# Install the native CPU image engine (stable-diffusion.cpp sd-server) for
# PilliVesh's /image page. Run inside Debian/Termux on the phone.
# No pip, no npm, no build step inside PilliVesh itself.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REF="${SDCPP_REF:-master}"
SRC="${SDCPP_SRC:-$HOME/.local/src/stable-diffusion.cpp}"
PREFIX="$HOME/.local/opt/pillivesh-image"
TARGET="$ROOT/bin/sd-server"

echo "== PilliVesh image engine installer =="
echo "ref: $REF"
echo "source: $SRC"

if ! command -v git >/dev/null 2>&1 || ! command -v cmake >/dev/null 2>&1 ||
   ! command -v ninja >/dev/null 2>&1 || ! command -v g++ >/dev/null 2>&1; then
  echo "Install build tools first: sudo apt install -y git cmake ninja-build build-essential" >&2
  exit 1
fi

if [ ! -d "$SRC/.git" ]; then
  mkdir -p "$(dirname "$SRC")"
  git clone --recursive https://github.com/leejet/stable-diffusion.cpp.git "$SRC"
fi
git -C "$SRC" fetch --all --tags
git -C "$SRC" checkout "$REF"
git -C "$SRC" submodule update --init --recursive

mkdir -p "$SRC/build-cpu"
cmake -S "$SRC" -B "$SRC/build-cpu" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DSD_WEBP=OFF -DSD_WEBM=OFF
cmake --build "$SRC/build-cpu" --config Release --parallel 2

mkdir -p "$ROOT/bin" "$PREFIX/bin"
cp "$SRC/build-cpu/bin/sd-server" "$PREFIX/bin/sd-server"
chmod +x "$PREFIX/bin/sd-server"
cp "$PREFIX/bin/sd-server" "$TARGET"
chmod +x "$TARGET"

COMMIT="$(git -C "$SRC" rev-parse HEAD)"
echo "$COMMIT" > "$ROOT/results/image_engine_commit.txt" 2>/dev/null || true
echo "Installed sd-server ($COMMIT) at $TARGET"
"$TARGET" --version 2>/dev/null || true
