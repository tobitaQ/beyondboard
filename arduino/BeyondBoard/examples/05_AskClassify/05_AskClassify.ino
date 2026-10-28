// Lets an AI choose a label, then saves the label.
// With choices, the answer is always exactly one of them.
//
// Before you start:
//   1. Build the backend once:  cd backend && npm run deploy
//   2. Write your Wi-Fi name and password in backend/out/device-1/aws_config.h,
//      and copy that file into this sketch folder. This sketch holds no passwords.
#include "aws_config.h"

const char* labels[] = {"normal", "warning", "danger"};

float readTemperature() {
  return 20.0 + random(0, 400) / 10.0;
}

void setup() {
  Serial.begin(115200);
  if (!aws.begin()) {
    Serial.println(aws.lastError());
  }
}

void loop() {
  float temp = readTemperature();
  String label = aws.ask("How safe is this temperature for a server room?", String(temp) + " C",
                         labels, 3);
  if (aws.ok()) {
    Serial.print(temp);
    Serial.print(" -> ");
    Serial.println(label);
    aws.save("status.csv", String(temp) + " " + label);
  } else {
    Serial.println(aws.lastError());
  }
  delay(60000);
}
