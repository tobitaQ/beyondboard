# E1 effort count: rater 2 (blind)

Date: 2026-10-02. Rules: e1_rules.md. Locations: console = web browser (AWS console, Arduino Cloud web app incl. Cloud Editor); terminal; editor (local text editor); IDE (Arduino IDE); other (installer / file manager).

Conventions I applied (the same for all approaches):
- One web form or wizard counts as 1 step, even with several fields. A pure look-up that the user has to do in the console (endpoint, property ID) counts as 1 step.
- Writing or editing one file counts as 1 step, including code edited in a browser editor (Lambda code editor, Arduino Cloud Editor). Those steps count as console steps because they happen in a browser.
- "Upload sketch" counts as 1 step in every approach. Checking the result (Serial Monitor, looking at the stored data) is not counted in any approach.
- Building the cloud side for the app (CloudPower `npm run deploy`, creating the AWS IoT thing or the Arduino Cloud device/Thing) counts per app, because each app is counted as if it were the first. Tool installs, credentials, library installs and model access count as one-time setup.

## Sources used
- AWS blog: https://aws.amazon.com/blogs/compute/building-an-aws-iot-core-device-using-aws-serverless-and-an-esp32/
- AWS IoT S3 rule action: https://docs.aws.amazon.com/iot/latest/developerguide/s3-rule-action.html
- AWS IoT Lambda rule action: https://docs.aws.amazon.com/iot/latest/developerguide/lambda-rule-action.html (the console grants the invoke permission automatically)
- Bedrock model access: https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html (all models are enabled by default, but Anthropic models need the one-time First Time Use form, submitted from the console model catalog or via the PutUseCaseForModelAccess API)
- Arduino Cloud webhooks: https://docs.arduino.cc/arduino-cloud/features/webhooks (Set Webhook on the Thing page; the payload contains event_id, webhook_id, device_id, thing_id and a values array)
- Arduino Cloud REST API / API keys: https://docs.arduino.cc/arduino-cloud/api/arduino-iot-api/ and https://docs.arduino.cc/arduino-cloud/getting-started/api-overview (API Keys page -> CREATE API KEY -> client ID/secret; token from https://api2.arduino.cc/iot/v1/clients/token)
- Arduino Cloud plans: https://cloud.arduino.cc/plans (free plan: 2 Things and 1-day data retention; the API is listed as not included in the free plan)
- Arduino Cloud docs pages are rendered with JavaScript and WebFetch returned them empty, so for Arduino Cloud I relied on search snippets plus the baseline code in evaluation/baselines/arduino_cloud/.
- CloudPower: arduino/CloudPower/examples/01–05, library.properties, backend/package.json, settings.json, scripts/deploy.mjs, common.mjs, devices.mjs, try.mjs, lib/backend-stack.ts, functions/detectAnomaly.py, files/config.json, contract_spec.md §1–4, STATUS.md §3.

---

## A. AWS direct

### One-time setup
| # | Step | Location | Needed for |
|---|---|---|---|
| S1 | Install the MQTT library by Joel Gaehwiler (Library Manager) | IDE | 1–5 |
| S2 | Install ArduinoJson (Library Manager) | IDE | 1–5 |
| S3 | Submit the Anthropic First Time Use form (Bedrock model catalog) | console | 4–5 |

### App 1: Save
1. Create an S3 bucket (console)
2. Create an IoT policy: Connect on client/<thing> and Publish on topic/esp32/temp, with the ARNs edited for region/account (console)
3. Create the thing, auto-generate the certificate, attach the policy, and download the cert, key and Root CA (console wizard)
4. Look up the device data endpoint in IoT Settings (console)
5. Create an IoT rule with `SELECT * FROM 'esp32/temp'`, an S3 action (bucket, key `temp/${timestamp()}.json`) and a new IAM role created in the form (console)
6. Write secrets.h: thing name, Wi-Fi, endpoint and 3 PEMs (IDE)
7. Write the sketch: WiFiClientSecure, MQTT connect, JSON publish (IDE)
8. Upload (IDE)

Total: 8 steps, 5 console.

### App 2: Load
1. Create an S3 bucket (console)
2. Write config.json (editor)
3. Upload config.json to the bucket (console)
4. Create a Lambda function, Python (console)
5. Write the Lambda code: S3 get_object, then iot-data publish to the reply topic (console)
6. Add s3:GetObject and iot:Publish to the Lambda execution role (console, IAM)
7. Create an IoT policy: Connect, Publish on the request topic, Subscribe on the topicfilter and Receive on the reply topic (console)
8. Create the thing, certificate and policy attachment, and download the files (console)
9. Look up the endpoint (console)
10. Create an IoT rule `SELECT * FROM 'esp32/config/get'` with a Lambda action (console)
11. Write secrets.h (IDE)
12. Write the sketch: subscribe, message handler, request/wait (IDE)
13. Upload (IDE)

