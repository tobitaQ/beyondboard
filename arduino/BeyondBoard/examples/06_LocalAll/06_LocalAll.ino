// Saves, runs and asks on this computer instead of AWS: no account, no cost.
// The calls are exactly the same as with aws; only the object name differs.
//
// Before you start:
//   1. Install Ollama (a local AI) and get a model:  ollama pull qwen2.5:3b
//   2. Upload this sketch, then close the Serial Monitor.
//   3. On the computer:  python3 local/cloud_local.py
//      It talks to the board over the USB cable and also shows Serial.println lines.
#include <BeyondBoard.h>

const char* labels[] = {"normal", "warning", "danger"};

float readTemperature() {
  return 20.0 + random(0, 400) / 10.0;
}

void setup() {
  if (!local.begin()) {  // starts Serial at 115200 and waits for the computer
    Serial.println(local.lastError());
  }
}

void loop() {
  float temp = readTemperature();
  local.save("temp.csv", temp);

  String result = local.run("detectAnomaly", String(temp));
  String label = local.ask("How safe is this temperature for a server room?", String(temp) + " C",
                           labels, 3);
  if (local.ok()) {
    Serial.println(String(temp) + " C -> " + result + ", AI says " + label);
  } else {
    Serial.println(local.lastError());
  }
  delay(10000);
}
