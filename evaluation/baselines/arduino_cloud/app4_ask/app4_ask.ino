// App 4: ask an AI to explain a reading
// Arduino Cloud version: Arduino Cloud has no AI, so the sketch calls Amazon Bedrock
// directly over HTTPS with a Bedrock API key kept on the board, as Arduino's blog does
// with OpenAI (2023). The answer is used right away, as aws.ask() does.
// The sketch Arduino Cloud generates, plus the lines the user writes.
// HTTPClient.h must come before thingProperties.h (name clash with ArduinoHttpClient on macOS).
// The Bedrock key is defined here, not in arduino_secrets.h: the Cloud Editor rebuilds
// that file from the Thing's secrets (checked by running app 4 on an ESP32, 2026-10-17).
#define SECRET_BEDROCK_API_KEY "bedrock-api-key"
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "arduino_secrets.h"
#include "thingProperties.h"

// Amazon Root CA 1, which signs the Bedrock endpoint's certificate.
const char ROOT_CA[] = R"EOF(
-----BEGIN CERTIFICATE-----
MIIDQTCCAimgAwIBAgITBmyfz5m/jAo54vB4ikPmljZbyjANBgkqhkiG9w0BAQsF
ADA5MQswCQYDVQQGEwJVUzEPMA0GA1UEChMGQW1hem9uMRkwFwYDVQQDExBBbWF6
b24gUm9vdCBDQSAxMB4XDTE1MDUyNjAwMDAwMFoXDTM4MDExNzAwMDAwMFowOTEL
MAkGA1UEBhMCVVMxDzANBgNVBAoTBkFtYXpvbjEZMBcGA1UEAxMQQW1hem9uIFJv
b3QgQ0EgMTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBALJ4gHHKeNXj
ca9HgFB0fW7Y14h29Jlo91ghYPl0hAEvrAIthtOgQ3pOsqTQNroBvo3bSMgHFzZM
9O6II8c+6zf1tRn4SWiw3te5djgdYZ6k/oI2peVKVuRF4fn9tBb6dNqcmzU5L/qw
IFAGbHrQgLKm+a/sRxmPUDgH3KKHOVj4utWp+UhnMJbulHheb4mjUcAwhmahRWa6
VOujw5H5SNz/0egwLX0tdHA114gk957EWW67c4cX8jJGKLhD+rcdqsq08p8kDi1L
93FcXmn/6pUCyziKrlA4b9v7LWIbxcceVOF34GfID5yHI9Y/QCB/IIDEgEw+OyQm
jgSubJrIqg0CAwEAAaNCMEAwDwYDVR0TAQH/BAUwAwEB/zAOBgNVHQ8BAf8EBAMC
AYYwHQYDVR0OBBYEFIQYzIU07LwMlJQuCFmcx7IQTgoIMA0GCSqGSIb3DQEBCwUA
A4IBAQCY8jdaQZChGsV2USggNiMOruYou6r4lK5IpDB/G/wkjUu0yKGX9rbxenDI
U5PMCCjjmCXPI6T53iHTfIUJrU6adTrCC2qJeHZERxhlbI1Bjjt/msv0tadQ1wUs
N+gDS63pYaACbvXy8MWy7Vu33PqUXHeeE6V/Uq2V8viTO96LXFvKWlJbYK8U90vv
o/ufQJVtMVT8QtPHRh8jrdkPSHCa2XV4cdFyQzR1bldZwgJcJmApzyMZFo6IQ6XU
5MsI+yMRQ+hDKXJioaldXgjUkK642M4UwtBV8ob2xJNDd2ZhwLnoQdeXeGADbkpy
rqXRfboQnoZsG4q5WTP468SQvvG5
-----END CERTIFICATE-----
)EOF";

// Bedrock Converse API with a Bedrock API key (Bearer). The model ID's ":" is written as %3A.
const char* BEDROCK_URL =
    "https://bedrock-runtime.ap-northeast-1.amazonaws.com/model/"
    "jp.anthropic.claude-haiku-4-5-20251001-v1%3A0/converse";

String askAI(String prompt, int maxTokens) {
  JsonDocument req;
  req["messages"][0]["role"] = "user";
  req["messages"][0]["content"][0]["text"] = prompt;
  req["inferenceConfig"]["maxTokens"] = maxTokens;
  String body;
  serializeJson(req, body);

  WiFiClientSecure client;
  client.setCACert(ROOT_CA);
  HTTPClient http;
  http.setTimeout(30000);
  http.begin(client, BEDROCK_URL);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", String("Bearer ") + SECRET_BEDROCK_API_KEY);
  int code = http.POST(body);
  String answer = "error " + String(code);
  if (code == 200) {
    JsonDocument res;
    deserializeJson(res, http.getString());
    answer = res["output"]["message"]["content"][0]["text"].as<String>();
  }
  http.end();
  return answer;
}

float readTemperature() {
  return 20.0 + random(0, 150) / 10.0;
}

bool asked = false;

void setup() {
  Serial.begin(9600);
  delay(1500);
  initProperties();
  ArduinoCloud.begin(ArduinoIoTPreferredConnection);
  setDebugMessageLevel(2);
  ArduinoCloud.printDebugInfo();
}

void loop() {
  ArduinoCloud.update();
  if (!asked && ArduinoCloud.connected()) {
    asked = true;
    temperature = readTemperature();
    String answer = askAI("Is this room temperature comfortable? Answer in one sentence.\n\nData:\n" +
                          String(temperature) + " C", 1024);
    Serial.println(answer);
  }
}
