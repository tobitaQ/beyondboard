// BeyondBoard: use storage, computing and AI from a sketch in one line.
//
// Choose where the work happens by the object name. Everything else is the same.
//   aws   : your AWS account, over Wi-Fi (ESP32).  #include "aws_config.h" made by `npm run deploy`
//   local : this computer, over the USB cable.     run `python3 local/cloud_local.py` on the computer
//
//   aws.begin();                                    // or local.begin();
//   aws.save("temp.csv", 23.5);                     // add one line to temp.csv
//   String s = aws.load("temp.csv");                // read it back
//   String r = aws.run("detectAnomaly", "38.2");    // run backend/functions/detectAnomaly.py
//   String a = aws.ask("Is 38.2 C hot?");           // ask an AI
//
// Every call waits until it is done. Check ok() and print lastError() to see
// what went wrong. The meaning of each call is fixed by the contract.
#pragma once

#include <Arduino.h>

enum CloudErrorCode {
  CLOUD_OK = 0,
  CLOUD_ERR_NOT_INITIALIZED = 1,
  CLOUD_ERR_WIFI = 2,
  CLOUD_ERR_NETWORK = 3,
  CLOUD_ERR_AUTH = 4,
  CLOUD_ERR_NOT_FOUND = 5,
  CLOUD_ERR_TOO_LARGE = 6,
  CLOUD_ERR_TYPE_MISMATCH = 7,
  CLOUD_ERR_TIMEOUT = 8,
  CLOUD_ERR_RUN_FAILED = 9,
  CLOUD_ERR_AI_FORMAT = 10,
  CLOUD_ERR_LIMIT = 11,
  CLOUD_ERR_INVALID_NAME = 12,
  CLOUD_ERR_SERVER = 13,
};

// Bytes such as a JPEG photo. A camera Photo (BeyondBoardCamera.h) is one.
struct CloudBytes {
  const uint8_t* data = nullptr;
  size_t length = 0;
  CloudBytes() {}
  CloudBytes(const uint8_t* d, size_t n) : data(d), length(n) {}
};

// The calls every destination offers.
class Cloud {
 public:
  // Adds one line "time,value" to `name`.
  bool save(const char* name, const char* value);
  bool save(const char* name, const String& value);
  bool save(const char* name, int value);
  bool save(const char* name, long value);
  bool save(const char* name, unsigned long value);
  bool save(const char* name, double value);
  // Saves bytes (for example a photo) under `name`, replacing what was there. Up to 1 MB.
  bool save(const char* name, const CloudBytes& bytes);
  bool save(const char* name, const uint8_t* data, size_t length) {
    return save(name, CloudBytes(data, length));
  }

  // Reads `name`: all lines this device saved, or a file put in backend/files/.
  // With `last`, only the last `last` lines.
  String load(const char* name, unsigned int last = 0);

  // Deletes what this device saved under `name`.
  bool remove(const char* name);

  // Names this device has saved under, one per line. With `prefix`, only those starting with it.
  String list(const char* prefix = "");

  // Runs backend/functions/<name>.py with `input` and returns its result.
  String run(const char* name, const String& input = "", unsigned long timeoutMs = 10000);

  // Asks an AI. With `choices`, the answer is always exactly one of them.
  String ask(const char* prompt, const String& data = "");
  String ask(const char* prompt, const String& data, const char* const choices[], size_t count);
  // Asks about a JPEG image, optionally with choices.
  String ask(const char* prompt, const CloudBytes& image, const char* const choices[] = nullptr,
             size_t count = 0);

  bool ok() const { return _code == CLOUD_OK; }
  int lastErrorCode() const { return _code; }
  String lastError() const { return _error; }

  // When calls are too frequent (and would cost money), a warning is printed
  // once to Serial. Turn it off with warnings(false).
  void warnings(bool on) { _warnings = on; }

 protected:
  explicit Cloud(const char* name) : _name(name) { _error = F("Call begin() first."); }
  virtual ~Cloud() {}

  // Sends one request and returns the raw JSON answer.
  // On failure, calls fail() and returns false.
  virtual bool send(const char* op, const String& body, unsigned long timeoutMs, const String& id,
                    String& answer) = 0;

  bool request(const char* op, const String& body, unsigned long timeoutMs, String* result);
  bool fail(int code, const String& message);
  bool fail(int code, const __FlashStringHelper* message);
  bool checkName(const char* name);
  void noteCall(const char* op);

  const char* _name;  // "aws" or "local", used in messages

  // Rough cost per call in USD, for the warning. 0 means free.
  float _askCost = 0;
  float _callCost = 0;
  long _askDailyLimit = 0;
  bool _ready = false;
  int _code = CLOUD_ERR_NOT_INITIALIZED;
  String _error;

 private:
  bool _warnings = true;
  // Per call type (ask, other): calls in the current minute, and whether we already warned.
  unsigned long _windowStart[2] = {0, 0};
  unsigned int _calls[2] = {0, 0};
  bool _warned[2] = {false, false};
};

// ---- local: this computer, over USB serial (any board) ----

class LocalCloud : public Cloud {
 public:
  LocalCloud() : Cloud("local") {}
  // Starts Serial and waits (up to waitMs) for the program on the computer.
  bool begin(unsigned long baud = 115200, unsigned long waitMs = 30000);
  // Uses another port that is already started, such as Serial1.
  bool begin(Stream& port, unsigned long waitMs = 30000);

 protected:
  bool send(const char* op, const String& body, unsigned long timeoutMs, const String& id,
            String& answer) override;

 private:
  Stream* _port = nullptr;
};

extern LocalCloud local;

// ---- aws: your AWS account, over Wi-Fi (ESP32) ----
// Defined in BeyondBoardAws.h, which aws_config.h includes.