Total: 13 steps, 9 console.

### App 3: Run
1. Create a Lambda function (console)
2. Write the Lambda code: threshold, then publish the reply (console)
3. Add iot:Publish to the execution role (console)
4. Create an IoT policy: connect/publish/subscribe/receive (console)
5. Create the thing and certificate, and download the files (console)
6. Look up the endpoint (console)
7. Create an IoT rule with a Lambda action (console)
8. Write secrets.h (IDE)
9. Write the sketch (IDE)
10. Upload (IDE)

Total: 10 steps, 7 console.

### App 4: Ask
1. Create a Lambda function (console)
2. Write the Lambda code: Bedrock Converse, then publish the reply (console)
3. Raise the Lambda timeout above the 3 s default, because a Bedrock call can exceed it (console)
4. Add bedrock:InvokeModel and iot:Publish to the execution role (console)
5. Create an IoT policy (console)
6. Create the thing and certificate, and download the files (console)
7. Look up the endpoint (console)
8. Create an IoT rule with a Lambda action (console)
9. Write secrets.h (IDE)
10. Write the sketch (IDE)
11. Upload (IDE)

Total: 11 steps, 8 console.

### App 5: Ask + save
1. Create an S3 bucket (console)
2. Create a Lambda function (console)
3. Write the Lambda code: Converse, label check/retry, S3 put, publish (console)
4. Raise the Lambda timeout (console)
5. Add bedrock:InvokeModel, s3:PutObject and iot:Publish to the role (console)
6. Create an IoT policy (console)
7. Create the thing and certificate, and download the files (console)
8. Look up the endpoint (console)
9. Create an IoT rule with a Lambda action (console)
10. Write secrets.h (IDE)
11. Write the sketch (IDE)
12. Upload (IDE)

Total: 12 steps, 9 console.

---

## B. Arduino Cloud (+ AWS Lambda/Bedrock through a webhook for apps 3–5)

### One-time setup
| # | Step | Location | Needed for |
|---|---|---|---|
| S1 | Install the Arduino Cloud Agent, needed to upload from the Cloud Editor | other | 1–5 |
| S2 | Create an Arduino Cloud API key (client ID and secret; save the PDF) | console | 3–5 |
| S3 | Submit the Anthropic First Time Use form on Bedrock | console | 4–5 |

### App 1: Save
1. Add a device: third-party, ESP32, model, name; save the Device ID and Secret Key (console wizard)
2. Create a Thing (console)
3. Associate the device with the Thing (console)
4. Add the cloud variable `temperature`: float, Read Only, On change (console)
5. Configure the network: Wi-Fi SSID/password and the device secret key (console)
6. Edit the generated sketch in the Cloud Editor: millis timer, assign the variable (console)
7. Upload through the Agent (console)

Total: 7 steps, 7 console.

### App 2: Load
A setting is a Read&Write cloud variable set from a dashboard. Arduino Cloud has no files.
1. Add a device (console)
2. Create a Thing (console)
3. Associate the device (console)
4. Add the variable `intervalSeconds`: int, Read & Write, with an onChange callback (console)
5. Configure the network (console)
6. Create a dashboard (console)
7. Add a widget linked to the variable (console)
8. Set the value in the widget (console)
9. Edit the sketch: onIntervalSecondsChange (console)
10. Upload (console)

Total: 10 steps, 10 console.

### App 3: Run
1. Add a device (console)
2. Create a Thing (console)
3. Associate the device (console)
4. Add the variable `temperature`: float, Read Only (console)
5. Add the variable `result`: String, Read & Write (console)
6. Configure the network (console)
7. Edit the sketch (console)
8. Upload (console)
9. Create a Lambda function with a function URL, auth NONE, set in the same create form (console)
10. Write the receiver code: parse the webhook JSON, threshold, OAuth token, then PUT the property publish (console)
11. Look up the `result` property ID, and the Thing ID if needed (console, Arduino Cloud)
12. Set Lambda environment variables: ARDUINO_CLIENT_ID, ARDUINO_CLIENT_SECRET, RESULT_PROPERTY_ID (console)
13. Set the webhook on the Thing to the function URL (console)

Total: 13 steps, 13 console.

