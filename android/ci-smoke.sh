#!/usr/bin/env bash
# Runs inside the emulator job of .github/workflows/android.yml: install the
# app, connect it to the demo server on the runner (the emulator reaches the
# host's 127.0.0.1 as 10.0.2.2), and keep screenshots of each step.
set -euo pipefail
APK="$1"
OUT="${2:-smoke}"
mkdir -p "$OUT"
shot() { adb exec-out screencap -p > "$OUT/$1.png"; }
# Whatever happens, keep the device log and what the server saw.
keep_logs() {
  adb logcat -d > "$OUT/logcat.txt" 2>&1 || true
  cp "$SERVER_LOG" "$OUT/server.log" 2>/dev/null || true
}
trap keep_logs EXIT
adb logcat -c || true

adb install -r "$APK"
adb shell am start -W -n org.biomanager.app/.MainActivity
sleep 8
shot 1-setup
adb shell dumpsys activity activities | grep -q "SetupActivity" || { echo "setup screen did not open"; exit 1; }

adb shell input text "http://10.0.2.2:5077"
adb shell input keyevent KEYCODE_ENTER
sleep 20
shot 2-connected
adb shell dumpsys activity activities | grep "mResumedActivity\|topResumedActivity" | grep -q "MainActivity" \
  || { echo "did not reach the main screen"; exit 1; }
grep -q "GET /login" "$SERVER_LOG" || { echo "the server never saw the app"; cat "$SERVER_LOG"; exit 1; }
echo "smoke test passed"
