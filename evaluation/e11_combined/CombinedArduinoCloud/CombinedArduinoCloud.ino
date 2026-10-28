// Arduino Cloud and BeyondBoard in one sketch: neighbouring tiers, used together.
// - Arduino Cloud connects the Wi-Fi, keeps device state, and shows a dashboard:
//   the temperature, the AI's comment, and an "Ask now" switch.
// - BeyondBoard uses the cloud: aws.save() keeps every reading in the user's own AWS
//   account, and aws.ask() asks an AI about the latest reading.
// The Wi-Fi password is written once, in arduino_secrets.h; BeyondBoard reuses the
// connection that Arduino Cloud made (aws.begin(SSID, PASS) does not reconnect when
// the board is already connected).
//
// aws_config.h must come first: it includes HTTPClient.h, whose name clashes on macOS
// with HttpClient.h of ArduinoHttpClient (installed with Arduino Cloud) if that comes first.
#include "aws_config.h"         // BeyondBoard: cloud URL and device token (Wi-Fi lines unused)
#include "arduino_secrets.h"
#include "thingProperties.h"    // Arduino Cloud: SSID, PASS and the cloud variables

bool awsReady = false;
bool askRequested = false;
unsigned long lastReading = 0;

float readTemperature() {
  return 20.0 + random(0, 150) / 10.0;
}

void setup() {
  Serial.begin(115200);
  delay(1500);
  initProperties();
  ArduinoCloud.begin(ArduinoIoTPreferredConnection);
  setDebugMessageLevel(2);
  ArduinoCloud.printDebugInfo();
}

void loop() {
  ArduinoCloud.update();
  if (!ArduinoCloud.connected()) return;

  // Start BeyondBoard only after Arduino Cloud has connected the Wi-Fi; earlier, it would
  // connect the Wi-Fi itself and get in Arduino Cloud's way.
  if (!awsReady) {
    awsReady = aws.begin(SSID, PASS);
    Serial.println(awsReady ? "BeyondBoard: ready" : aws.lastError());
    if (!awsReady) return;
  }

  if (millis() - lastReading > 60000 || lastReading == 0) {
    lastReading = millis();
    temperature = readTemperature();               // shown on the dashboard
    aws.save("combined/temp.csv", temperature);    // kept in the user's AWS account
    Serial.println(aws.ok() ? "saved " + String(temperature) : aws.lastError());
  }

  if (askRequested) {
    askRequested = false;
    unsigned long start = millis();
    String answer = aws.ask("Is this room temperature comfortable? Answer in one sentence.",
                            String(temperature) + " C");
    comment = aws.ok() ? answer : aws.lastError();   // shown on the dashboard
    askNow = false;                                   // turn the switch back off
    // ArduinoCloud.update() is not called while aws.ask() waits: check that the
    // connection to Arduino Cloud survives.
    Serial.print("ask took ");
    Serial.print(millis() - start);
    Serial.print(" ms; Arduino Cloud connected: ");
    Serial.println(ArduinoCloud.connected() ? "yes" : "no");
    Serial.println(comment);
  }
}

// Called when the "Ask now" switch is turned on in the dashboard. The question is asked
// in loop(), not here, so that this callback returns at once.
void onAskNowChange() {
  if (askNow) askRequested = true;
}
