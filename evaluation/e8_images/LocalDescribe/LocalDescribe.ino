// Asks the local destination (Ollama on the computer, over USB) to describe the
// same first ten images as CloudFaces. Run local/cloud_local.py while it runs;
// the lines below appear in its output.
#include <BeyondBoard.h>
#include "images.h"

void setup() {
  if (!local.begin()) return;
  Serial.println("BEGIN");
  Serial.println("id,ask_ms,answer");
  for (size_t i = 0; i < 10 && i < IMAGE_COUNT; i++) {
    const TestImage& img = IMAGES[i];
    unsigned long t0 = millis();
    String what = local.ask("Describe this picture in one sentence.", CloudBytes(img.data, img.length));
    Serial.printf("%s,%lu,\"%s\"\n", img.id, millis() - t0, local.ok() ? what.c_str() : local.lastError().c_str());
  }
  Serial.println("END");
}

void loop() {}
