// Saves a temperature to the cloud every 10 seconds.
// Each aws.save() adds one line "time,value" to temp.csv in the cloud.
//
// Before you start:
//   1. Build the backend once:  cd backend && npm run deploy
//   2. Write your Wi-Fi name and password in backend/out/device-1/aws_config.h,
//      and copy that file into this sketch folder. This sketch holds no passwords.
#include "aws_config.h"

// Replace this with your sensor.
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
  if (aws.save("temp.csv", temp)) {
    Serial.print("saved ");
    Serial.println(temp);
  } else {
    Serial.println(aws.lastError());
  }
  delay(10000);
}
