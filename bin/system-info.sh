#!/data/data/com.termux/files/usr/bin/bash

echo "======================================"
echo "        LOCAL AI SYSTEM INFO"
echo "======================================"

echo
echo "[DEVICE]"
getprop ro.product.model
getprop ro.board.platform

echo
echo "[CPU]"
nproc
cat /proc/cpuinfo | grep -m 1 "Features"

echo
echo "[RAM]"
free -h

echo
echo "[STORAGE]"
df -h /data

echo
echo "[GPU / VULKAN]"
llama-cli --list-devices 2>&1

echo
echo "[CPU GOVERNOR]"
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null

echo
echo "[THERMAL]"
for z in 15 19 20 23 24 84 85 89 93; do
    type=$(cat /sys/class/thermal/thermal_zone$z/type 2>/dev/null)
    temp=$(cat /sys/class/thermal/thermal_zone$z/temp 2>/dev/null)
    [ -n "$type" ] && echo "$type: $temp"
done

echo
echo "[CPU AFFINITY]"
taskset -p $$ 2>/dev/null

echo
echo "======================================"
