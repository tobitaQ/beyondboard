// Takes a photo, saves it, counts the faces with a cloud service, and asks an AI about it.
// Needs an ESP32 board with a camera and PSRAM (Tools > PSRAM: "OPI PSRAM" on ESP32-S3).
//
// countFaces is backend/functions/countFaces.py: it calls Amazon Rekognition,
// a cloud service that is hard to match on the board itself. It only counts faces;
// it does not tell who they are.
//
// Before you start:
//   1. Build the backend once:  cd backend && npm run deploy
//   2. Write your Wi-Fi name and password in backend/out/device-1/aws_config.h,
//      and copy that file into this sketch folder. This sketch holds no passwords.
#include "aws_config.h"
#include <BeyondBoardCamera.h>

void setup() {
  if (!aws.begin()) Serial.println(aws.lastError());
  if (!camera.begin(CAMERA_FREENOVE_ESP32S3)) Serial.println(camera.lastError());
}

void loop() {
  Photo photo = camera.capture();
  if (!photo.ok()) {
    Serial.println(camera.lastError());
  } else if (aws.save("door.jpg", photo)) {
    String faces = aws.run("countFaces", "door.jpg");
    Serial.println(aws.ok() ? "faces: " + faces : aws.lastError());
    String what = aws.ask("Describe this picture in one sentence.", photo);
    Serial.println(aws.ok() ? "AI: " + what : aws.lastError());
  } else {
    Serial.println(aws.lastError());
  }
  delay(60000);
}
