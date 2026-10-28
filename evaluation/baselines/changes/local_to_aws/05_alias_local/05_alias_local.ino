// 05_AskClassify with the destination chosen in one place (`auto& cloud = ...;`).
// Used to measure the change "move from local to aws" when the sketch is written this way:
// 05_alias_local and 05_alias_aws differ only in the #include line and that one line.
#include <BeyondBoard.h>

auto& cloud = local;

const char* labels[] = {"normal", "warning", "danger"};

float readTemperature() {
  return 20.0 + random(0, 400) / 10.0;
}

void setup() {
  Serial.begin(115200);
  if (!cloud.begin()) {
    Serial.println(cloud.lastError());
  }
}

void loop() {
  float temp = readTemperature();
  String label = cloud.ask("How safe is this temperature for a server room?", String(temp) + " C",
                           labels, 3);
  if (cloud.ok()) {
    Serial.print(temp);
    Serial.print(" -> ");
    Serial.println(label);
    cloud.save("status.csv", String(temp) + " " + label);
  } else {
    Serial.println(cloud.lastError());
  }
  delay(60000);
}
