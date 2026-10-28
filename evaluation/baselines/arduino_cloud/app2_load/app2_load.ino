// App 2: read a setting (no files: a variable set from the dashboard)
// Arduino Cloud version: the sketch Arduino Cloud generates, plus the lines the user writes.
#include "arduino_secrets.h"
#include "thingProperties.h"

void setup() {
  Serial.begin(9600);
  delay(1500);
  initProperties();
  ArduinoCloud.begin(ArduinoIoTPreferredConnection);
  setDebugMessageLevel(2);
  ArduinoCloud.printDebugInfo();
}

void loop() {
  ArduinoCloud.update();
}

// Called when the value is changed on the dashboard.
void onIntervalSecondsChange() {
  Serial.print("intervalSeconds = ");
  Serial.println(intervalSeconds);
}
