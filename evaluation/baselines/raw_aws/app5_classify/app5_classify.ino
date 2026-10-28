// App 5: let an AI choose a label, then save it
// Raw AWS version, written the way the official AWS blog
// "Building an AWS IoT Core device using AWS Serverless and an ESP32" does
// (MQTT library by Joel Gaehwiler + ArduinoJson + WiFiClientSecure).
#include "secrets.h"
#include <WiFiClientSecure.h>
#include <MQTTClient.h>
#include <ArduinoJson.h>
#include "WiFi.h"

WiFiClientSecure net = WiFiClientSecure();
MQTTClient client = MQTTClient(1024);

void connectAWS() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.println("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  // Configure WiFiClientSecure to use the AWS IoT device credentials
  net.setCACert(AWS_CERT_CA);
  net.setCertificate(AWS_CERT_CRT);
  net.setPrivateKey(AWS_CERT_PRIVATE);

  client.begin(AWS_IOT_ENDPOINT, 8883, net);
  client.onMessage(messageHandler);
  Serial.print("Connecting to AWS IOT");
  while (!client.connect(THINGNAME)) {
    Serial.print(".");
    delay(100);
  }
  if (!client.connected()) {
    Serial.println("AWS IoT Timeout!");
    return;
  }
  client.subscribe("esp32/classify/reply");
  Serial.println("AWS IoT Connected!");
}

float readTemperature() {
  return 20.0 + random(0, 150) / 10.0;
}

String reply;
bool replied = false;

void messageHandler(String &topic, String &payload) {
  JsonDocument doc;
  deserializeJson(doc, payload);
  reply = doc["label"].as<String>();
  replied = true;
}

// MQTT is asynchronous: send a request, then wait for the answer on another topic.
bool request(const char* topic, JsonDocument& doc, unsigned long timeoutMs) {
  char jsonBuffer[512];
  serializeJson(doc, jsonBuffer);
  replied = false;
  client.publish(topic, jsonBuffer);
  unsigned long start = millis();
  while (!replied && millis() - start < timeoutMs) {
    client.loop();
    delay(10);
  }
  return replied;
}

void setup() {
  Serial.begin(115200);
  connectAWS();
}

void loop() {
  float temp = readTemperature();
  JsonDocument doc;
  doc["data"] = String(temp) + " C";
  // The Lambda asks the AI, checks that the answer is one of the labels,
  // and saves it to S3 before replying.
  if (request("esp32/classify/request", doc, 30000)) {
    Serial.print(temp);
    Serial.print(" -> ");
    Serial.println(reply);
  } else {
    Serial.println("No answer");
  }
  client.loop();
  delay(60000);
}
