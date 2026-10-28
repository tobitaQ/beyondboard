// App 1: save a temperature every 10 seconds
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

  Serial.print("Connecting to AWS IOT");
  while (!client.connect(THINGNAME)) {
    Serial.print(".");
    delay(100);
  }
  if (!client.connected()) {
    Serial.println("AWS IoT Timeout!");
    return;
  }

  Serial.println("AWS IoT Connected!");
}

float readTemperature() {
  return 20.0 + random(0, 150) / 10.0;
}

#define AWS_IOT_PUBLISH_TOPIC "esp32/temp"

void publishTemperature(float temp) {
  JsonDocument doc;
  doc["temp"] = temp;
  char jsonBuffer[512];
  serializeJson(doc, jsonBuffer);
  client.publish(AWS_IOT_PUBLISH_TOPIC, jsonBuffer);
}

void setup() {
  Serial.begin(115200);
  connectAWS();
}

void loop() {
  publishTemperature(readTemperature());
  client.loop();
  delay(10000);
}
