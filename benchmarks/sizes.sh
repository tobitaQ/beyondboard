#!/bin/bash
# E2: flash and RAM of each sketch. Writes benchmarks/results/sizes.csv.
# Usage: benchmarks/sizes.sh
#
# Compile only; nothing is uploaded and AWS is not called.
# - The aws sketches get a dummy aws_config.h with fake values (written into the
#   temporary build folder only), so the real backend/out/*/aws_config.h is never used.
# - The E1 baselines (evaluation/baselines/) need third-party libraries. They are
#   installed, at the pinned versions below, into this repository's .arduino/ folder
#   ($SIZES_LIB_DIR; downloads go to .arduino/staging), so nothing outside the
#   repository is written and the user's own Arduino libraries are not touched.
# - Needs the cores arduino:avr and esp32:esp32 (the CSV was made with 1.8.6 and 3.3.5).
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
CLI="${ARDUINO_CLI:-/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli}"
export ARDUINO_DIRECTORIES_USER="${SIZES_LIB_DIR:-$ROOT/.arduino}"
export ARDUINO_DIRECTORIES_DOWNLOADS="$ARDUINO_DIRECTORIES_USER/staging"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
OUT="$ROOT/benchmarks/results/sizes.csv"
LIBS=("ArduinoIoTCloud@2.10.0" "MQTT@2.5.3" "ArduinoJson@7.4.3")

mkdir -p "$ARDUINO_DIRECTORIES_USER"
"$CLI" lib update-index >/dev/null
"$CLI" lib install "${LIBS[@]}" >/dev/null

# Same shape as the file `npm run deploy` writes (backend/scripts/devices.mjs), with fake values.
cat > "$WORK/aws_config.h" <<'EOF'
#pragma once
#define AWS_WIFI_NAME "wifi-name"
#define AWS_WIFI_PASSWORD "wifi-password"
#define AWS_CLOUD_URL "https://abcdefghijklmnopqrstuvwxyz012345.lambda-url.ap-northeast-1.on.aws"
#define AWS_CLOUD_TOKEN "0123456789abcdef0123456789abcdef0123456789abcdef"
#define AWS_ASK_COST_USD 0.001300
#define AWS_CALL_COST_USD 0.000003
#define AWS_ASK_DAILY_LIMIT 200
#include <BeyondBoardAws.h>
EOF

echo "board,sketch,flash_bytes,ram_bytes" > "$OUT"

measure() {  # board fqbn, sketch dir, [label written to the CSV; default: folder name]
  local board=$1 dir=$2 name label copy
  name=$(basename "$dir")
  label=${3:-$name}
  copy="$WORK/build/$(dirname "$label")/$name"  # the folder name must match the .ino name
  rm -rf "$copy"
  mkdir -p "$(dirname "$copy")"
  cp -r "$dir" "$copy"
  grep -q '"aws_config.h"' "$copy"/*.ino && cp "$WORK/aws_config.h" "$copy/"
  local json flash ram
  json=$("$CLI" compile --fqbn "$board" --library "$ROOT/arduino/BeyondBoard" --format json "$copy" 2>/dev/null)
  read -r flash ram < <(echo "$json" | python3 -c '
import json, sys
r = json.load(sys.stdin)
assert r.get("success", True), r.get("compiler_err")
sizes = {s["name"]: s["size"] for s in r["builder_result"]["executable_sections_size"]}
print(sizes.get("text", 0), sizes.get("data", 0))')
  echo "$board,$label,$flash,$ram" | tee -a "$OUT"
}

# ESP32: library vs hand-written baselines, and two examples.
for s in Empty SerialOnly RawHttps MinimalAws MinimalLocal; do
  measure esp32:esp32:esp32 "$ROOT/benchmarks/sizes/$s"
done
measure esp32:esp32:esp32 "$ROOT/arduino/BeyondBoard/examples/05_AskClassify"
measure esp32:esp32:esp32 "$ROOT/arduino/BeyondBoard/examples/06_LocalAll"

# Arduino UNO: local only.
for s in Empty SerialOnly MinimalLocal; do
  measure arduino:avr:uno "$ROOT/benchmarks/sizes/$s"
done
measure arduino:avr:uno "$ROOT/arduino/BeyondBoard/examples/06_LocalAll"

# Other ESP32 chips.
for board in esp32:esp32:esp32s3 esp32:esp32:esp32s2 esp32:esp32:esp32c3 esp32:esp32:esp32c6; do
  for s in RawHttps MinimalAws MinimalLocal; do
    measure "$board" "$ROOT/benchmarks/sizes/$s"
  done
done

# E1: the five sample apps, three ways, on ESP32.
# ours = the library examples 01-05 (aws); the others are in evaluation/baselines/.
OURS=(01_SaveSensor 02_LoadConfig 03_RunFunction 04_AskExplain 05_AskClassify)
APPS=(app1_save app2_load app3_run app4_ask app5_classify)
for i in "${!APPS[@]}"; do
  app=${APPS[$i]}
  measure esp32:esp32:esp32 "$ROOT/evaluation/baselines/arduino_cloud/$app" "arduino_cloud/$app"
  measure esp32:esp32:esp32 "$ROOT/arduino/BeyondBoard/examples/${OURS[$i]}" "ours/$app"
  measure esp32:esp32:esp32 "$ROOT/evaluation/baselines/raw_aws/$app" "raw_aws/$app"
done
