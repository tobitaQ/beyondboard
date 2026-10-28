// E2: latency of each call, measured on the board.
// Prints CSV lines "bench,<destination>,<op>,<i>,<ms>,<code>" and heap figures.
//
// aws:   copy backend/out/device-1/aws_config.h here and upload.
// local: change USE_LOCAL to 1, upload, then run local/cloud_local.py and keep its output.
#define USE_LOCAL 0
#define REPEAT 30

#if USE_LOCAL
#include <BeyondBoard.h>
Cloud& cloud = local;
const char* DEST = "local";
#else
#include "aws_config.h"
Cloud& cloud = aws;
const char* DEST = "aws";
#endif

const char* labels[] = {"normal", "warning", "danger"};

void report(const char* op, int i, unsigned long ms) {
  Serial.printf("bench,%s,%s,%d,%lu,%d\n", DEST, op, i, ms, cloud.lastErrorCode());
}

void setup() {
#if !USE_LOCAL
  Serial.begin(115200);
  delay(500);
#endif
  unsigned long t = millis();
#if USE_LOCAL
  bool ok = local.begin();
#else
  bool ok = aws.begin();
#endif
  report("begin", 0, millis() - t);
  if (!ok) Serial.println(cloud.lastError());
  cloud.warnings(false);  // this benchmark calls quickly on purpose

  for (int i = 0; i < REPEAT; i++) {
    t = millis(); cloud.save("bench/temp.csv", 20.0 + i / 10.0); report("save", i, millis() - t);
  }
  for (int i = 0; i < REPEAT; i++) {
    t = millis(); cloud.load("config.json"); report("load", i, millis() - t);
  }
  for (int i = 0; i < REPEAT; i++) {
    t = millis(); cloud.run("detectAnomaly", String(25 + i % 10)); report("run", i, millis() - t);
  }
  for (int i = 0; i < REPEAT; i++) {
    t = millis(); cloud.ask("How safe is this server room?", String(20 + i) + " C", labels, 3);
    report("ask", i, millis() - t);
  }
#if defined(ESP32)
  Serial.printf("heap,%s,free=%u,min_free=%u\n", DEST, ESP.getFreeHeap(), ESP.getMinFreeHeap());
#endif
  Serial.println("bench,done");
}

void loop() {}
