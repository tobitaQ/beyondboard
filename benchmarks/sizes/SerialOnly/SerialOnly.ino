// Baseline for local: Serial and String only.
void setup() {
  Serial.begin(115200);
  Serial.println(String(1.5, 6));
}
void loop() {
  if (Serial.available()) Serial.println(Serial.readStringUntil('\n'));
}
