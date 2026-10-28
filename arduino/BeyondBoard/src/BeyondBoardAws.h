// aws: your AWS account, over Wi-Fi and HTTPS (ESP32).
// Included by aws_config.h (made by `npm run deploy`), which defines the
// URL, token and Wi-Fi first. Sketches that only use `local` never include
// this file, so the Wi-Fi and HTTPS libraries are not built into them.
#pragma once

#if !defined(ESP32)
#error "aws needs an ESP32 board (it uses Wi-Fi). Use local to work over USB instead."
#endif
#if !defined(AWS_CLOUD_URL) || !defined(AWS_CLOUD_TOKEN)
#error "Include \"aws_config.h\" (made by `npm run deploy`) instead of BeyondBoardAws.h."
#endif

#include <HTTPClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>

#include "AwsCloudCA.h"
#include "BeyondBoard.h"

class AwsCloud : public Cloud {
 public:
  AwsCloud() : Cloud("aws") {
#ifdef AWS_ASK_COST_USD
    _askCost = AWS_ASK_COST_USD;
    _callCost = AWS_CALL_COST_USD;
    _askDailyLimit = AWS_ASK_DAILY_LIMIT;
#endif
  }

  // Connects to the Wi-Fi in aws_config.h and checks that the cloud can be reached.
  // The sketch itself holds no passwords.
  bool begin() { return connect(AWS_WIFI_NAME, AWS_WIFI_PASSWORD, AWS_CLOUD_URL, AWS_CLOUD_TOKEN); }
  bool begin(const char* ssid, const char* password) {  // to use another Wi-Fi
    return connect(ssid, password, AWS_CLOUD_URL, AWS_CLOUD_TOKEN);
  }

 protected:
  bool send(const char* op, const String& body, unsigned long timeoutMs, const String& id,
            String& answer) override {
    if (WiFi.status() != WL_CONNECTED) {  // try once to reconnect before giving up
      WiFi.reconnect();
      unsigned long start = millis();
      while (WiFi.status() != WL_CONNECTED && millis() - start < 10000) delay(200);
      if (WiFi.status() != WL_CONNECTED) {
        return fail(CLOUD_ERR_WIFI, F("Wi-Fi was disconnected and could not reconnect."));
      }
    }

    // _http is kept between calls: destroying an HTTPClient closes the TLS
    // connection, and a new handshake costs about 0.35 s on an ESP32.
    HTTPClient& http = _http;
    int status = 0;
    // A kept connection may have been closed by the server while idle. If sending fails
    // before the request leaves the board, open a new connection and send once more.
    // (Not when the answer is lost: the cloud may already have done the work.)
    for (int attempt = 0; attempt < 2; attempt++) {
      http.setReuse(true);
      http.setConnectTimeout(10000);
      unsigned long t = timeoutMs + 5000;
      http.setTimeout(t > 65000 ? 65000 : (uint16_t)t);
      if (!http.begin(_client, _url + "/v1/" + op)) {
        return fail(CLOUD_ERR_NETWORK, F("Could not reach the cloud. Check the internet connection."));
      }
      http.addHeader("Content-Type", "application/json");
      http.addHeader("x-device-token", _token);
      http.addHeader("x-request-id", id);
      status = http.POST(body);
      bool notSent = status == HTTPC_ERROR_CONNECTION_REFUSED || status == HTTPC_ERROR_SEND_HEADER_FAILED ||
                     status == HTTPC_ERROR_SEND_PAYLOAD_FAILED || status == HTTPC_ERROR_NOT_CONNECTED;
      if (!notSent || attempt == 1) break;
      http.end();
      _client.stop();
    }
    if (status <= 0) {
      http.end();
      if (status == HTTPC_ERROR_READ_TIMEOUT) {
        return fail(CLOUD_ERR_TIMEOUT, F("The cloud did not answer in time."));
      }
      return fail(CLOUD_ERR_NETWORK, String(F("Could not reach the cloud. Check the internet connection. (")) +
                                         status + ')');
    }
    answer = http.getString();
    http.end();
    if (status != 200) {
      return fail(CLOUD_ERR_SERVER, "The cloud returned an error. Check that the backend is deployed.");
    }
    return true;
  }

 private:
  bool connect(const char* ssid, const char* password, const char* url, const char* token) {
    // Like local.begin(), start Serial if the sketch has not, so that a sketch
    // keeps printing when it switches between local and aws.
    if (Serial.baudRate() == 0) Serial.begin(115200);
    _ready = false;
    if (!url || !token) {
      return fail(CLOUD_ERR_AUTH,
                  "aws_config.h was not found. Run `npm run deploy`, copy out/<device>/aws_config.h "
                  "into your sketch folder, and write #include \"aws_config.h\" at the top.");
    }
    _url = url;
    _token = token;

    if (ssid && strcmp(ssid, "wifi-name") == 0) {
      return fail(CLOUD_ERR_WIFI, "Write your Wi-Fi name and password in aws_config.h.");
    }
    if (ssid && WiFi.status() != WL_CONNECTED) {
      WiFi.mode(WIFI_STA);
      // Stop an earlier attempt (for example, with a wrong name) that may still be
      // running; otherwise the board refuses the new settings.
      WiFi.disconnect();
      delay(100);
      WiFi.begin(ssid, password);
      unsigned long start = millis();
      while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) delay(200);
    }
    wl_status_t status = WiFi.status();
    if (status != WL_CONNECTED) {
      if (!ssid) {
        return fail(CLOUD_ERR_WIFI, "Wi-Fi is not connected. Write your Wi-Fi name and password in aws_config.h.");
      }
      if (status == WL_NO_SSID_AVAIL) {
        return fail(CLOUD_ERR_WIFI, String("Wi-Fi \"") + ssid +
                                        "\" was not found. ESP32 can only use 2.4 GHz Wi-Fi: if your router "
                                        "has two names (for example ...-G-... and ...-A-...), use the 2.4 GHz one.");
      }
      return fail(CLOUD_ERR_WIFI, String("Could not connect to Wi-Fi \"") + ssid + "\". Check the password.");
    }

    _client.setCACert(AWS_CLOUD_ROOT_CA);
    _ready = true;
    String ignored;
    if (!request("ping", "{}", 15000, &ignored)) {
      _ready = false;
      return false;
    }
    return true;
  }

  WiFiClientSecure _client;
  HTTPClient _http;
  String _url;
  String _token;
};

inline AwsCloud aws;
