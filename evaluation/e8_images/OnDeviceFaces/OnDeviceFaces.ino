// Counts faces on the board with esp-dl, for comparison with CloudFaces.
// Needs arduino-esp32 2.0.x (3.x no longer ships esp-dl) and an ESP32-S3 with PSRAM.
// The detector and its thresholds are those of the core's CameraWebServer example
// (two-stage: HumanFaceDetectMSR01 + HumanFaceDetectMNP01).
// images.h is made by make_header.py from the selected WIDER FACE images.
#include "images.h"
#include "img_converters.h"
#include "human_face_detect_msr01.hpp"
#include "human_face_detect_mnp01.hpp"

void setup() {
  Serial.begin(115200);
  delay(3000);
  HumanFaceDetectMSR01 s1(0.1F, 0.5F, 10, 0.2F);
  HumanFaceDetectMNP01 s2(0.5F, 0.3F, 5);
  Serial.println("BEGIN");
  Serial.println("id,faces,decode_ms,detect_ms,boxes");
  for (size_t i = 0; i < IMAGE_COUNT; i++) {
    const TestImage& img = IMAGES[i];
    uint8_t* rgb = (uint8_t*)ps_malloc(img.width * img.height * 3);
    unsigned long t0 = millis();
    bool ok = rgb && fmt2rgb888(img.data, img.length, PIXFORMAT_JPEG, rgb);
    unsigned long t1 = millis();
    String boxes;
    int faces = -1;
    if (ok) {
      std::list<dl::detect::result_t>& candidates = s1.infer(rgb, {img.height, img.width, 3});
      std::list<dl::detect::result_t>& results = s2.infer(rgb, {img.height, img.width, 3}, candidates);
      faces = results.size();
      for (auto& r : results) {
        boxes += String(r.box[0]) + " " + r.box[1] + " " + r.box[2] + " " + r.box[3] + ";";
      }
    }
    unsigned long t2 = millis();
    free(rgb);
    Serial.printf("%s,%d,%lu,%lu,%s\n", img.id, faces, t1 - t0, t2 - t1, boxes.c_str());
  }
  Serial.printf("min_free_heap,%u\nmin_free_psram,%u\n", ESP.getMinFreeHeap(), ESP.getMinFreePsram());
  Serial.println("END");
}

void loop() {}
