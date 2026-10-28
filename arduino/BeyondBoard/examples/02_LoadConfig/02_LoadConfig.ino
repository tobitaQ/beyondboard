// Reads settings from the cloud.
// Put a file in backend/files/ (for example config.json) and deploy;
// then aws.load("config.json") returns its contents.
// aws.load("temp.csv") returns the lines this device saved.
//
// Before you start:
//   1. Build the backend once:  cd backend && npm run deploy
//   2. Write your Wi-Fi name and password in backend/out/device-1/aws_config.h,
//      and copy that file into this sketch folder. This sketch holds no passwords.
#include "aws_config.h"

void setup() {
  Serial.begin(115200);
  if (!aws.begin()) {
    Serial.println(aws.lastError());
    return;
  }

  String config = aws.load("config.json");
  if (aws.ok()) {
    Serial.println("config.json:");
    Serial.println(config);
  } else {
    Serial.println(aws.lastError());
  }
}

void loop() {
}
