# Rules for judging service changes (fixed before rating)

For each of the 38 events in events.md, give three judgments.

## Architectures being compared
- **Direct-from-sketch**: an Arduino sketch (ESP32 etc.) uses the service directly: through the vendor's device SDK/library, or by calling the vendor's HTTP API (e.g., an LLM API with a model name) from the sketch. Any cloud-side configuration (rules, consoles) is the user's.
- **Direct-with-function**: the sketch talks to an IoT platform or HTTPS endpoint, and a user-written cloud function (e.g., AWS Lambda) sits in between and calls further services (storage, AI models). The device-side protocol/SDK is still the platform's.
- **CloudPower**: the sketch calls a small library (save/load/run/ask) that speaks a fixed HTTPS (or USB-serial) contract to the user's own backend. The backend is deployed with one command (AWS CDK) and contains adapters that map the contract onto services (Lambda, DynamoDB, S3, Bedrock). AI model IDs live in a backend settings file (settings.json), never in sketches. User functions are Python `def run(input)` files run by the backend. See contract_spec.md and backend/ for details.

## Codes
Direct-from-sketch and Direct-with-function, one of:
- **S**: the sketch code must be rewritten (and reflashed)
- **C**: only cloud-side work is needed (console settings, cloud code); the device is untouched
- **-**: no effect, or only a contract/plan decision (pricing, renames with compatible endpoints)
- **new**: a new capability appears that requires adopting a new SDK/API

CloudPower, one of:
- **S**: the sketch must be rewritten
- **Cfg**: only the generated config file (aws_config.h: endpoint URL, token) changes; sketch code unchanged but reflashed
- **A**: absorbed by changing a backend adapter or settings.json and redeploying; device untouched
- **A+Cfg**: both A and Cfg
- **I**: absorbed by upgrading infrastructure-as-code or runtime versions and redeploying; device untouched
- **-**: CloudPower does not depend on the service, or the change is outside its contract
- **Add**: a new capability that can be added as a new call without changing existing sketches

Judge what would have happened at the time of the event to a prototype built in that style. If unsure, pick the most likely code and mark confidence "low".