### App 4: Ask
1–8: as in app 3, with the variables `question` (String, Read Only) and `answer` (String, Read & Write): device, Thing, associate, 2 variables, network, sketch, upload (console)
9. Create a Lambda function with a function URL (console)
10. Write the receiver code: parse, Converse, token, write-back (console)
11. Raise the Lambda timeout (console)
12. Add bedrock:InvokeModel to the execution role (console)
13. Look up the property ID (console)
14. Set the environment variables (console)
15. Set the webhook (console)

Total: 15 steps, 15 console.

### App 5: Ask + save
1–8: as in app 3, with the variables `temperature` and `label` (String, Read & Write); the label is "saved" as the variable's history (console)
9–15: as in app 4. The receiver code has the label check and retry (console)

Total: 15 steps, 15 console.

---

## C. CloudPower

### One-time setup
| # | Step | Location | Needed for |
|---|---|---|---|
| S1 | Get the repository (git clone) | terminal | 1–5 |
| S2 | Install Node.js | other | 1–5 |
| S3 | Install the AWS CLI | other | 1–5 |
| S4 | Set AWS credentials (`aws login` / `aws configure`) | terminal | 1–5 |
| S5 | `npm install` in backend/ | terminal | 1–5 |
| S6 | `npx cdk bootstrap`. The repo does not mention it, but the stack has Lambda and S3 assets, so CDK requires it | terminal | 1–5 |
| S7 | Install the CloudPower library: copy or link arduino/CloudPower into the Arduino libraries folder | other | 1–5 |
| S8 | Submit the Anthropic First Time Use form on Bedrock | console | 4–5 |

The default settings.json (region ap-northeast-1, device-1, Haiku 4.5 jp profile) works unchanged, so editing it is not counted.

### App 1: Save
1. `npm run deploy` (terminal)
2. Write the Wi-Fi name/password in backend/out/device-1/aws_config.h (editor)
3. Copy aws_config.h into the sketch folder (other)
4. Write the sketch: `aws.begin()`, `aws.save("temp.csv", temp)` (IDE)
5. Upload (IDE)

Total: 5 steps, 0 console.

### App 2: Load
1. Write backend/files/config.json (editor)
2. `npm run deploy` (terminal)
3. Edit Wi-Fi in aws_config.h (editor)
4. Copy aws_config.h (other)
5. Write the sketch: `aws.load("config.json")` (IDE)
6. Upload (IDE)

Total: 6 steps, 0 console.

### App 3: Run
1. Write backend/functions/detectAnomaly.py with `def run(input)` (editor). `npm run try` is optional and not counted.
2. `npm run deploy` (terminal)
3. Edit Wi-Fi in aws_config.h (editor)
4. Copy aws_config.h (other)
5. Write the sketch: `aws.run("detectAnomaly", ...)` (IDE)
6. Upload (IDE)

Total: 6 steps, 0 console.

### App 4: Ask
1. `npm run deploy` (terminal)
2. Edit Wi-Fi in aws_config.h (editor)
3. Copy aws_config.h (other)
4. Write the sketch: `aws.ask(prompt, data)` (IDE)
5. Upload (IDE)

Total: 5 steps, 0 console.

### App 5: Ask + save
1–5: as in app 4. The sketch uses `aws.ask(prompt, data, labels, 3)` and `aws.save("status.csv", ...)`.

Total: 5 steps, 0 console.

---

## Summary table

| app | approach | steps (excl. setup) | console_steps (excl.) | steps (incl. setup) | console_steps (incl.) |
|---|---|---|---|---|---|
| 1 | AWS direct | 8 | 5 | 10 | 5 |
| 1 | Arduino Cloud | 7 | 7 | 8 | 7 |
| 1 | CloudPower | 5 | 0 | 12 | 0 |
| 2 | AWS direct | 13 | 9 | 15 | 9 |
| 2 | Arduino Cloud | 10 | 10 | 11 | 10 |
| 2 | CloudPower | 6 | 0 | 13 | 0 |
| 3 | AWS direct | 10 | 7 | 12 | 7 |
| 3 | Arduino Cloud | 13 | 13 | 15 | 14 |
| 3 | CloudPower | 6 | 0 | 13 | 0 |
| 4 | AWS direct | 11 | 8 | 14 | 9 |
| 4 | Arduino Cloud | 15 | 15 | 18 | 17 |
| 4 | CloudPower | 5 | 0 | 13 | 1 |
| 5 | AWS direct | 12 | 9 | 15 | 10 |
| 5 | Arduino Cloud | 15 | 15 | 18 | 17 |
| 5 | CloudPower | 5 | 0 | 13 | 1 |

Setup steps included per app: AWS 2 (apps 1–3) or 3 (apps 4–5, 1 console). Arduino Cloud 1 (apps 1–2), 2 (app 3, 1 console) or 3 (apps 4–5, 2 console). CloudPower 7 (apps 1–3) or 8 (apps 4–5, 1 console).

