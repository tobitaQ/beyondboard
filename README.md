# BeyondBoard

Cloud storage, computing, and generative AI as one-line Arduino calls.

> The library was called **CloudPower** until 2026-10-17; some evaluation records keep that name.

```cpp
#include "aws_config.h"                         // made by `npm run deploy`

void setup() {
  aws.begin();                                  // Wi-Fi and token come from aws_config.h
  aws.save("temp.csv", 23.5);                   // add one line to temp.csv
  String r = aws.run("detectAnomaly", "38.2");  // run your Python function in the cloud
  String a = aws.ask("Is 38.2 C hot?");         // ask an AI
}
void loop() {}
```

Replace `aws` with `local` (and include `<BeyondBoard.h>`) to run the same calls on your own
computer over USB, with no account and no internet.

This repository holds the library, the backend, the local adapter, and the evaluation for the
paper "BeyondBoard: Cloud Storage, Computing, and Generative AI as One-Line
Arduino Calls".

For step-by-step setup and how to repeat every measurement in the paper, open
[docs/tutorial.html](docs/tutorial.html) (the reproduction guide).

## Calls

| Call | What it does |
|---|---|
| `begin()` | Connect (Wi-Fi from `aws_config.h`, or USB) and check the destination |
| `save(name, value)` | Append one line `time,value` (up to 1 KB) |
| `save(name, bytes)` | Save a photo or other bytes (up to 1 MB), replacing what was there |
| `load(name[, last])` | Read saved lines or a placed file (up to 16 KB) |
| `remove(name)`, `list([prefix])` | Delete saved data; list saved names |
| `run(name[, input][, timeoutMs])` | Run `backend/functions/<name>.py` and return its output |
| `ask(prompt[, data][, choices, count])` | Ask an AI; with choices, the answer is exactly one of them |
| `ask(prompt, image[, choices, count])` | Ask about a JPEG image (up to 3 MB) |
| `ok()`, `lastErrorCode()`, `lastError()` | Check success; read a plain sentence that says what to do |

The behavior every destination must share is checked by `tests/conformance.py`.
A camera module (`BeyondBoardCamera.h`) gives `camera.begin(board)` and `camera.capture()`
for ESP32 camera boards.

## Getting started

### 1. Install the library

Copy `arduino/BeyondBoard` into your Arduino `libraries` folder (for example
`~/Documents/Arduino/libraries/BeyondBoard`) and restart the Arduino IDE. The examples appear
under File > Examples > BeyondBoard. Boards: ESP32, ESP32-S2, -S3, -C3, -C6 for `aws` and
`local`; Arduino UNO for `local`.

### 2a. Start with `local` (no account)

```
python3 -m venv local/.venv && local/.venv/bin/pip install -r local/requirements.txt
local/.venv/bin/python local/cloud_local.py          # finds the board on USB
```

Upload `examples/06_LocalAll`. For `ask`, install [Ollama](https://ollama.com) and pull
`qwen2.5:3b` (text) and `qwen2.5vl:3b` (images).

### 2b. Move to `aws` (your own AWS account)

Once per computer: install Node.js (we use 22) and the AWS CLI, create an access key and run
`aws configure`, then

```
cd backend
npm install
npx cdk bootstrap        # once per account and region
npm run deploy           # builds the backend; writes out/<device>/aws_config.h
```

Devices, the region, the AI model, and function permissions are in `backend/settings.json`.
Write your Wi-Fi name and password into `out/<device>/aws_config.h` (ESP32 needs the 2.4 GHz
network), copy it into your sketch folder, and upload. Anthropic models on Amazon Bedrock may
ask for a one-time use-case form in the AWS console. Never share `aws_config.h`: it holds the
device's token and your Wi-Fi password.

### 3. Keep working

| Command (in `backend/`) | What it does |
|---|---|
| `npm run try -- <function> [input]` | Run a function on this computer, without deploying |
| `npm run deploy` | Publish new functions and settings (1–2 minutes) |
| `npm run call -- <op> ...` | Call the cloud as a device would |
| `npm run stats` | Calls, time, and estimated cost |
| `npm run revoke -- <device>` / `npm run rotate -- <device>` | Stop a device's token / make a new one |
| `npm run destroy` | Remove everything from your account, data included |

A deployed backend that is not called costs almost nothing. Each device may ask the AI 200
times a day (set in `settings.json`).

## Repository

| Path | Contents |
|---|---|
| `arduino/BeyondBoard/` | The device library and examples 01–07 |
| `backend/` | AWS CDK stack, adapters, user functions (`functions/`), commands (`scripts/`) |
| `local/` | Local adapter: USB serial, SQLite, Ollama |
| `tests/conformance.py` | 22 conformance checks for both destinations |
| `benchmarks/` | Latency, concurrency, and size measurements (`results/`) |
| `evaluation/` | Comparator implementations (`baselines/`), code metrics, image tasks, fault injection, project coverage, second rater, service-change sources |
| `tools/` | Line counts, code metrics, rater agreement |

Some files in `evaluation/` are in Japanese.

## Reproducing the evaluation

```
python3 tests/conformance.py aws                     # needs a deployed backend
python3 tests/conformance.py local http://localhost:8787 <token>
python3 benchmarks/summarize.py                      # latency and concurrency tables
bash benchmarks/sizes.sh                             # flash and RAM (compile only)
python3 tools/code_metrics.py                        # E7 code metrics
python3 evaluation/e8_images/analyze.py              # E8 face counting (needs scipy)
python3 tools/agreement.py evaluation/second_rater/e3_rater1.csv evaluation/second_rater/e3_rater2.csv
```

The E8 images are not in the repository (WIDER FACE is CC BY-NC-ND 4.0);
`evaluation/e8_images/select_images.py` rebuilds them from the official release and COCO.

## License

MIT. See [LICENSE](LICENSE).
