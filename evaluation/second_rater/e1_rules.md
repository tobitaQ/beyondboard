# Rules for counting first-build effort (fixed before counting)

> Note (2026-10-17): this file is kept as given to the second rater on 2026-10-02. The paper's rule (Section "Where the Work Happens") also excludes logging in, choosing a region, and checking the result, for every approach; the second rater already left out checking the result (`e1_rater2.md`, conventions). Arduino Cloud applications 3--5 were later changed from a webhook to direct HTTPS calls (`evaluation/e7_code_metrics.md` section 0); the second rater counted the webhook version.

## Five sample applications (ESP32, Wi-Fi)
1. Save: log a temperature reading to the cloud periodically.
2. Load: read a setting (a small JSON/text config) from the cloud at start-up.
3. Run: send a reading to user-written cloud code that detects an anomaly (threshold) and returns the result to the device.
4. Ask: ask a generative AI (Anthropic Claude on Amazon Bedrock) to explain a reading and print the answer on the device.
5. Ask + save: let the AI choose one label from given choices for a reading, and save the label in the cloud.
The user sees the same result in all approaches. The AI model is the same (Claude Haiku on Bedrock) for all.

## Approaches
- **AWS direct**: AWS IoT Core over MQTT from the sketch (official AWS blog "Building an AWS IoT Core device using AWS Serverless and an ESP32" and the AWS IoT developer guide), IoT rules, S3, Lambda, Bedrock.
- **Arduino Cloud**: Arduino Cloud with cloud variables (official docs); computing and AI through a webhook to an external cloud (AWS Lambda calling Bedrock) that writes the answer back through the Arduino Cloud REST API.
- **CloudPower**: the library in arduino/CloudPower and the backend in backend/ of this repository (read its code, scripts, comments, and examples; there is no README).

## What to count, per application, for a user building that application first (each app counted independently, as if it were the first)
- **Step**: one coherent user action: creating one setting in a screen (web console form), editing one file, or running one command. A web-console step is one done in a browser.
- Exclude: creating cloud accounts, installing the Arduino IDE and board package. Include everything else needed, including one-time tool setup (CLI installs, credentials, bootstrap commands, library installs, model-access requests) — list one-time setup separately per approach.
- **Concept**: a platform-specific term the user must understand to build the app (e.g., "IoT policy", "cloud variable"). General Arduino/programming concepts (String, Serial, functions, JSON as a format only if the platform requires the user to design payloads? — count JSON payload design as a concept if the user must write it) are not counted.

## Output
For each approach: the one-time setup step list; for each app, the numbered step list with location (console / terminal / editor / IDE / other tool) — so counts can be compared; totals (steps, of which console). Concept list per approach, marking which are needed for app 1 and which for apps 1–5.
