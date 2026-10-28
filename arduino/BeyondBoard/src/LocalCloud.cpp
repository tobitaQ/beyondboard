// local: this computer, over the USB cable (any board).
// Each request is one line "@cloud {...}"; the program on the computer
// (local/cloud_local.py) answers with one line in the same form. Other lines,
// such as your own Serial.println, are shown by that program.
#define BEYOND_BOARD_LIBRARY_SOURCE
#include "BeyondBoard.h"

LocalCloud local;

static const char PREFIX[] = "@cloud ";
static const unsigned long PING_INTERVAL_MS = 1000;
static const unsigned long ANSWER_MARGIN_MS = 5000;

bool LocalCloud::begin(unsigned long baud, unsigned long waitMs) {
  Serial.begin(baud);
  return begin(Serial, waitMs);
}

bool LocalCloud::begin(Stream& port, unsigned long waitMs) {
  _port = &port;
  _ready = true;  // later calls try again even if the computer is not ready yet
  unsigned long start = millis();
  String ignored;
  do {
    if (request("ping", "{}", PING_INTERVAL_MS, &ignored)) return true;
  } while (_code == CLOUD_ERR_TIMEOUT && millis() - start < waitMs);
  return false;
}

bool LocalCloud::send(const char* op, const String& body, unsigned long timeoutMs, const String& id,
                      String& answer) {
  while (_port->available()) _port->read();  // drop anything left from before
  _port->print(PREFIX);
  _port->print(F("{\"op\":\""));
  _port->print(op);
  _port->print(F("\",\"id\":\""));
  _port->print(id);
  _port->print(F("\",\"body\":"));
  _port->print(body);
  _port->print(F("}\n"));

  String wanted = String(F("\"id\": \"")) + id + '"';
  String line;
  unsigned long start = millis();
  unsigned long limit = timeoutMs + (timeoutMs > PING_INTERVAL_MS ? ANSWER_MARGIN_MS : 0);
  while (millis() - start < limit) {
    if (!_port->available()) {
      delay(1);
      continue;
    }
    char c = _port->read();
    if (c != '\n') {
      if (c != '\r') line += c;
      continue;
    }
    if (line.startsWith(PREFIX) && line.indexOf(wanted) >= 0) {
      answer = line.substring(sizeof(PREFIX) - 1);
      return true;
    }
    line = "";
  }
  return fail(CLOUD_ERR_TIMEOUT,
              F("No answer from the computer. Close the Serial Monitor and start: python3 "
                "local/cloud_local.py"));
}
