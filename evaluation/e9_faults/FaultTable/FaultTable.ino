// Fault injection: causes each failure on purpose and prints what the device
// sees (ok, error code, sentence, time). Needs aws_config.h in this folder.
// After "WAITING", revoke the device's token on the computer
// (npm run revoke -- <device>) and send any line to continue.
#include "aws_config.h"

void report(const char* id, const char* fault, bool ok, unsigned long t0) {
  Serial.printf("%s|%s|%s|%d|%s|%lu\n", id, fault, ok ? "ok" : "fail", aws.lastErrorCode(),
                ok ? "" : aws.lastError().c_str(), millis() - t0);
}

void setup() {
  Serial.begin(115200);
  delay(3000);
  Serial.println("BEGIN");
  Serial.println("id|fault|result|code|message|ms");
  unsigned long t;

  t = millis(); bool ok = aws.save("e9/log.csv", 1); report("F1", "call before begin()", ok, t);
  t = millis(); ok = aws.begin("no-such-wifi-beyondboard", "password1"); report("F2", "Wi-Fi name not found", ok, t);
  t = millis(); ok = aws.begin(AWS_WIFI_NAME, "wrong-password-123"); report("F3", "wrong Wi-Fi password", ok, t);
  t = millis(); ok = aws.begin(); report("F0", "correct settings", ok, t);
  t = millis(); ok = aws.save("bad name!", 1); report("F4", "invalid name", ok, t);
  t = millis(); aws.run("noSuchFunction", "x"); report("F5", "function does not exist", aws.ok(), t);
  t = millis(); aws.run("testFail", "x"); report("F6", "exception in the user's function", aws.ok(), t);
  t = millis(); aws.run("testSleep", "5", 2000); report("F7", "function exceeds its time limit", aws.ok(), t);

  size_t big = 1100 * 1024;
  uint8_t* data = (uint8_t*)ps_malloc(big);
  if (data) memset(data, 0xFF, big);
  t = millis(); ok = data && aws.save("e9/big.jpg", data, big); report("F8", "photo over 1 MB", ok, t);
  free(data);

  uint8_t small[] = {0xFF, 0xD8, 0xFF, 0xD9};
  aws.save("e9/photo.jpg", small, sizeof(small));
  t = millis(); ok = aws.save("e9/photo.jpg", "a line"); report("F9", "text line saved to a photo", ok, t);

  aws.remove("e9/log.csv");
  WiFi.disconnect(false);
  delay(500);
  t = millis(); ok = aws.save("e9/log.csv", 1); report("F10", "Wi-Fi dropped before a call", ok, t);
  String lines = aws.load("e9/log.csv");
  int count = 0;
  for (char c : lines) count += c == '\n';
  if (lines.length() && !lines.endsWith("\n")) count++;
  Serial.printf("F10b|lines saved after reconnect|%d\n", count);

  Serial.println("WAITING");
  while (!Serial.available()) delay(100);
  t = millis(); ok = aws.save("e9/log.csv", 2); report("F11", "token revoked", ok, t);
  Serial.println("END");
}

void loop() {}
