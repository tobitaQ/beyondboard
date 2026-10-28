// Asks an AI to explain sensor data.
// Each question costs a little money; the backend limits questions per day.
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
    return;
  }

  float temp = readTemperature();
  String answer = aws.ask("Is this room temperature comfortable? Answer in one sentence.",
                          String(temp) + " C");
  if (aws.ok()) {
    Serial.println(answer);
  } else {
    Serial.println(aws.lastError());
  }
}

void loop() {
}
