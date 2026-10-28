// App 1: save a temperature every 10 seconds
// Arduino Cloud version: the sketch Arduino Cloud generates, plus the lines the user writes.
#include "arduino_secrets.h"
#include "thingProperties.h"

float readTemperature() {
  return 20.0 + random(0, 150) / 10.0;
}

unsigned long last = 0;

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
  // delay() is discouraged with Arduino Cloud, so use millis().
  if (millis() - last > 10000) {
    last = millis();
    temperature = readTemperature();
  }
}