Sensitivity: if Cloud Editor work (edit sketch, upload) were counted as IDE rather than console, the Arduino Cloud console counts drop by 2 per app.

---

## Concepts

### AWS direct
Needed for app 1:
1. MQTT publish / topic
2. Thing
3. X.509 device certificate + private key
4. Amazon Root CA
5. IoT policy (actions Connect/Publish)
6. ARN (policy resources)
7. MQTT client ID = thing name
8. Device data endpoint
9. IoT rule + rule SQL
10. Rule action
11. S3 bucket
12. S3 object key / substitution template
13. IAM role for the rule (service role)
14. Region
15. JSON payload design

Added for apps 2–5:
16. MQTT subscribe/receive + topic filter
17. Request/reply topics (asynchronous response matching)
18. Lambda function
19. Lambda handler / event
20. Lambda execution role + IAM permissions
21. boto3 SDK
22. IoT data-plane publish (iot-data)
23. Lambda timeout
24. Amazon Bedrock
25. Model ID / inference profile
26. Converse API
27. Model access / Anthropic FTU form
28. Inference config (maxTokens)

Counts: app 1 = 15, apps 1–5 = 28.

### Arduino Cloud
Needed for app 1:
1. Thing
2. Device (third-party) + Device ID / Secret Key
3. Cloud variable (type)
4. Variable permission (Read Only / Read & Write)
5. Variable update policy (On change / periodic)
6. Network configuration / secrets tab
7. Generated thingProperties.h / initProperties
8. ArduinoCloud.update() non-blocking loop (no delay)
9. Cloud Editor + Cloud Agent
10. Variable history / data retention (plan)

Added for apps 2–5:
11. Dashboard
12. Widget linked to a variable
13. onChange callback
14. Webhook + its payload format
15. Arduino Cloud REST API (property publish)
16. API key / OAuth client credentials token
17. Thing ID / property ID
18. Lambda function
19. Function URL (auth type)
20. Environment variables
21. Lambda handler / event body
22. Lambda timeout
23. Execution role + IAM permissions
24. Amazon Bedrock
25. Model ID / inference profile
26. Converse API
27. Model access / Anthropic FTU form
28. Inference config (maxTokens)
29. JSON payload design (webhook parsing, REST body)

Counts: app 1 = 10, apps 1–5 = 29.

### CloudPower
Needed for app 1:
1. Backend deploy (`npm run deploy`)
2. aws_config.h (generated config holding Wi-Fi + token)
3. `aws.begin()`
4. `aws.save(name, value)` with a logical name (append record)
5. `aws.ok()` / `aws.lastError()`
6. AWS CLI credentials
7. CDK bootstrap

Added for apps 2–5:
8. `aws.load(name)`
9. backend/files/ (files served by load)
10. `aws.run(name, input)`
11. backend/functions/<name>.py with `def run(input)`
12. `aws.ask(prompt, data)`
13. `aws.ask(..., choices, n)` (constrained choice)
14. Model access / Anthropic FTU form

Counts: app 1 = 7, apps 1–5 = 14. Without the two setup-only concepts (6, 7): 5 and 12.

## Ambiguities and how I resolved them
1. Per-app versus one-time: I counted deploy/thing/device creation per app and tool, credential and library setup as one-time.
2. Granularity of a console "setting": one form or wizard is 1 step. The AWS thing wizard (thing + certificate + policy attach + download) is 1 step. A Lambda function URL enabled in the create form is not a separate step. An IoT rule with an inline "create role" is 1 step.
3. Browser code editors: Lambda code and Arduino Cloud Editor edits count as console steps. Sensitivity is given above.
4. Look-ups (IoT endpoint, Arduino property ID) count as steps.
5. Bedrock model access: since 2025 there is no per-model access request, but the Anthropic FTU form is still required (console). I counted it as one-time setup for apps 4–5 in all three approaches.
6. CloudPower has no README. `cdk bootstrap`, the AWS CLI and credentials are not mentioned in the repo but are required to run `npm run deploy`, so I added them to setup.
7. Arduino Cloud app 2: a "config" is a Read&Write variable set from a dashboard widget, following the baseline. App 5 "save": the variable history (1 day on the free plan). The REST API needed for apps 3–5 is listed as not available on the free plan. That does not change the step counts, but it is a cost barrier.
8. App 1 "save" in Arduino Cloud depends on the variable history and needs no extra step. In AWS it needs an S3 bucket and a rule action.
9. Verification steps (Serial Monitor, viewing data, `npm run try`) are excluded everywhere.
