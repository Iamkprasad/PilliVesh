#!/data/data/com.termux/files/usr/bin/bash

LAB="$HOME/ai-lab"
RESULTS="$LAB/results"

mkdir -p "$RESULTS"

echo "======================================"
echo "       LOCAL AI BENCHMARK LAB"
echo "======================================"
echo
echo "Date: $(date)"
echo

echo "[SYSTEM]"
free -h
echo

echo "[GPU]"
llama-cli --list-devices 2>&1
echo

echo "[CPU]"
echo "Cores: $(nproc)"
echo "Affinity: $(taskset -p $$ 2>&1)"
echo

echo "[THERMALS]"
for z in 15 19 20 23 24 84 85 89 93; do
    type=$(cat /sys/class/thermal/thermal_zone$z/type 2>/dev/null)
    temp=$(cat /sys/class/thermal/thermal_zone$z/temp 2>/dev/null)
    [ -n "$type" ] && echo "$type: $temp"
done

echo
echo "======================================"
echo "Benchmark engine ready."
echo "Model tests will be added next."
echo "======================================"
