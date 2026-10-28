// 05_AskClassify written for local (this computer, over USB) instead of aws.
// Used to measure the change "move from local to aws": the only differences from
// arduino/BeyondBoard/examples/05_AskClassify are the #include line and `local.` for `aws.`.
//
// Before you start:
//   1. Upload this sketch, then close the Serial Monitor.
//   2. On the computer:  python3 local/cloud_local.py
#include <BeyondBoard.h>

const char* labels[] = {"normal", "warning", "danger"};

float readTemperature() {
  return 20.0 + random(0, 400) / 10.0;
}

void setup() {
  Serial.begin(115200);
  if (!local.begin()) {
    Serial.println(local.lastError());
  }
}

void loop() {
  float temp = readTemperature();
  String label = local.ask("How safe is this temperature for a server room?", String(temp) + " C",
                           labels, 3);
  if (local.ok()) {
    Serial.print(temp);
    Serial.print(" -> ");
    Serial.println(label);
    local.save("status.csv", String(temp) + " " + label);
  } else {
    Serial.println(local.lastError());
  }
  delay(60000);
}
