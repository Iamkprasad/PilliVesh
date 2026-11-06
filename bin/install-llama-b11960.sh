#!/data/data/com.termux/files/usr/bin/bash
# One-time llama.cpp b11960 install for LFM3 (Termux). Termux pkg 0.7.0
# cannot load lfm3 arch. Installs to $PREFIX, backs up old to
# ~/.backup/llama-0.7.0/, keeps wrappers so no LD_LIBRARY_PATH is needed.
set -e
[ -n "${PREFIX:-}" ] || { echo "Termux only (needs \$PREFIX)."; exit 1; }
mkdir -p ~/.backup/llama-0.7.0
cp -a "$PREFIX/bin/llama"* ~/.backup/llama-0.7.0/ 2>/dev/null || true
cp -a "$PREFIX/lib"/libggml* "$PREFIX/lib"/libllama* "$PREFIX/lib"/libmtmd* ~/.backup/llama-0.7.0/ 2>/dev/null || true
curl -sL -o /tmp/llama-b11960.tar.gz https://github.com/ggml-org/llama.cpp/releases/download/b11960/llama-b11960-bin-android-arm64.tar.gz
mkdir -p /tmp/llama-b11960 && tar xzf /tmp/llama-b11960.tar.gz -C /tmp/llama-b11960 --strip-components=1
cp -a /tmp/llama-b11960/*.so "$PREFIX/lib/"
cp -a /tmp/llama-b11960/llama-cli "$PREFIX/bin/llama-cli.b11960"
cp -a /tmp/llama-b11960/llama-server "$PREFIX/bin/llama-server.b11960"
cp -a /tmp/llama-b11960/*.so "$PREFIX/bin/"
for b in llama-cli llama-server; do
  printf '#!/data/data/com.termux/files/usr/bin/bash\nexport LD_LIBRARY_PATH=%s/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}\nexec %s/bin/%s.b11960 "$@"\n' "$PREFIX" "$PREFIX" "$b" > "$PREFIX/bin/$b"
  chmod +x "$PREFIX/bin/$b"
done
rm -rf /tmp/llama-b11960 /tmp/llama-b11960.tar.gz
llama-server --version
echo "OK: LFM3 (lfm3) now loadable. Restart dashboard: ./run-dashboard.sh"
