// Counts faces with BeyondBoard: save each image, then run countFaces (Amazon
// Rekognition) on it by name; faceBoxes returns the boxes for scoring.
// Then asks the AI to describe the first ten images.
// Same images.h as OnDeviceFaces. Needs aws_config.h in this folder.
#include "aws_config.h"
#include "images.h"

void setup() {
  if (!aws.begin()) Serial.println(aws.lastError());
  Serial.println("BEGIN");
  Serial.println("id,faces,save_ms,run_ms,boxes");
  for (size_t i = 0; i < IMAGE_COUNT; i++) {
    const TestImage& img = IMAGES[i];
    String name = String("e8/") + img.id + ".jpg";
    unsigned long t0 = millis();
    bool saved = aws.save(name.c_str(), img.data, img.length);
    unsigned long t1 = millis();
    String faces = saved ? aws.run("countFaces", name) : "";
    unsigned long t2 = millis();
    bool counted = aws.ok();
    String boxes = saved ? aws.run("faceBoxes", name) : "";
    Serial.printf("%s,%s,%lu,%lu,%s\n", img.id, counted ? faces.c_str() : "-1", t1 - t0, t2 - t1,
                  aws.ok() ? boxes.c_str() : "");
    if (!counted || !aws.ok()) Serial.println(aws.lastError());
  }
  Serial.println("id,ask_ms,answer");
  for (size_t i = 0; i < 10 && i < IMAGE_COUNT; i++) {
    const TestImage& img = IMAGES[i];
    unsigned long t0 = millis();
    String what = aws.ask("Describe this picture in one sentence.", CloudBytes(img.data, img.length));
    Serial.printf("%s,%lu,\"%s\"\n", img.id, millis() - t0, aws.ok() ? what.c_str() : aws.lastError().c_str());
  }
  Serial.println("END");
}

void loop() {}
