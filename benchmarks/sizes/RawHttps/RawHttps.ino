// Baseline for aws: the least a sketch needs to POST JSON over HTTPS by hand
// (Wi-Fi, certificate check, one request). No cloud features, no error handling.
#include <HTTPClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>

static const char CA[] = "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----\n";
WiFiClientSecure client;

void setup() {
  Serial.begin(115200);
  WiFi.begin("wifi-name", "wifi-password");
  while (WiFi.status() != WL_CONNECTED) delay(200);
  client.setCACert(CA);
  HTTPClient http;
  http.begin(client, "https://example.com/v1/save");
  http.addHeader("Content-Type", "application/json");
  int code = http.POST("{\"name\":\"temp.csv\",\"value\":\"23.5\"}");
  Serial.println(code);
  Serial.println(http.getString());
  http.end();
}

void loop() {}
