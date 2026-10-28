// Runs your own function in the cloud.
// aws.run("detectAnomaly", ...) runs backend/functions/detectAnomaly.py.
// Try the function on your computer first:  npm run try -- detectAnomaly 38.2
//
// Before you start:
//   1. Build the backend once:  cd backend && npm run deploy
//   2. Write your Wi-Fi name and password in backend/out/device-1/aws_config.h,
//      and copy that file into this sketch folder. This sketch holds no passwords.
#include "aws_config.h"

float readTemperature() {
  return 20.0 + random(0, 150) / 10.0;
}

void setup() {
  Serial.begin(115200);
  if (!aws.begin()) {
    Serial.println(aws.lastError());
  }
}

void loop() {
  float temp = readTemperature();
  String result = aws.run("detectAnomaly", String(temp));
  if (aws.ok()) {
    Serial.print(temp);
    Serial.print(" -> ");
    Serial.println(result);
  } else {
    Serial.println(aws.lastError());
  }
  delay(10000);
}
